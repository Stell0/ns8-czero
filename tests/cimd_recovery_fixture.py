# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable native recovery of Core-seeded CIMD state, not HTTPS-fetch proof."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode
from uuid import uuid4

from oidc_fixture import STATE, task
from oidc_probe import Browser
from oauth_fixture import issue

CONTROL_CODE = '''import json,sys
from sqlalchemy import text
from czero_core.database import Database
from czero_core.cimd import CimdService
from czero_core.cimd_metadata import parse_metadata
from czero_app.auth import AppAuth
request=json.load(sys.stdin);database=Database()
try:
 auth=AppAuth.from_env(database,'')
 assert auth is not None,'Native fixture authentication unavailable'
 session=auth.sessions.get(request['cookie'])
 assert str(session.actor.user_id)==request['profile_id'],'Native fixture identity changed'
 service=CimdService(auth.access)
 assert service.enabled(),'Native CIMD policy did not persist'
 metadata=parse_metadata(request['metadata_url'],json.dumps(request['document']).encode())
 if request['operation']=='seed':
  service.approve(session.actor,metadata,expected_digest=metadata.digest,cache_seconds=300)
 rows=service.status(session.actor)['clients']
 row=next(v for v in rows if v['metadata_url']==metadata.client_id)
 assert row['enabled'] and not row['review_required'],'Approved CIMD state changed'
 assert row['metadata_digest']==metadata.digest,'Approved CIMD metadata changed'
 if request['operation']=='observe':
  # Trusted fixture cache revalidation only. Real network validation is covered
  # by the controlled HTTPS tests and dedicated live acceptance, separately.
  service.observe(metadata,expected_revision=row['revision'],cache_seconds=300)
 assert service.clients._lookup(str(row['client_id'])) is None,'CIMD UUID alias accepted'
 assert service.clients._lookup(metadata.client_id)['registration_kind']=='cimd'
 stable={key:row[key] for key in ('client_id','metadata_url','client_name','enabled','revision',
     'allowed_scopes','metadata_digest','approved_descriptor','review_required')}
 if request['operation']=='deadline':
  with auth.access.database.engine.connect() as connection:
   deadline=connection.execute(text('SELECT extract(epoch FROM min(expires_at)) FROM c0_oauth_grants WHERE client_id=:id AND account_id=:actor'),
       {'id':row['client_id'],'actor':session.actor.user_id}).scalar_one()
  assert deadline is not None,'Native CIMD grant deadline missing'
  stable={'grant_expires_at':float(deadline)}
 print(json.dumps(stable,default=str))
finally:database.close()
'''


def control(module_id, operation, browser, profile, document):
    assert re.fullmatch(r'czero[0-9]+', module_id)
    cookies = [value.value for value in browser.cookies if value.name == 'c0_session']
    assert len(cookies) == 1, 'Native CIMD fixture session missing'
    payload = {'operation': operation, 'cookie': cookies[0], 'profile_id': profile['id'],
               'metadata_url': document['client_id'], 'document': document}
    result = subprocess.run(['runagent', '-m', module_id, 'podman', 'exec', '-i', 'czero',
        'python', '-c', CONTROL_CODE], input=json.dumps(payload).encode(), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=90)
    assert result.returncode == 0, 'Native CIMD Core fixture failed'
    return json.loads(result.stdout)


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value))
    temporary.chmod(0o600)
    temporary.replace(path)


def request_pair(browser, pair, expected_id=None):
    status, body, _ = browser.request('/api/v1/profile', headers={'Authorization': 'Bearer ' + pair['access_token']})
    if status == 200 and expected_id is not None:
        assert json.loads(body)['id'] == expected_id, 'Native CIMD profile identity changed'
    return status


def seed(module_id, browser, profile, *, directory=STATE, control_fn=control):
    path = directory / 'expected-cimd-recovery.json'
    assert not path.exists(), 'CIMD recovery fixture already exists'
    public_id = 'https://client.example.test/recovery/' + uuid4().hex + '.json'
    document = {'client_id': public_id, 'client_name': 'Disposable Core-seeded CIMD recovery',
        'redirect_uris': ['http://127.0.0.1:8765/callback'], 'token_endpoint_auth_method': 'none',
        'grant_types': ['authorization_code', 'refresh_token'], 'response_types': ['code'], 'scope': 'c0:read'}
    approval = control_fn(module_id, 'seed', browser, profile, document)
    public = {'client_id': public_id, 'redirect_uris': document['redirect_uris']}
    pair = issue(browser, profile, public)
    assert pair['expires_in'] > 180, 'Insufficient native CIMD token window'
    assert request_pair(browser, pair, profile['id']) == 200, 'Native CIMD delegated profile failed'
    approval = control_fn(module_id, 'inspect', browser, profile, document)
    deadline = control_fn(module_id, 'deadline', browser, profile, document)['grant_expires_at']
    assert deadline > time.time() + 180, 'Insufficient native CIMD grant window'
    save(path, {'module_id': module_id, 'profile_id': profile['id'], 'document': document,
                'grant_expires_at': deadline,
                'approval': approval, 'public_client': public, 'pair': pair})
    return {'stage': 'seed', 'approval_preserved': True, 'policy_enabled': True,
            'core_seeded': True, 'network_fetch_tested': False}


def verify(module_id, browser, profile, *, directory=STATE, control_fn=control):
    path = directory / 'expected-cimd-recovery.json'
    state = json.loads(path.read_text())
    assert profile['id'] == state['profile_id'], 'Native CIMD account identity changed'
    approval = control_fn(module_id, 'inspect', browser, profile, state['document'])
    assert approval == state['approval'], 'Native CIMD approval was not preserved exactly'
    restored = module_id != state['module_id']
    if not restored:
        status, body, _ = browser.request('/oauth/token', urlencode({'grant_type': 'refresh_token',
            'client_id': state['document']['client_id'], 'refresh_token': state['pair']['refresh_token'],
            'resource': browser.origin + '/mcp'}).encode(), 'POST', {'Content-Type': 'application/x-www-form-urlencoded'})
        assert status == 200, 'Native update lost CIMD refresh authority'
        current = json.loads(body)
        assert current['expires_in'] > 180 and current['scope'] == state['pair']['scope'], 'CIMD renewal bounds or scopes changed'
        assert current['refresh_token'] != state['pair']['refresh_token'], 'CIMD refresh did not rotate'
        assert request_pair(browser, current, profile['id']) == 200, 'Native update lost CIMD profile access'
        deadline = control_fn(module_id, 'deadline', browser, profile, state['document'])['grant_expires_at']
        assert deadline == state['grant_expires_at'] and deadline > time.time() + 180, 'CIMD grant deadline changed or expired'
        state['pair'] = current
        save(path, state)
        proof = {'stage': 'update', 'existing_authority_retained': True, 'refresh_rotated': True, 'absolute_bound_preserved': True}
    else:
        assert state['grant_expires_at'] > time.time(), 'CIMD recovery grant expired before native binding assertion'
        assert request_pair(browser, state['pair']) == 401, 'Clean restore retained old CIMD access'
        status, _, _ = browser.request('/oauth/token', urlencode({'grant_type': 'refresh_token',
            'client_id': state['document']['client_id'], 'refresh_token': state['pair']['refresh_token'],
            'resource': browser.origin + '/mcp'}).encode(), 'POST', {'Content-Type': 'application/x-www-form-urlencoded'})
        assert status == 400, 'Clean restore retained old CIMD refresh authority'
        control_fn(module_id, 'observe', browser, profile, state['document'])
        fresh = issue(browser, profile, state['public_client'])
        assert request_pair(browser, fresh, profile['id']) == 200, 'Fresh CIMD consent failed after restore'
        status, _, _ = browser.api('/api/v1/oauth/clients/' + approval['client_id'],
            {'enabled': False, 'expected_revision': approval['revision']}, 'PUT', profile['csrf_token'])
        assert status == 200 and request_pair(browser, fresh) == 401, 'Native CIMD cleanup did not revoke authority'
        proof = {'stage': 'restore', 'old_authority_rejected': True, 'old_grant_unexpired': True, 'fresh_consent': True, 'client_disabled': True}
    return {**proof, 'approval_preserved': True, 'policy_enabled': True,
            'core_seeded': True, 'network_fetch_tested': False}


def main(module_id, operation):
    assert os.geteuid() == 0 and re.fullmatch(r'czero[0-9]+', module_id)
    assert operation in ('seed', 'verify')
    personas = json.loads((STATE / 'personas.json').read_text())
    host = personas['host']
    assert host.endswith('.test'), 'CIMD recovery is confined to disposable hosts'
    if operation == 'seed':
        task('module/' + module_id + '/configure-module', {'host': host, 'cimd_enabled': True})
    config = task('module/' + module_id + '/get-configuration', {})
    assert config['cimd_enabled'] is True, 'Native CIMD switch did not survive update/restore'
    browser = Browser('https://' + host)
    profile = browser.login('c0owner', personas['password'])
    result = seed(module_id, browser, profile) if operation == 'seed' else verify(module_id, browser, profile)
    if result['stage'] == 'restore':
        task('module/' + module_id + '/configure-module', {'host': host, 'cimd_enabled': False})
        assert task('module/' + module_id + '/get-configuration', {})['cimd_enabled'] is False
        status, body, _ = browser.api('/api/v1/oauth/cimd')
        assert status == 200 and json.loads(body)['enabled'] is False, 'Native CIMD cleanup policy remained on'
        result['policy_disabled'] = True
    print('C0 CIMD recovery: ' + json.dumps(result))


if __name__ == '__main__':
    try:
        main(*sys.argv[1:])
    except Exception as error:
        print(str(error) if isinstance(error, AssertionError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
