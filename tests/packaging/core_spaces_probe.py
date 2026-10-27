# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted, owned Core fixtures for disposable installations only; no live SSO claim."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from uuid import UUID, uuid4

from sqlalchemy import text
from czero_core import Database
from czero_core.access import AccessService
from czero_core.annotations import AnnotationService, ContentTarget
from czero_core.bundles import KnowledgeBundleService
from czero_core.identity import PermissionDenied, Role, VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.knowledge import KnowledgeService
from czero_core.objects import ObjectService, ObjectNotFound
from czero_core.projects import ProjectService
from czero_core.oauth_clients import OAuthClientService
from czero_core.oauth_grants import OAuthGrantService, GrantRejected, pkce_challenge
from czero_core.sessions import SessionContext
from czero_core.sources import OriginalStore, SourceService, SourceNotFound, register_source_handlers
from czero_core.spaces import SpaceService
from czero_core.structured import StructuredFilters, StructuredSearchService
from czero_core.wiki import KnowledgeConflict, KnowledgeNotFound

assert os.environ.get('CZERO_DISPOSABLE_TEST') == '1', 'Disposable fixture marker required'
database = Database()
issuer = 'https://fixture.example.invalid/' + uuid4().hex
owner_key, editor_key = uuid4(), uuid4()
access = AccessService(database, issuer, owner_key)
owner = access.resolve(VerifiedIdentity(issuer,'owner',str(owner_key),'owner','Owner',time.time()+600))
spaces = SpaceService(database, access)
created, type_name, client_id = [], 'space-fixture-' + uuid4().hex, None
try:
    private = spaces.create(owner,'Private fixture '+uuid4().hex,idempotency_key='private')
    created.append(UUID(private['id']))
    other = spaces.create(owner,'Other fixture '+uuid4().hex,idempotency_key='other')
    created.append(UUID(other['id']))
    knowledge = KnowledgeService(database,access)
    selected = knowledge.in_space(private['id'])
    first = selected.upsert_page(owner,'same-slug','Private fixture','Unverified observation',idempotency_key='same-key')
    second = knowledge.in_space(other['id']).upsert_page(owner,'same-slug','Other fixture','Other observation',idempotency_key='same-key')
    assert first['id'] != second['id']
    assert selected.upsert_page(owner,'same-slug','Private fixture','Unverified observation',idempotency_key='same-key') == first
    try:knowledge.get_page(owner,first['id'])
    except KnowledgeNotFound:pass
    else:raise AssertionError('Shared page lookup crossed spaces')
    entity = selected.create_entity(owner,'investigation','Private fixture entity',idempotency_key='entity')
    with tempfile.TemporaryDirectory(prefix='core-spaces-') as directory:
        originals = OriginalStore(Path(directory)/'originals')
        registry = default_registry(); register_source_handlers(registry,database,originals)
        sources = SourceService(database,access,registry,originals)
        source = sources.in_space(private['id'])
        receipt = source.ingest_text(owner,title='Private evidence',body='Retained fixture evidence',idempotency_key='evidence')
        with database.engine.begin() as c:registry.get('source.extract').execute(c,{'version_id':receipt['id']})
        document = source.document(owner,receipt['id']); chunk = source.chunks(owner,document['id'])[0]
        assert source.citation(owner,chunk['id'])['body'] == 'Retained fixture evidence'
        try:sources.citation(owner,chunk['id'])
        except SourceNotFound:pass
        else:raise AssertionError('Shared citation lookup crossed spaces')
        claim = selected.create_claim(owner,entity['id'],'observed',{'unknown':True},page_id=first['id'],evidence_chunk_ids=[str(chunk['id'])],idempotency_key='claim')
        assert selected.get_claim(owner,claim['id'])['evidence'][0]['chunk_id'] == str(chunk['id'])
        objects = ObjectService(database,access,reference_resolvers={**knowledge.reference_resolvers(),**sources.reference_resolvers()})
        objects.register_type(owner,type_name,'Fixture',{'type':'object','properties':{'name':{'type':'string','maxLength':64}},'required':['name']},['name'])
        record = objects.in_space(private['id']).create(owner,type_name,{'name':'Same unique value'})
        objects.in_space(other['id']).create(owner,type_name,{'name':'Same unique value'})
        project=ProjectService(database,access).in_space(private['id'])
        manifest={'project_id':private['id'],'space_id':private['id'],'name':'Packaged synthetic project',
            'purpose':'Verify independent project persistence','scope':'Fabricated package evidence only'}
        initialized=project.initialize(owner,manifest,authorization_ref='synthetic:package-setup',idempotency_key='project')
        assert project.initialize(owner,manifest,authorization_ref='synthetic:package-setup',idempotency_key='project')==initialized
        project.set_topic(owner,{'topic_id':'package-anchor','label':'Synthetic package anchor','classification':'user',
            'authorization_ref':'synthetic:user-track'},idempotency_key='package-topic')
        stored=project.get(owner)
        assert stored['id']==initialized['id'] and stored['data']==initialized['data']
        before=project.export_page(owner,'objects')['rows']
        subprocess.run([sys.executable,'-I','-m','czero_core.migrate'],check=True,capture_output=True,timeout=60)
        assert project.get(owner)==stored and project.export_page(owner,'objects')['rows']==before
        assert project.export_page(owner,'wiki_text',resource_id=first['content']['id'])['rows'][0]['body']==first['content']['body']
        assert str(chunk['id']) in {row['id'] for row in project.export_page(owner,'chunks')['rows']}
        assert claim['id'] in {row['id'] for row in project.export_page(owner,'claims')['rows']}
        annotations = AnnotationService(database,access).in_space(private['id'])
        targets = [ContentTarget('source_version',receipt['id'],receipt['number']),
                   ContentTarget('wiki_revision',first['content']['id'],first['revision']),
                   ContentTarget('entity',entity['id'],entity['revision']),
                   ContentTarget('object',record['id'],record['revision']),
                   ContentTarget('claim',claim['id'],claim['revision'])]
        for index,target in enumerate(targets):
            assert annotations.get(owner,target,'verification')['status']=='unknown'
            annotations.update(owner,target,'applicability',{'products':['C0'],'version_tags':['0.28'],'status':'applicable'},
                expected_revision=0,idempotency_key='applicable-'+str(index))
            annotations.update(owner,target,'verification',{'status':'unverified'},
                expected_revision=0,idempotency_key='verify-'+str(index))
        target=targets[1]
        old=annotations.get(owner,target,'verification')
        annotations.update(owner,target,'verification',{'status':'verified'},expected_revision=1,idempotency_key='verified')
        assert annotations.update(owner,target,'verification',{'status':'unverified'},expected_revision=0,idempotency_key='verify-1')==old
        assert [r['number'] for r in annotations.history(owner,target,'verification')['revisions']]==[2,1]
        assert annotations.get(owner,target,'applicability')['revision']==1
        assert selected.get_page(owner,first['id'])==first
        try:AnnotationService(database,access).get(owner,target,'verification')
        except KnowledgeNotFound:pass
        else:raise AssertionError('Shared annotation lookup crossed spaces')
        structured = StructuredSearchService(database,access).in_space(private['id'])
        for target,category,query in zip(targets,['source','wiki','entity','object','claim'],
                                       ['Retained','Unverified','fixture','Same','unknown'],strict=True):
            result=structured.search(owner,query,filters=StructuredFilters(categories=[category],
                products=['C0'],version_tags=['0.28']))
            assert result['candidate_count']==1 and len(result['hits'])==1
            assert result['hits'][0]['reference']['id']==str(target.id)
            assert result['hits'][0]['reference']['revision']==target.revision
        assert structured.search(owner,'Unverified',filters=StructuredFilters(version_tags=['0.2']))['hits']==[]
        target=targets[1]
        assert objects.in_space(private['id']).resolve_reference(owner,'chunk',chunk['id'],'chunk')['data']['body'] == 'Retained fixture evidence'
        try:objects.get(owner,record['id'])
        except ObjectNotFound:pass
        else:raise AssertionError('Shared object lookup crossed spaces')
        bundles=KnowledgeBundleService(database,access).in_space(private['id'])
        operations=[
            {'operation':'wiki.upsert','arguments':{'slug':'consolidated','title':'Consolidated','body':'Retained consolidation'}},
            {'operation':'object.create','arguments':{'type_name':type_name,'data':{'name':'Consolidated record'}}},
            {'operation':'annotation.update','arguments':{
                'target':{'kind':'wiki_revision','id':{'$result':0,'path':'content.id'},'revision':1},
                'namespace':'applicability','expected_revision':0,
                'value':{'knowledge_type':'procedure','status':'applicable','confidence':None,
                    'supersedes':[{'kind':target.kind,'id':str(target.id),'revision':target.revision}],
                    'source_references':[{'kind':'chunk','id':str(chunk['id'])}]}}}]
        consolidated=bundles.apply(owner,operations,idempotency_key='consolidation')
        assert len(consolidated['results'])==3
        assert consolidated['results'][2]['value']['knowledge_type']=='procedure'
        assert consolidated['results'][2]['value']['source_references']==[{'kind':'chunk','id':str(chunk['id'])}]
        assert selected.get_page(owner,first['id'])==first
        assert annotations.get(owner,target,'verification')['status']=='verified'
        assert bundles.apply(owner,operations,idempotency_key='consolidation')==consolidated
        failed=[{'operation':'wiki.upsert','arguments':{'slug':'rolled-back','title':'Never','body':'Never'}},
                {'operation':'object.update','arguments':{'object_id':str(record['id']),'data':{'name':'Never'},'expected_revision':999}}]
        try:bundles.apply(owner,failed,idempotency_key='rolled-back')
        except KnowledgeConflict:pass
        else:raise AssertionError('Stale multi-resource write succeeded')
        try:selected.resolve_page(owner,'rolled-back')
        except KnowledgeNotFound:pass
        else:raise AssertionError('Failed bundle partially published')
        assert objects.in_space(private['id']).get(owner,record['id'])['revision']==1
        try:access.resolve(VerifiedIdentity(issuer,'editor',str(editor_key),'editor','Editor',time.time()+600))
        except PermissionDenied:pass
        account = next(row for row in access.list_accounts(owner) if row['account_key'] == editor_key)
        access.set_role(owner,account['id'],Role.EDITOR)
        editor = access.resolve(VerifiedIdentity(issuer,'editor',str(editor_key),'editor','Editor',time.time()+600))
        spaces.set_grant(owner,private['id'],editor.user_id,Role.EDITOR,expected_revision=0,idempotency_key='grant')
        callback, resource = 'https://fixture.example.invalid/callback','https://fixture.example.invalid/mcp'
        client = OAuthClientService(access).register(owner,'Space probe '+uuid4().hex,[callback],scopes=['c0:read','c0:write'])
        client_id = UUID(client['client_id'])
        tokens = OAuthGrantService(access,'disposable-space-probe',resource)
        verifier = secrets.token_urlsafe(32)
        code = tokens.issue_code(SessionContext(editor,datetime.fromtimestamp(time.time()+600,timezone.utc),'fixture-csrf'),client['client_id'],callback=callback,scopes={'c0:read','c0:write'},challenge=pkce_challenge(verifier),resource=resource)
        pair = tokens.exchange_code(code,client['client_id'],callback=callback,verifier=verifier,resource=resource)
        delegated = tokens.verify(pair.access_token,resource=resource).actor
        assert selected.get_page(delegated,first['id']) == first
        assert project.export_page(delegated,'objects')['rows']==project.export_page(owner,'objects')['rows']
        assert annotations.get(delegated,target,'verification')['status']=='verified'
        assert structured.search(delegated,'Unverified',filters=StructuredFilters(version_tags=['0.28']))['hits']
        delegated_operations=[{'operation':'wiki.upsert','arguments':{'slug':'delegated-consolidation','title':'Delegated','body':'Delegated'}}]
        delegated_bundle=bundles.apply(delegated,delegated_operations,idempotency_key='delegated-consolidation')
        assert delegated_bundle['space_id']==private['id']
        spaces.set_grant(owner,private['id'],editor.user_id,None,expected_revision=1,idempotency_key='revoke')
        spaces.set_grant(owner,private['id'],editor.user_id,Role.EDITOR,expected_revision=2,idempotency_key='regrant')
        try:selected.get_page(delegated,first['id'])
        except PermissionDenied:pass
        else:raise AssertionError('Captured authority survived revocation/regrant')
        try:project.export_page(delegated,'objects')
        except PermissionDenied:pass
        else:raise AssertionError('Captured project export authority revived')
        try:annotations.get(delegated,target,'verification')
        except PermissionDenied:pass
        else:raise AssertionError('Captured annotation authority revived')
        try:structured.search(delegated,'Unverified')
        except PermissionDenied:pass
        else:raise AssertionError('Captured retrieval authority revived')
        try:tokens.verify(pair.access_token,resource=resource)
        except GrantRejected:pass
        else:raise AssertionError('Revoked token revived')
        try:bundles.apply(delegated,delegated_operations,idempotency_key='delegated-consolidation')
        except PermissionDenied:pass
        else:raise AssertionError('Captured bundle receipt authority revived')
        with database.engine.begin() as c:registry.get('source.cleanup').execute(c,{'version_id':receipt['id']})
finally:
    with database.engine.begin() as c:
        if client_id:c.execute(text('DELETE FROM c0_oauth_clients WHERE id=:id'),{'id':client_id})
        for identifier in created:
            for table in ('c0_annotation_targets','c0_evidence_links','c0_entity_links','c0_relations','c0_claims','c0_knowledge_receipts',
                          'c0_knowledge_events','c0_entity_aliases','c0_entities','c0_wiki_revisions','c0_wiki_pages',
                          'c0_chunks','c0_documents','c0_source_versions','c0_sources','c0_jobs','c0_object_relations',
                          'c0_object_keys','c0_objects','c0_object_events','c0_space_grants'):
                c.execute(text('DELETE FROM '+table+' WHERE space_id=:space'),{'space':identifier})
            c.execute(text('DELETE FROM c0_spaces WHERE id=:id'),{'id':identifier})
        c.execute(text('DELETE FROM c0_object_types WHERE name=:name'),{'name':type_name})
        c.execute(text('DELETE FROM c0_accounts WHERE issuer=:issuer'),{'issuer':issuer})
    database.close()
print(json.dumps({'spaces':True,'scoped_names':True,'immutable_evidence':True,'typed_references':True,'grant_revocation':True,'annotations':True,'structured_retrieval':True,'atomic_consolidation':True,'maintenance_annotations':True,'research_projects':True}))
