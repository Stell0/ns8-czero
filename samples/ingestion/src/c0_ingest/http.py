# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""HTTPS requests never forward credentials through redirects."""
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_url(request, *, timeout=30):
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)
