# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable native profile checks; private identities never enter reports."""
import json
import os
import sys
from uuid import UUID

from oidc_fixture import STATE


def verify_profile(browser, me):
    status, body, _ = browser.api('/api/v1/profile')
    assert status == 200, 'Authenticated profile unavailable'
    value = json.loads(body)
    expected = {'id': me['id']}
    for source, target in (('display_name', 'name'), ('username', 'nickname')):
        label = me.get(source)
        if isinstance(label, str) and label.strip():
            expected[target] = label
    assert value == expected, 'Profile differs from verified account'
    assert str(UUID(value['id'])) == value['id'], 'Profile identity is not the persisted UUID'
    saved = STATE / 'predecessor-profiles.json'
    if saved.exists():
        predecessor = json.loads(saved.read_text())
        if me.get('username') in predecessor:
            assert value['id'] == predecessor[me['username']], 'Genuine predecessor profile identity changed'
    return value


def predecessor(stage):
    from oidc_probe import Browser
    assert stage in ('seed', 'verify'), 'Invalid predecessor profile stage'
    personas = json.loads((STATE / 'personas.json').read_text())
    assert personas['host'].endswith('.test'), 'Predecessor profile requires a disposable hostname'
    owner = Browser('https://' + personas['host'])
    me = owner.login('c0owner', personas['password'])
    member = Browser(owner.origin)
    saved = STATE / 'predecessor-profiles.json'
    if stage == 'seed':
        denied = Browser(owner.origin)
        denied.login('c0member', personas['password'], expected=403)
        status, body, _ = owner.api('/api/v1/access/accounts')
        assert status == 200, 'Cannot inspect predecessor accounts'
        account = next(row for row in json.loads(body)['accounts'] if row['username'] == 'c0member')
        status, _, _ = owner.api('/api/v1/access/accounts/' + account['id'], {'role':'reader'}, 'PUT', me['csrf_token'])
        assert status == 204, 'Cannot admit predecessor reader'
    current = member.login('c0member', personas['password'])
    assert me['id'] != current['id'], 'Distinct predecessor accounts share an identity'
    if stage == 'seed':
        old = os.umask(0o077)
        try:
            saved.write_text(json.dumps({'c0owner':me['id'], 'c0member':current['id']}))
        finally:
            os.umask(old)
        saved.chmod(0o600)
        # Seed only established /me identity; this works on genuine M17 too.
    else:
        verify_profile(owner, me)
        verify_profile(member, current)
    member.logout(current)
    if stage == 'verify':
        assert owner.api('/api/v1/access/accounts/' + current['id'], {'role':None}, 'PUT', me['csrf_token'])[0] == 204, 'Cannot restore unadmitted fixture account'
    owner.logout(me)


if __name__ == '__main__':
    try:
        predecessor(sys.argv[1])
        print('Disposable genuine predecessor profile identity checks passed')
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
