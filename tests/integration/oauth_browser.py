# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Drive first-party form submissions in the tab selected by the latest redirect."""
from urllib.parse import parse_qs, urlsplit

from httpx import AsyncClient


class OAuthBrowser(AsyncClient):
    flow = None
    stage = None

    @property
    def binding_cookie(self):
        return '__Host-c0-flow-' + self.flow

    def form_url(self, path):
        return f'{path}?flow={self.flow}' if self.flow else path

    def signin_url(self):
        return self.form_url('/auth/login') + '&stage=' + self.stage if self.flow else '/auth/login'

    async def request(self, method, url, **kwargs):
        path = urlsplit(str(url)).path
        if self.flow and '?' not in str(url):
            if path.startswith(('/oauth/connect', '/oauth/consent')):
                url = self.form_url(str(url))
            elif path == '/auth/login' and kwargs.get('params') is None:
                url = self.signin_url()
        response = await super().request(method, url, **kwargs)
        if path == '/oauth/authorize' and response.status_code == 302:
            target = urlsplit(response.headers['location'])
            if target.path in ('/oauth/connect','/oauth/consent'):
                self.stage = target.path.split('/')[-1]
                self.flow = parse_qs(target.query).get('flow', [None])[0]
        if path == '/oauth/consent/background' and response.status_code == 200:
            self.stage = 'background'
        if path == '/auth/logout' and response.is_success:
            self.flow = self.stage = None
        return response
