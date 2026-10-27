# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual PostgreSQL project authorization, history and concurrent mutations."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from czero_core.identity import PermissionDenied, Role
from czero_core.objects import ObjectService
from czero_core.projects import ProjectService, ProjectConflict
from czero_core.project_schema import PREFIX, normalize_manifest
from czero_core.spaces import SpaceService
from test_access import access, identity, record_unadmitted, account_named

pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


@pytest.fixture
def project(access):
    accounts, database, key = access
    owner = accounts.resolve(identity(accounts, key))
    spaces = SpaceService(database, accounts)
    owned = []
    def create():
        space = spaces.create(owner, 'Synthetic-' + uuid4().hex, idempotency_key=uuid4().hex)
        owned.append(UUID(space['id']))
        service = ProjectService(database, accounts, clock=lambda: datetime(2026, 10, 25, 7, tzinfo=timezone.utc)).in_space(space['id'])
        manifest = normalize_manifest({'project_id': space['id'], 'space_id': space['id'],
            'name': 'Synthetic research', 'purpose': 'Test research', 'scope': 'Fabricated safe fixtures only'})
        return service, manifest
    service, manifest = create()
    yield service, manifest, owner, create
    with database.engine.begin() as connection:
        for space in owned:
            for table in ('c0_object_keys', 'c0_object_events', 'c0_objects', 'c0_knowledge_receipts', 'c0_space_grants', 'c0_space_cursors'):
                connection.execute(text('DELETE FROM ' + table + ' WHERE space_id=:space'), {'space': space})
            connection.execute(text("DELETE FROM c0_space_receipts WHERE result->>'id'=:id"), {'id': str(space)})
            connection.execute(text('DELETE FROM c0_spaces WHERE id=:id'), {'id': space})


def initialize(fixture):
    service, manifest, owner, _ = fixture
    return service.initialize(owner, manifest, authorization_ref='synthetic-user-turn:setup', idempotency_key='setup')


def topic(service, owner, identifier='anchor', **changes):
    values = {'topic_id': identifier, 'label': 'Same label', 'classification': 'user',
        'authorization_ref': 'synthetic-user-turn:track', **changes}
    return service.set_topic(owner, values, idempotency_key=uuid4().hex)


def test_initialize_replay_and_configuration_history(project):
    service, manifest, owner, _ = project
    first = initialize(project)
    assert initialize(project) == first
    with pytest.raises(ProjectConflict):
        service.initialize(owner, manifest, authorization_ref='another approval', idempotency_key='another-setup')
    changed = deepcopy(manifest); changed['description'] = 'Revision two'
    second = service.configure(owner, changed, expected_revision=first['revision'],
        authorization_ref='synthetic-user-turn:configure', idempotency_key='config2')
    assert second['revision'] == 2
    assert service.get(owner)['data']['manifest']['description'] == 'Revision two'
    history = service.list_records(owner, 'config_v1')
    assert [row['data']['version'] for row in history] == [1, 2]
    assert history[0]['data']['manifest']['description'] == ''
    with pytest.raises(ProjectConflict):
        service.configure(owner, manifest, expected_revision=1, authorization_ref='stale', idempotency_key='stale')


def test_protected_selection_current_grants_and_raw_record_guards(project):
    service, manifest, owner, create = project
    first = initialize(project)
    other, other_manifest = create()
    other.initialize(owner, other_manifest, authorization_ref='synthetic setup', idempotency_key='setup')
    assert service.get(owner)['data']['manifest']['space_id'] != other.get(owner)['data']['manifest']['space_id']
    a = topic(service, owner); b = topic(other, owner)
    assert a['id'] != b['id'] and a['data']['label'] == b['data']['label']
    accounts = service.access; key = uuid4()
    record_unadmitted(accounts, key, 'project-editor')
    account = account_named(accounts, owner, 'project-editor')
    accounts.set_role(owner, account['id'], Role.EDITOR)
    actor = accounts.resolve(identity(accounts, key, 'project-editor'))
    spaces = SpaceService(service.database, accounts)
    spaces.set_grant(owner, manifest['space_id'], actor.user_id, Role.EDITOR, expected_revision=0, idempotency_key='grant')
    assert service.get(actor)['id'] == first['id']
    with pytest.raises(PermissionDenied): other.get(actor)
    with pytest.raises(PermissionDenied):
        service.configure(actor, manifest, expected_revision=1, authorization_ref='forged approval', idempotency_key='denied')
    raw = ObjectService(service.database, accounts).in_space(manifest['space_id'])
    with pytest.raises(PermissionDenied):
        raw.update(owner, first['id'], first['data'], expected_revision=1)
    with pytest.raises(PermissionDenied):
        raw.delete(owner, first['id'], expected_revision=1)
    with pytest.raises(PermissionDenied):
        raw.create(owner, PREFIX + 'manifest_v1', first['data'])
    spaces.set_grant(owner, manifest['space_id'], actor.user_id, None, expected_revision=1, idempotency_key='revoke')
    with pytest.raises(PermissionDenied): service.get(actor)
    with pytest.raises(ValueError): ProjectService(service.database, accounts).get(owner)
    with pytest.raises(PermissionDenied):
        ProjectService(service.database, accounts).in_space(spaces.list(owner)['spaces'][0]['id']).get(owner)


def test_topics_have_direct_anchors_terminal_expiry_and_history(project):
    service, manifest, owner, _ = project
    initialize(project)
    topic(service, owner)
    adjacent = topic(service, owner, 'adjacent', classification='adjacent', anchor_ids=['anchor'],
        direct_contribution='Tests anchor constraints', assessment_ref='synthetic-assessment:1')
    with pytest.raises(ValueError):
        topic(service, owner, 'chain', classification='adjacent', anchor_ids=['adjacent'],
            direct_contribution='Via adjacent only', assessment_ref='assessment:2')
    peripheral = topic(service, owner, 'peripheral', classification='peripheral', anchor_ids=['anchor'],
        direct_contribution='Potentially relevant', assessment_ref='assessment:3')
    assert peripheral['data']['expires_at'] == '2026-10-25T08:00:00+00:00' # default UTC, future checkpoint
    with pytest.raises(ValueError): topic(service, owner, 'child', parent_ids=['peripheral'])
    values = {k: v for k, v in adjacent['data'].items() if k not in ('key', 'schema_version', 'authorized_by', 'created_at', 'expires_at')}
    values['lifecycle'] = 'archived'
    archived = service.set_topic(owner, values, expected_revision=1, idempotency_key='archive')
    values['lifecycle'] = 'active'
    with pytest.raises(ValueError): service.set_topic(owner, values, expected_revision=archived['revision'], idempotency_key='reactivate')


def test_concurrent_configuration_has_one_winner(project):
    service, manifest, owner, _ = project
    initialize(project)
    def change(index):
        try:
            return service.configure(owner, {**manifest, 'description': str(index)}, expected_revision=1,
                authorization_ref='synthetic approval', idempotency_key='concurrent:' + str(index))
        except ProjectConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(change, range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(service.list_records(owner, 'config_v1')) == 2


def test_primary_topic_cannot_be_retired_behind_configuration(project):
    service, manifest, owner, _ = project
    initialize(project)
    anchor = topic(service, owner)
    active = {**manifest, 'primary_topic_ids':['anchor'], 'state':{'initialized':True,'migration_status':'not_started'}}
    service.configure(owner, active, expected_revision=1, authorization_ref='synthetic setup', idempotency_key='activate')
    values = {'topic_id':'anchor','label':'Same label','classification':'user','lifecycle':'retired',
        'authorization_ref':'synthetic retirement request'}
    with pytest.raises(ValueError):
        service.set_topic(owner, values, expected_revision=anchor['revision'], idempotency_key='retire')
    assert service.list_records(owner,'topic_v1')[0]['data']['lifecycle'] == 'active'


def test_admin_configure_installs_additive_managed_schema_for_existing_project(project,monkeypatch):
    from czero_core.project_schema import SCHEMAS,record,string
    service,manifest,owner,_=project
    initialize(project)
    kind='fixture_upgrade_v1';name=PREFIX+kind
    monkeypatch.setitem(SCHEMAS,kind,record(key=string(128)))
    try:
        configured=service.configure(owner,manifest,expected_revision=1,authorization_ref='synthetic compatible feature upgrade',idempotency_key='upgrade-types')
        assert configured['data']['version']==2 and configured['data']['manifest']==manifest
        with service.database.engine.connect() as connection:
            schema=connection.execute(text('SELECT schema FROM c0_object_types WHERE name=:name'),{'name':name}).scalar_one()
            assert schema==SCHEMAS[kind]
    finally:
        with service.database.engine.begin() as connection:
            connection.execute(text('DELETE FROM c0_object_types WHERE name=:name'),{'name':name})
