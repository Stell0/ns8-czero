# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import importlib.util
from pathlib import Path


def test_disposable_tcp_route_changes_only_application_destination():
    path=Path(__file__).resolve().parents[1]/'mcp_tls_probe.py'
    spec=importlib.util.spec_from_file_location('mcp_tls_fixture',path)
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    calls=[]
    class Backend:
        async def connect_tcp(self,host,port,**options):
            calls.append((host,port,options));return object()
    async def check():
        route=probe.ApplicationRoute('c0.example.test','10.0.2.2');route.backend=Backend()
        await route.connect_tcp('c0.example.test',443,timeout=5)
        await route.connect_tcp('idp.example.test',443,timeout=5)
    asyncio.run(check())
    assert calls==[('10.0.2.2',443,{'timeout':5}),('idp.example.test',443,{'timeout':5})]
