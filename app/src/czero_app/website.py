# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Local compiled website assets; no API or OAuth catch-all fallback."""
import json
import re
from html import escape
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse


CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
       "img-src 'self'; connect-src 'self'; worker-src 'self'; base-uri 'self'; "
       "frame-ancestors 'none'")


class Website:
    def __init__(self, directory: Path, base_path: str):
        self.directory = directory
        self.base_path = base_path

    def render(self, boot=None, *, status_code=200):
        path = self.directory / 'index.html'
        if not path.is_file():
            raise HTTPException(503, 'website_build_unavailable')
        value = json.dumps(boot or {}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        body = path.read_text().replace('<base href="/" />', '<base href="' + escape(self.base_path + '/', quote=True) + '" />')
        body = body.replace('<!--C0_BOOT-->', '<script id="c0-boot" type="application/json">' + value + '</script>')
        return HTMLResponse(body, status_code=status_code, headers={'Cache-Control': 'no-store', 'Content-Security-Policy': CSP,
            'Referrer-Policy': 'strict-origin', 'X-Content-Type-Options': 'nosniff'})

    def install(self, app):
        def page():
            return self.render()

        for path in ('/', '/search', '/wiki', '/wiki/{identifier}', '/sources', '/sources/{identifier}',
                     '/evidence/{identifier}', '/tables', '/tables/{identifier}', '/projects', '/explore', '/explore/{kind}', '/explore/{kind}/{identifier}',
                     '/account', '/agents', '/admin', '/admin/spaces', '/admin/advanced', '/admin/work'):
            app.add_api_route(path, page, methods=['GET'], include_in_schema=False)

        @app.get('/assets/{filename}', include_in_schema=False)
        def asset(filename: str):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:js|css|woff2)', filename):
                raise HTTPException(404)
            path = self.directory / 'assets' / filename
            if not path.is_file() or path.is_symlink():
                raise HTTPException(404)
            media = {'.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2'}[path.suffix]
            return FileResponse(path, media_type=media, headers={'Cache-Control': 'public, max-age=31536000, immutable',
                'X-Content-Type-Options': 'nosniff'})

        @app.get('/markdown-worker.js', include_in_schema=False)
        def worker():
            path = self.directory / 'markdown-worker.js'
            if not path.is_file() or path.is_symlink():
                raise HTTPException(404)
            return FileResponse(path, media_type='text/javascript',
                headers={'Content-Security-Policy': CSP, 'X-Content-Type-Options': 'nosniff'})

        @app.get('/vendor/{filename}', include_in_schema=False)
        def vendor(filename: str):
            allowed = {'markdown-it-15.0.2.min.js', 'markdown-it-LICENSE', 'poppins-LICENSE',
                       'poppins-latin-400-normal.woff2', 'poppins-latin-500-normal.woff2', 'third-party-notices.txt'}
            if filename not in allowed:
                raise HTTPException(404)
            path = self.directory / 'vendor' / filename
            if not path.is_file() or path.is_symlink():
                raise HTTPException(404)
            media = {'.js': 'text/javascript', '.woff2': 'font/woff2'}.get(path.suffix, 'text/plain')
            return FileResponse(path, media_type=media, headers={'X-Content-Type-Options': 'nosniff'})
