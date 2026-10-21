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


@pytest.fixture
def certificates(tmp_path):
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)])
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(
        x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1)).not_valid_after(
        now + timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), critical=False).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256())
    cert_path, key_path = tmp_path/'tls.crt', tmp_path/'tls.key'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert_path, key_path)
    client = ssl.create_default_context(cafile=str(cert_path))
    return server, client


class Harness:
    def __init__(self, monkeypatch, certificates):
        self.monkeypatch, (self.server_context, self.client_context) = monkeypatch, certificates
        self.requests, self.connections, self.names, self.resolutions = [], [], [], []
        self.status, self.headers, self.body = 200, [], None
        self.content_type = b'application/json'
        self.gate = None
        self.fetcher = MetadataFetcher(ssl_context=self.client_context)
        self.server_context.set_servername_callback(lambda _, name, __: self.names.append(name))

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.respond, '127.0.0.1', 0, ssl=self.server_context)
        port = self.server.sockets[0].getsockname()[1]
        loop = asyncio.get_running_loop()
        connect = loop.sock_connect
        async def routed(sock, address):
            self.connections.append(address)
            assert address == (PUBLIC, 443)
            return await connect(sock, ('127.0.0.1', port))
        def resolve(host, port, *args):
            self.resolutions.append((host, port))
            assert host == HOST and port == 443
            return dns()
        self.monkeypatch.setattr(loop, 'sock_connect', routed)
        self.monkeypatch.setattr(socket, 'getaddrinfo', resolve)
        return self

    async def respond(self, reader, writer):
        try:
            request = await reader.readuntil(b'\r\n\r\n')
            self.requests.append(request)
            target = request.split(b' ', 2)[1].decode('ascii')
            if self.gate is not None:
                await self.gate.wait()
            body = self.body if self.body is not None else document('https://' + HOST + target)
            headers = [(b'Content-Type', self.content_type), *self.headers]
            if not any(name.lower() == b'content-length' for name, _ in headers):
                headers.append((b'Content-Length', str(len(body)).encode()))
            writer.write(b'HTTP/1.1 ' + str(self.status).encode() + b' Controlled\r\n' + b''.join(
                name + b': ' + value + b'\r\n' for name, value in headers) + b'\r\n' + body)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def __aexit__(self, *args):
        if self.gate:
            self.gate.set()
        await self.fetcher.aclose()
        self.server.close()
        await self.server.wait_closed()


