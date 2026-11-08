# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Application-owned resources close even when an earlier cleanup fails."""
import asyncio
import os

import pytest

from czero_core.cimd import CimdPolicyService
from test_auth_http import application

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.mark.parametrize('startup_fails', [False, True])
def test_identity_close_failure_still_disposes_database(application, monkeypatch, startup_fails):
    app, _, _, _, database, _ = application
    closed = []
    dispose = database.close

    def close_database():
        dispose()
        closed.append('database')

    def close_identity():
        closed.append('identity')
        raise RuntimeError('synthetic identity close failure')

    def sync_policy(*args):
        if startup_fails:
            raise RuntimeError('synthetic startup failure')

    monkeypatch.setattr(database, 'close', close_database)
    monkeypatch.setattr(app.state.auth.oidc, 'close', close_identity)
    monkeypatch.setattr(CimdPolicyService, 'sync_policy', sync_policy)

    async def check():
        with pytest.raises(RuntimeError, match='identity close failure'):
            async with app.router.lifespan_context(app):
                assert not startup_fails
        assert closed == ['identity', 'database']

    asyncio.run(check())
