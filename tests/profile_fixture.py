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


def predecessor(stage, *, reader_admission=False):
    from oidc_probe import Browser
    assert stage in ('seed', 'verify'), 'Invalid predecessor profile stage'
    personas = json.loads((STATE / 'personas.json').read_text())
    assert personas['host'].endswith('.test'), 'Predecessor profile requires a disposable hostname'
    owner = Browser('https://' + personas['host'])
    me = owner.login('c0owner', personas['password'])
    member = Browser(owner.origin)
    saved = STATE / 'predecessor-profiles.json'
    if stage == 'seed' and not reader_admission:
        denied = Browser(owner.origin)
        denied.login('c0member', personas['password'], expected=403)
        status, body, _ = owner.api('/api/v1/access/accounts')
        assert status == 200, 'Cannot inspect predecessor accounts'
        account = next(row for row in json.loads(body)['accounts'] if row['username'] == 'c0member')
        status, _, _ = owner.api('/api/v1/access/accounts/' + account['id'], {'role':'reader'}, 'PUT', me['csrf_token'])
        assert status == 204, 'Cannot admit predecessor reader'
    current = member.login('c0member', personas['password'])
    if stage == 'seed' and reader_admission:
        assert current['role'] == 'reader' and current['is_owner'] is False, 'Predecessor default Reader admission differs'
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


def predecessor_background(module_id, stage):
    """Prove exact pre-migration background authority, then clean only its client."""
    from oidc_probe import Browser
    from oauth_fixture import seed_persistence, verify_persistence
    from persistent_fixture import issue, native
    assert stage in ('seed', 'verify')
    personas = json.loads((STATE / 'personas.json').read_text())
    assert personas['host'].endswith('.test'), 'Background predecessor requires a disposable hostname'
    browser = Browser('https://' + personas['host'])
    profile = browser.login('c0owner', personas['password'])
    filename = 'predecessor-background.json'
    def create(active, actor, client):
        return issue(active, actor, client, personas['password'], offline=True)[0]
    def read_profile(module, origin, pair):
        # An independent empty cookie jar proves delegated authority alone.
        delegated = Browser(origin)
        status, body, _ = delegated.request('/api/v1/profile',
            headers={'Authorization':'Bearer ' + pair['access_token']})
        assert status == 200 and json.loads(body)['id'] == profile['id'], 'Upgraded background read failed'
    if stage == 'seed':
        seed_persistence(module_id, browser, profile, issue_fn=create, filename=filename,
            client_name='Disposable genuine predecessor background connection')
    else:
        verify_persistence(module_id, browser, profile, filename=filename, sdk_fn=read_profile)
    value = json.loads((STATE / filename).read_text())
    assert len(value['rows']['grants']) == 1
    grant = value['rows']['grants'][0]
    assert grant['persistent'] is True and grant['expires_at'] is None and grant['native_authority_id']
    if stage == 'verify':
        # Exact-row comparison and successful rotating refresh have completed.
        client = value['client']
        assert browser.api('/api/v1/oauth/clients/' + client['client_id'],
            {'enabled':False, 'expected_revision':client['revision']}, 'PUT', profile['csrf_token'])[0] == 200
        assert Browser(browser.origin).request('/api/v1/profile',
            headers={'Authorization':'Bearer ' + value['pair']['access_token']})[0] == 401
        assert native(module_id, {'operation':'revoke', 'id':grant['native_authority_id']}) == {'provider_revoked':True}
    print('C0 predecessor background: ' + json.dumps({'stage':stage, 'verified':True}, sort_keys=True))


if __name__ == '__main__':
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('stage', choices=('seed','verify'))
        parser.add_argument('--reader-admission', action='store_true')
        parser.add_argument('--background-module')
        args = parser.parse_args()
        if args.background_module and args.stage == 'verify':
            predecessor_background(args.background_module, args.stage)
        predecessor(args.stage, reader_admission=args.reader_admission)
        if args.background_module and args.stage == 'seed':
            predecessor_background(args.background_module, args.stage)
        print('Disposable genuine predecessor profile identity checks passed')
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
