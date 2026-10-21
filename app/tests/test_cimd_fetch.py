# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real HTTP/TLS, with only the synthetic public TCP destination routed locally."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import ipaddress
import json
import socket
import ssl
from threading import Event
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from czero_app.cimd_fetch import FetchRejected, MetadataFetcher, cache_seconds, public_addresses

HOST = 'cimd.example.test'
URL = 'https://' + HOST + '/client.json'
PUBLIC = '93.184.216.34'


def dns(address=PUBLIC):
    ip = ipaddress.ip_address(address)
    family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (address, 443))]


def document(url=URL, **changes):
    return json.dumps({'client_id': url, 'client_name': 'Controlled public client',
        'redirect_uris': ['https://client.example.test/callback'],
        'token_endpoint_auth_methods_supported': ['none', 'private_key_jwt'],
        'token_endpoint_auth_method': 'private_key_jwt',
        'grant_types': ['authorization_code', 'refresh_token'], **changes}).encode()


from pathlib import Path
import runpy
_fixture = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tests/cimd_https_fixture.py'))
certificates, Harness = _fixture['certificates'], _fixture['Harness']


@pytest.mark.parametrize('address', [
    '127.0.0.1', '10.0.0.1', '172.16.1.1', '192.168.1.1', '169.254.169.254', '0.0.0.0',
    '100.64.0.1', '192.0.0.9', '192.88.99.1', '198.18.0.1', '192.0.2.1', '224.0.0.1',
    '240.0.0.1', '::1', '::', 'fc00::1', 'fe80::1', 'ff02::1', '2001:db8::1',
    '::ffff:8.8.8.8', '2002:0808:0808::1', '2001:0:4136:e378:8000:63bf:3fff:fdd2',
    '64:ff9b::808:808', '64:ff9b:1::808:808', '2001:20::1',
])
def test_private_special_and_transition_addresses_are_all_rejected(address):
    with pytest.raises(FetchRejected):
        public_addresses(dns(address))
    with pytest.raises(FetchRejected):
        public_addresses(dns() + dns(address))


def test_public_dns_requires_bounded_complete_supported_results():
    assert public_addresses(dns() + dns('2606:4700:4700::1111')) == (
        (socket.AF_INET, PUBLIC), (socket.AF_INET6, '2606:4700:4700::1111'))
    for results in [[], dns() * 17, [(socket.AF_UNIX, socket.SOCK_STREAM, 0, '', ('/tmp/no', 443))]]:
        with pytest.raises(FetchRejected):
            public_addresses(results)


@pytest.mark.parametrize('control,age,expected', [
    ('', None, 60), ('max-age=600', None, 300), ('max-age=120', '100', 20),
    ('no-store, max-age=120', None, 0), ('no-cache', None, 0), ('max-age=0', None, 0),
    ('max-age=bogus', None, 0), ('max-age=120,max-age=120', None, 0),
    ('max-age=120', 'bogus', 0), ('max-age=120', '200', 0), ('max-age="90"', None, 90),
])
def test_cache_control_age_and_maximum_are_conservative(control, age, expected):
    headers = [(b'Cache-Control', control.encode())]
    if age is not None:
        headers.append((b'Age', age.encode()))
    assert cache_seconds(headers, 1900000000) == expected


def test_expires_and_date_account_for_stale_responses():
    now = datetime.fromtimestamp(1900000000, timezone.utc)
    headers = [(b'Date', format_datetime(now - timedelta(seconds=20), usegmt=True).encode()),
               (b'Expires', format_datetime(now + timedelta(seconds=50), usegmt=True).encode())]
    assert cache_seconds(headers, now.timestamp()) == 50
    assert cache_seconds(headers + [(b'Age', b'60')], now.timestamp()) == 10
    assert cache_seconds([(b'Date', b'invalid')], now.timestamp()) == 0


def test_real_tls_public_pin_sni_and_identity_without_jwks_or_forwarded_credentials(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.body = document(jwks_uri='http://169.254.169.254/trap', logo_uri='http://127.0.0.1/trap')
            value = await h.fetcher.fetch(URL, cache=True)
            assert value.metadata.client_id == URL and value.remaining > 0
            assert h.connections == [(PUBLIC, 443)] and h.names == [HOST] and h.resolutions == [(HOST, 443)]
            request = h.requests[0].lower()
            assert b'host: cimd.example.test' in request and b'accept-encoding: identity' in request
            for name in (b'authorization:', b'cookie:', b'referer:'):
                assert name not in request
            assert b'get /client.json ' in request
            assert (await h.fetcher.fetch(URL, cache=True)) == value
            assert len(h.requests) == 1
    asyncio.run(check())


def test_mixed_dns_rejected_before_any_connection_and_dns_rebinding_does_not_reresolve(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            monkeypatch.setattr(socket, 'getaddrinfo', lambda *args: dns() + dns('127.0.0.1'))
            with pytest.raises(FetchRejected):
                await h.fetcher.fetch(URL)
            assert h.connections == [] and h.requests == []
            calls = []
            def rebinding(*args):
                calls.append(args)
                return dns() if len(calls) == 1 else dns('127.0.0.1')
            monkeypatch.setattr(socket, 'getaddrinfo', rebinding)
            assert (await h.fetcher.fetch(URL)).metadata.client_id == URL
            assert len(calls) == 1 and h.connections == [(PUBLIC, 443)]
    asyncio.run(check())


@pytest.mark.parametrize('change', ['redirect', 'failure', 'compression', 'content_type', 'duplicate_type',
                                   'body_limit', 'header_limit', 'total_limit', 'duplicate_json', 'encoding', 'depth'])
def test_invalid_http_and_metadata_are_rejected_without_redirects_or_negative_cache(monkeypatch, certificates, change):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            if change == 'redirect':
                h.status, h.headers = 302, [(b'Location', b'https://trap.example.test/client.json')]
            elif change == 'failure':
                h.status = 500
            elif change == 'compression':
                h.headers = [(b'Content-Encoding', b'gzip')]
            elif change == 'content_type':
                h.content_type = b'text/html'
            elif change == 'duplicate_type':
                h.headers = [(b'Content-Type', b'application/json')]
            elif change == 'body_limit':
                h.body = b' ' * 32769
            elif change == 'header_limit':
                h.headers = [(b'X-Fill', b'a' * 66000)]
            elif change == 'total_limit':
                h.headers = [(b'X-Fill', b'a' * 40000)]
                h.body = b' ' * 30000 + document()
            elif change == 'duplicate_json':
                h.body = b'{"client_id":"' + URL.encode() + b'","client_id":"other"}'
            elif change == 'encoding':
                h.body = b'\xff'
            elif change == 'depth':
                h.body = b'{"x":' + b'[' * 17 + b'0' + b']' * 17 + b'}'
            for _ in range(2):
                with pytest.raises(FetchRejected):
                    await h.fetcher.fetch(URL, cache=True)
            assert len(h.connections) == 2 and not h.fetcher.cache
            assert all(b'trap' not in request for request in h.requests)
    asyncio.run(check())


@pytest.mark.parametrize('control', ['no-store', 'no-cache', 'max-age=0'])
def test_no_store_is_valid_request_local_metadata_but_not_reusable(monkeypatch, certificates, control):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.headers = [(b'Cache-Control', control.encode())]
            for _ in range(2):
                assert (await h.fetcher.fetch(URL, cache=True)).metadata.client_id == URL
            assert len(h.requests) == 2 and not h.fetcher.cache
    asyncio.run(check())


def test_fresh_preview_clears_cached_approval_and_unknown_preview_never_caches(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            original = await h.fetcher.fetch(URL, cache=True)
            h.body = document(client_name='Changed')
            changed = await h.fetcher.fetch(URL, reuse=False, cache=False)
            assert original.metadata.digest != changed.metadata.digest and not h.fetcher.cache
            assert (await h.fetcher.fetch(URL, cache=True)).metadata.digest == changed.metadata.digest
            assert len(h.requests) == 3
    asyncio.run(check())


def test_untrusted_certificate_and_wrong_hostname_cannot_complete_http(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            await h.fetcher.aclose()
            h.fetcher = MetadataFetcher()  # System trust cannot trust the synthetic CA.
            with pytest.raises(FetchRejected):
                await h.fetcher.fetch(URL)
            assert h.names == [HOST] and not h.requests
            await h.fetcher.aclose()
            h.fetcher = MetadataFetcher(ssl_context=h.client_context)
            # Route another public name to the same TLS endpoint. The certificate
            # lacks this hostname; SNI must remain that original requested name.
            monkeypatch.setattr(socket, 'getaddrinfo', lambda *args: dns())
            with pytest.raises(FetchRejected):
                await h.fetcher.fetch('https://wrong.example.test/client.json')
            assert h.names[-1] == 'wrong.example.test' and not h.requests
    asyncio.run(check())


def test_four_single_flights_bound_network_and_thirty_two_waiters_fail_fast(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.gate = asyncio.Event()
            urls = ['https://' + HOST + '/client' + str(i) + '.json' for i in range(4)]
            tasks = [asyncio.create_task(h.fetcher.fetch(url)) for url in urls for _ in range(8)]
            while len(h.requests) < 4:
                await asyncio.sleep(0)
            assert h.fetcher.active == 4 and h.fetcher.waiters == 32
            for url in [urls[0], 'https://' + HOST + '/extra.json']:
                with pytest.raises(FetchRejected, match='metadata_busy'):
                    await h.fetcher.fetch(url)
            assert len(h.resolutions) == 4 and len(h.connections) == 4
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[0]
            h.gate.set()
            results = await asyncio.gather(*tasks[1:])
            assert len(results) == 31 and h.fetcher.active == 0 and h.fetcher.waiters == 0
    asyncio.run(check())


def test_actual_five_second_dns_deadline_retains_slots_until_resolvers_finish(monkeypatch):
    release, entered = Event(), Event()
    calls = []
    def blocked(*args):
        calls.append(args)
        if len(calls) == 4:
            entered.set()
        release.wait(12)
        return dns()
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
    async def check():
        fetcher = MetadataFetcher()
        try:
            started = time.monotonic()
            tasks = [asyncio.create_task(fetcher.fetch('https://' + HOST + '/' + str(i))) for i in range(4)]
            while not entered.is_set():
                await asyncio.sleep(0)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assert all(isinstance(result, FetchRejected) for result in results)
            assert 4.8 < time.monotonic() - started < 6
            assert fetcher.active == 4 and len(calls) == 4
            for i in range(10):
                with pytest.raises(FetchRejected, match='metadata_busy'):
                    await fetcher.fetch('https://' + HOST + '/new' + str(i))
            assert len(calls) == 4
            release.set()
            deadline = time.monotonic() + 2
            while fetcher.active and time.monotonic() < deadline:
                await asyncio.sleep(0)
            assert fetcher.active == 0
        finally:
            release.set()
            await fetcher.aclose()
    asyncio.run(check())


def test_total_plaintext_bound_accepts_valid_response_below_limit(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.headers = [(b'X-Fill', b'a' * 30000)]
            h.body = b' ' * 30000 + document()
            assert (await h.fetcher.fetch(URL)).metadata.client_id == URL
    asyncio.run(check())


def test_actual_five_second_deadline_includes_stalled_http(monkeypatch, certificates):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.gate = asyncio.Event()
            started = time.monotonic()
            with pytest.raises(FetchRejected):
                await h.fetcher.fetch(URL)
            assert 4.8 < time.monotonic() - started < 6
            assert len(h.requests) == 1 and h.fetcher.active == 0
    asyncio.run(check())


@pytest.mark.parametrize('content_type', [b'application/json; charset=utf-8', b'application/oauth-client+json'])
def test_json_media_types_are_accepted(monkeypatch, certificates, content_type):
    async def check():
        async with Harness(monkeypatch, certificates) as h:
            h.content_type = content_type
            assert (await h.fetcher.fetch(URL)).metadata.client_id == URL
    asyncio.run(check())
