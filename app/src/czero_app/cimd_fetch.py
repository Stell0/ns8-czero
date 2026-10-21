# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded CIMD-only HTTPS transport over public httpcore/asyncio interfaces."""
import asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import urlsplit

import httpcore

from czero_core.cimd_metadata import ClientMetadata, MetadataRejected, metadata_url, parse_metadata


class FetchRejected(ValueError):
    def __init__(self, code='metadata_unavailable'):
        if code not in {'metadata_unavailable', 'metadata_rejected', 'metadata_busy'}:
            code = 'metadata_unavailable'
        super().__init__(code)
        self.code = code


def public_addresses(results):
    if not results or len(results) > 16:
        raise FetchRejected('metadata_rejected')
    addresses = []
    for family, kind, protocol, _, address in results:
        if family not in (socket.AF_INET, socket.AF_INET6) or kind != socket.SOCK_STREAM:
            raise FetchRejected('metadata_rejected')
        try:
            ip = ipaddress.ip_address(address[0])
        except ValueError:
            raise FetchRejected('metadata_rejected') from None
        if (not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_unspecified
                or ip.is_loopback or ip.is_link_local or ip.is_private or '%' in address[0]):
            raise FetchRejected('metadata_rejected')
        if ip.version == 6:
            if (family != socket.AF_INET6 or ip.ipv4_mapped is not None or ip.sixtofour is not None
                    or ip.teredo is not None or any(ip in network for network in (
                        ipaddress.ip_network('64:ff9b::/96'), ipaddress.ip_network('64:ff9b:1::/48'),
                        ipaddress.ip_network('2001::/23')))):
                raise FetchRejected('metadata_rejected')
        elif family != socket.AF_INET or any(ip in network for network in (
                ipaddress.ip_network('192.0.0.0/24'), ipaddress.ip_network('192.88.99.0/24'))):
            raise FetchRejected('metadata_rejected')
        item = (family, str(ip))
        if item not in addresses:
            addresses.append(item)
    return tuple(addresses)


def cache_seconds(headers, now):
    """Conservative HTTP freshness; malformed/ambiguous hints forbid reuse."""
    values = {}
    for name, value in headers:
        key = name.decode('ascii').lower()
        values.setdefault(key, []).append(value.decode('ascii'))
    directives = ','.join(values.get('cache-control', [])).lower().split(',')
    ttl = 60.0
    ages = []
    for part in directives:
        name, _, value = part.strip().partition('=')
        if name in {'no-store', 'no-cache'}:
            return 0
        if name == 'max-age':
            value = value.strip('"')
            if not re.fullmatch(r'[0-9]{1,10}', value):
                return 0
            ages.append(int(value))
    if len(ages) > 1:
        return 0
    date = now
    if 'date' in values:
        try:
            if len(values['date']) != 1:
                return 0
            date = parsedate_to_datetime(values['date'][0]).timestamp()
        except (TypeError, ValueError, OverflowError):
            return 0
    if ages:
        ttl = ages[0]
    elif 'expires' in values:
        try:
            if len(values['expires']) != 1:
                return 0
            ttl = parsedate_to_datetime(values['expires'][0]).timestamp() - date
        except (TypeError, ValueError, OverflowError):
            return 0
    age = max(0, now - date)
    if 'age' in values:
        if len(values['age']) != 1 or not re.fullmatch(r'[0-9]{1,10}', values['age'][0]):
            return 0
        age = max(age, int(values['age'][0]))
    return max(0, min(300, ttl - age))


class _Stream(httpcore.AsyncNetworkStream):
    def __init__(self, reader, writer, hostname):
        self.reader, self.writer, self.hostname = reader, writer, hostname
        self.received = 0

    async def read(self, max_bytes, timeout=None):
        async with asyncio.timeout(timeout):
            data = await self.reader.read(min(max_bytes, 65537 - self.received))
        self.received += len(data)
        if self.received > 65536:
            raise FetchRejected('metadata_rejected')
        return data

    async def write(self, buffer, timeout=None):
        async with asyncio.timeout(timeout):
            self.writer.write(buffer)
            await self.writer.drain()

    async def aclose(self):
        # Abort immediately rather than leaving TLS shutdown sockets alive after
        # the total request deadline or relinquishing a fetch concurrency slot.
        self.writer.transport.abort()

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        if (server_hostname != self.hostname or not ssl_context.check_hostname
                or ssl_context.verify_mode != ssl.CERT_REQUIRED):
            raise FetchRejected('metadata_rejected')
        async with asyncio.timeout(timeout):
            await self.writer.start_tls(ssl_context, server_hostname=server_hostname,
                                        ssl_handshake_timeout=timeout)
        return self

    def get_extra_info(self, info):
        if info in {'ssl_object', 'socket'}:
            return self.writer.get_extra_info(info)
        return None


class PinnedBackend(httpcore.AsyncNetworkBackend):
    """Per-fetch validated numeric peers; original hostname remains TLS identity."""
    def __init__(self, hostname, addresses):
        self.hostname, self.addresses = hostname, addresses

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.hostname or port != 443 or local_address is not None:
            raise FetchRejected('metadata_rejected')
        async with asyncio.timeout(timeout):
            for family, address in self.addresses:
                sock = socket.socket(family, socket.SOCK_STREAM)
                try:
                    sock.setblocking(False)
                    for option in socket_options or ():
                        sock.setsockopt(*option)
                    # Numeric addresses take asyncio's inet_pton fast path;
                    # no hostname is ever passed to a connecting resolver.
                    await asyncio.get_running_loop().sock_connect(sock, (address, port))
                    reader, writer = await asyncio.open_connection(sock=sock, limit=16384)
                    sock = None  # StreamWriter now owns the socket.
                    return _Stream(reader, writer, host)
                except OSError:
                    pass
                finally:
                    if sock is not None:
                        sock.close()
        raise httpcore.ConnectError('metadata_unavailable')

    async def connect_unix_socket(self, *args, **kwargs):
        raise FetchRejected('metadata_rejected')

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


@dataclass(frozen=True)
class FetchedMetadata:
    metadata: ClientMetadata
    fresh_until: float

    @property
    def remaining(self):
        return max(0, self.fresh_until - time.monotonic())


@dataclass
class _Flight:
    task: asyncio.Task
    waiters: int = 0


class MetadataFetcher:
    def __init__(self, *, ssl_context=None):
        self.ssl_context = ssl_context or ssl.create_default_context()
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='c0-cimd-dns')
        self.cache = OrderedDict()
        self.flights = {}
        self.active = self.waiters = 0
        self.closed = False

    async def fetch(self, url, *, reuse=True, cache=False):
        metadata_url(url)
        if self.closed:
            raise FetchRejected()
        if not reuse:
            self.cache.pop(url, None)
        if reuse and url in self.cache:
            value = self.cache[url]
            if value.remaining > 0:
                self.cache.move_to_end(url)
                return value
            del self.cache[url]
        flight = self.flights.get(url)
        if self.waiters >= 32 or (flight is not None and flight.waiters >= 8):
            raise FetchRejected('metadata_busy')
        if flight is None:
            if self.active >= 4:
                raise FetchRejected('metadata_busy')
            self.active += 1
            flight = _Flight(asyncio.create_task(self._fetch(url)))
            self.flights[url] = flight
            def finished(task):
                if self.flights.get(url) is flight:
                    del self.flights[url]
                if not task.cancelled():
                    task.exception()  # Consume an error even if all callers left.
            flight.task.add_done_callback(finished)
        flight.waiters += 1
        self.waiters += 1
        try:
            value = await asyncio.shield(flight.task)
            if cache and value.remaining > 0:
                self.remember(url, value)
            return value
        finally:
            flight.waiters -= 1
            self.waiters -= 1

    def remember(self, url, value):
        """Trusted caller has approved the binding; unknown previews stay uncached."""
        if value.metadata.client_id != url or value.remaining <= 0:
            return
        self.cache[url] = value
        self.cache.move_to_end(url)
        while len(self.cache) > 64:
            self.cache.popitem(last=False)

    async def _fetch(self, url):
        resolver = None
        loop = asyncio.get_running_loop()
        def release():
            self.active -= 1
        try:
            async with asyncio.timeout(5):
                hostname = urlsplit(url).hostname
                resolver = self.executor.submit(socket.getaddrinfo, hostname, 443,
                    socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP)
                wrapped = asyncio.wrap_future(resolver)
                wrapped.add_done_callback(lambda future: None if future.cancelled() else future.exception())
                addresses = public_addresses(await asyncio.shield(wrapped))
                backend = PinnedBackend(hostname, addresses)
                async with httpcore.AsyncConnectionPool(ssl_context=self.ssl_context, http1=True,
                        http2=False, max_connections=1, max_keepalive_connections=0,
                        retries=0, network_backend=backend) as pool:
                    async with pool.stream('GET', url, headers={
                            'Accept': 'application/json, application/*+json', 'Accept-Encoding': 'identity',
                            'User-Agent': 'C0-CIMD/1', 'Connection': 'close'},
                            extensions={'timeout': {'connect': 5, 'read': 5, 'write': 5, 'pool': 0}}) as response:
                        headers = response.headers
                        types = [v.split(b';', 1)[0].strip().lower() for k, v in headers if k.lower() == b'content-type']
                        encodings = [v.strip().lower() for k, v in headers if k.lower() == b'content-encoding']
                        if (response.status != 200 or len(types) != 1
                                or not re.fullmatch(rb'application/(?:json|[a-z0-9!#$&^_.+-]+\+json)', types[0])
                                or encodings not in ([], [b'identity'])):
                            raise FetchRejected('metadata_rejected')
                        body = bytearray()
                        async for chunk in response.aiter_stream():
                            body.extend(chunk)
                            if len(body) > 32768:
                                raise FetchRejected('metadata_rejected')
                        value = parse_metadata(url, bytes(body))
                        ttl = cache_seconds(headers, time.time())
                        return FetchedMetadata(value, time.monotonic() + ttl)
        except FetchRejected:
            raise
        except MetadataRejected:
            raise FetchRejected('metadata_rejected') from None
        except (OSError, TimeoutError, httpcore.NetworkError, httpcore.ProtocolError,
                httpcore.TimeoutException, UnicodeError, ValueError):
            raise FetchRejected() from None
        finally:
            if resolver is not None and not resolver.done():
                # A timed-out libc lookup cannot be cancelled. Keep its fetch
                # slot until the actual worker returns, preventing queued work.
                def resolved(_):
                    try:
                        if not loop.is_closed():
                            loop.call_soon_threadsafe(release)
                    except RuntimeError:
                        pass  # The owning event loop has already shut down.
                resolver.add_done_callback(resolved)
            else:
                release()

    async def aclose(self):
        self.closed = True
        tasks = [flight.task for flight in self.flights.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.cache.clear()
        self.executor.shutdown(wait=False, cancel_futures=True)
