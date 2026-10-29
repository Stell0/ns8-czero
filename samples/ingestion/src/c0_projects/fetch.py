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
import time
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
    def __init__(self, config, *, accept_json=False):
        if type(accept_json) is not bool:raise C0Error('invalid_response_selection')
        self.config=config
        self.requests=0
        self.downloaded=0
        self._connections={}
        self._last={}
        self.accept='application/json' if accept_json else 'text/*, application/xml, application/rss+xml, application/atom+xml, application/pdf'

    def get(self, url):
        content,canonical,media,_=self.response(url)
        return content,canonical,media

    def close(self):
        for connection,_ in self._connections.values():connection.close()
        self._connections.clear()

    def response(self,url,*,headers=None,allow_status=(200,),validate_url=None,interval=0,remaining_bytes=None):
        initial=urlsplit(public_url(url))
        try:
            for redirect in range(4):
                parsed=urlsplit(public_url(url))
                if validate_url:validate_url(url)
                if (not validate_url and parsed.hostname.lower()!=initial.hostname.lower()) or (initial.scheme=='https' and parsed.scheme!='https'):
                    raise C0Error('source_cross_host_redirect_denied')
                if self.requests>=self.config['max_requests']:
                    raise C0Error('source_request_budget_exhausted')
                port=443 if parsed.scheme=='https' else 80
                peers=public_addresses(parsed.hostname,port,self.config['timeout'])
                origin=(parsed.scheme,parsed.hostname,port)
                cached=self._connections.get(origin)
                if cached and cached[1] not in peers:
                    cached[0].close();cached=None
                if cached:connection=cached[0]
                else:
                    connection=(http.client.HTTPSConnection(parsed.hostname,port,timeout=self.config['timeout'],context=ssl.create_default_context())
                        if parsed.scheme=='https' else http.client.HTTPConnection(parsed.hostname,port,timeout=self.config['timeout']))
                    connection._create_connection=lambda address,timeout,*args: socket.create_connection((peers[0],port),timeout)
                    self._connections[origin]=(connection,peers[0])
                wait=interval-(time.monotonic()-self._last.get(origin,0))
                if wait>0:time.sleep(min(wait,60))
                self._last[origin]=time.monotonic()
                self.requests+=1
                def expire(current=connection):
                    try:
                        if current.sock: current.sock.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    current.close()
                timer=Timer(self.config['timeout'],expire);timer.daemon=True;timer.start()
                success=False
                try:
                    connection.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),
                        headers={'User-Agent':'c0-projects/0.3','Accept':self.accept,**(headers or {})})
                    response=connection.getresponse()
                    if response.status in (301,302,303,307,308):
                        if redirect==3 or not response.getheader('Location'):
                            raise C0Error('source_redirect_limit')
                        url=urljoin(url,response.getheader('Location'))
                        connection.close();self._connections.pop(origin,None)
                        continue
                    if response.status not in allow_status:
                        raise FetchError('source_http_' + str(response.status),retry_time(response.getheader('Retry-After')))
                    limit=self.config['max_bytes'] if remaining_bytes is None else min(self.config['max_bytes'],remaining_bytes)
                    declared=response.getheader('Content-Length') if response.status!=304 else None
                    if declared is not None and (not declared.isdigit() or int(declared)>limit):
                        raise C0Error('source_content_length_invalid_or_too_large')
                    content=response.read(limit+1)
                    if len(content)>limit:
                        raise C0Error('source_content_too_large')
                    if declared is not None and len(content)!=int(declared):
                        raise C0Error('source_incomplete_body')
                    if response.getheader('Content-Encoding','identity')!='identity':
                        raise C0Error('source_encoding_unsupported')
                    self.downloaded+=len(content)
                    success=True
                    return content,url,response.getheader('Content-Type','text/plain').split(';')[0].strip().lower(),{
                        'status':response.status,'etag':response.getheader('ETag',''),
                        'last_modified':response.getheader('Last-Modified',''),'retry_after':retry_time(response.getheader('Retry-After'))}
                finally:
                    timer.cancel()
                    if not success:
                        connection.close();self._connections.pop(origin,None)
        except (OSError,ValueError,http.client.HTTPException):
            self.close()
            raise C0Error('source_transport_failed') from None
        raise C0Error('source_redirect_limit')
