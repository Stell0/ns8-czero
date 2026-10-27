# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4
import pytest
from czero_core.identity import PermissionDenied
from czero_core.project_exports import KINDS
from test_access import access,identity,record_unadmitted,account_named
from test_projects import project,topic
from test_sources import sources
from test_project_evidence import evidence,page


def test_export_pagination_history_fragments_and_explicit_exclusions(evidence):
    service,owner,_,knowledge,source,_=evidence
    one=page(evidence,'# Original\n\nMarkdown stays separate from metadata.')
    knowledge.update_page(owner,one['id'],'Revised','# Changed\n\nActual new revision.',metadata={},expected_revision=1,idempotency_key='edit')
    second=page(evidence,'# Other page')
    first=service.export_page(owner,'wiki_pages',limit=1)
    assert len(first['rows'])==1 and first['next_cursor']
    following=service.export_page(owner,'wiki_pages',limit=1,after=first['next_cursor'])
    assert {row['id'] for row in first['rows']+following['rows']}=={one['id'],second['id']} and not following['next_cursor']
    revisions=service.export_page(owner,'wiki_revisions')['rows'];assert len(revisions)==3 and all('body' not in row for row in revisions)
    content=service.export_page(owner,'wiki_text',resource_id=one['content']['id'])['rows'][0]
    assert content['body'].startswith('# Original') and content['end_char']==content['total_chars']
    version,_=source('A'*50000+'é'*30000)
    document=next(row for row in service.export_page(owner,'documents')['rows'] if row['version_id']==str(version['id']))
    body='';cursor=''
    while True:
        chunk=service.export_page(owner,'document_text',resource_id=document['id'],after=cursor)
        part=chunk['rows'][0];assert part['start_char']==len(body)
        body+=part['body'];cursor=chunk['next_cursor']
        if not cursor:break
    import hashlib
    assert hashlib.sha256(body.encode()).hexdigest()==document['text_hash'] and len(body)==document['body_chars']
    for kind in KINDS:
        if kind.endswith('_text'):continue
        assert service.export_page(owner,kind)['project_id']==str(service._space_id)
    for forbidden in ('sessions','oauth_grants','jobs','memberships','../../private'):
        with pytest.raises(ValueError):service.export_page(owner,forbidden)
    assert not any('path' in key for row in service.export_page(owner,'source_versions')['rows'] for key in row)


def test_export_foreign_space_identity_cursor_and_current_access_fail_closed(project):
    service,manifest,owner,create=project
    service.initialize(owner,manifest,authorization_ref='synthetic:export',idempotency_key='init');topic(service,owner)
    other,other_manifest=create();other.initialize(owner,other_manifest,authorization_ref='synthetic:other',idempotency_key='other');topic(other,owner)
    first=service.export_page(owner,'objects',limit=1)
    with pytest.raises(ValueError):other.export_page(owner,'objects',after=first['next_cursor'])
    with pytest.raises(ValueError):service.export_page(owner,'sources',after=first['next_cursor'])
    with pytest.raises(ValueError):service.export_page(owner,'document_text',resource_id=str(uuid4()))
    from czero_core.identity import Role
    from czero_core.spaces import SpaceService
    accounts=service.access;key=uuid4();record_unadmitted(accounts,key,'export-reader')
    account=account_named(accounts,owner,'export-reader');accounts.set_role(owner,account['id'],Role.READER)
    actor=accounts.resolve(identity(accounts,key,'export-reader'));spaces=SpaceService(service.database,accounts)
    spaces.set_grant(owner,manifest['space_id'],actor.user_id,Role.READER,expected_revision=0,idempotency_key='grant-reader')
    assert service.export_page(actor,'objects')['rows']
    with pytest.raises(PermissionDenied):other.export_page(actor,'objects')
    spaces.set_grant(owner,manifest['space_id'],actor.user_id,None,expected_revision=1,idempotency_key='revoke-reader')
    with pytest.raises(PermissionDenied):service.export_page(actor,'objects',after=first['next_cursor'])
