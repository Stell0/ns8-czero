# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded public HTTP with pinned DNS peers, verified TLS and no proxy/credentials."""
import http.client
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
import ipaddress
import queue
import socket
import ssl
from threading import Thread, Timer
from urllib.parse import urljoin, urlsplit

from c0_ingest.errors import C0Error
from .model import public_url


class FetchError(C0Error):
    def __init__(self,code,retry_after=''):
        super().__init__(code)
        self.retry_after=retry_after


def retry_time(value):
    if not value:return ''
    now=datetime.now(timezone.utc)
    try:
        desired=now+timedelta(seconds=int(value)) if value.isdigit() else parsedate_to_datetime(value)
        if desired.tzinfo is None:return ''
        return min(max(desired,now),now+timedelta(days=1)).isoformat()
    except (ValueError,TypeError,OverflowError):return ''


def public_addresses(host, port, timeout):
    result=queue.Queue(maxsize=1)
    def resolve():
        try: result.put(socket.getaddrinfo(host,port,type=socket.SOCK_STREAM))
        except OSError: result.put(None)
    Thread(target=resolve,daemon=True).start()
    try: rows=result.get(timeout=min(timeout,5))
    except queue.Empty: raise C0Error('source_dns_timeout') from None
    if not rows or len(rows)>32:
        raise C0Error('source_dns_unavailable')
    addresses=sorted({row[4][0] for row in rows})
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise C0Error('source_private_destination_denied')
    return addresses


class Fetcher:
    def __init__(self, config):
        self.config=config
        self.requests=0

    def get(self, url):
        initial=urlsplit(public_url(url))
        try:
            for redirect in range(4):
                parsed=urlsplit(public_url(url))
                if parsed.hostname.lower()!=initial.hostname.lower() or (initial.scheme=='https' and parsed.scheme!='https'):
                    raise C0Error('source_cross_host_redirect_denied')
                if self.requests>=self.config['max_requests']:
                    raise C0Error('source_request_budget_exhausted')
                port=443 if parsed.scheme=='https' else 80
                peers=public_addresses(parsed.hostname,port,self.config['timeout'])
                connection=(http.client.HTTPSConnection(parsed.hostname,port,timeout=self.config['timeout'],context=ssl.create_default_context())
                    if parsed.scheme=='https' else http.client.HTTPConnection(parsed.hostname,port,timeout=self.config['timeout']))
                connection._create_connection=lambda address,timeout,*args: socket.create_connection((peers[0],port),timeout)
                self.requests+=1
                def expire(current=connection):
                    try:
                        if current.sock: current.sock.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    current.close()
                timer=Timer(self.config['timeout'],expire);timer.daemon=True;timer.start()
                try:
                    connection.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),
                        headers={'User-Agent':'c0-projects/0.1','Accept':'text/*, application/xml, application/rss+xml, application/atom+xml, application/pdf'})
                    response=connection.getresponse()
                    if response.status in (301,302,303,307,308):
                        if redirect==3 or not response.getheader('Location'):
                            raise C0Error('source_redirect_limit')
                        url=urljoin(url,response.getheader('Location'))
                        continue
                    if response.status!=200:
                        raise FetchError('source_http_' + str(response.status),retry_time(response.getheader('Retry-After')))
                    declared=response.getheader('Content-Length')
                    if declared is not None and (not declared.isdigit() or int(declared)>self.config['max_bytes']):
                        raise C0Error('source_content_length_invalid_or_too_large')
                    content=response.read(self.config['max_bytes']+1)
                    if len(content)>self.config['max_bytes']:
                        raise C0Error('source_content_too_large')
                    if declared is not None and len(content)!=int(declared):
                        raise C0Error('source_incomplete_body')
                    if response.getheader('Content-Encoding','identity')!='identity':
                        raise C0Error('source_encoding_unsupported')
                    return content,url,response.getheader('Content-Type','text/plain').split(';')[0].strip().lower()
                finally:
                    timer.cancel();connection.close()
        except (OSError,ValueError,http.client.HTTPException):
            raise C0Error('source_transport_failed') from None
        raise C0Error('source_redirect_limit')
