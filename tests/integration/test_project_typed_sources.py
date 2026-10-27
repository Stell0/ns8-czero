# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4
from czero_core.identity import Role,PermissionDenied
from czero_core.objects import ObjectService
from czero_core.spaces import SpaceService
from c0_projects.adapters import collect
from c0_projects.model import source_config
from test_access import access,identity,record_unadmitted,account_named
from test_projects import project,initialize


def test_selected_typed_source_rechecks_real_postgresql_grants_and_retains_provenance(project,tmp_path):
    target,manifest,owner,create=project;initialize(project);source,_=create()
    objects=ObjectService(source.database,source.access).in_space(source._space_id)
    name='fixture_repo_'+uuid4().hex
    objects.register_type(owner,name,'Synthetic repository',{'type':'object','properties':{
        'repository':{'type':'string','maxLength':128}},'required':['repository'],'additionalProperties':False})
    saved=objects.create(owner,name,{'repository':'fixture-c0-lab/synthetic-project'})
    accounts=source.access;key=uuid4();record_unadmitted(accounts,key,'subscription-reader')
    account=account_named(accounts,owner,'subscription-reader');accounts.set_role(owner,account['id'],Role.READER)
    actor=accounts.resolve(identity(accounts,key,'subscription-reader'));spaces=SpaceService(source.database,accounts)
    spaces.set_grant(owner,str(source._space_id),actor.user_id,Role.READER,expected_revision=0,idempotency_key='grant-source')
    class Reader:
        space_id=str(source._space_id)
        def call(self,name,**values):
            from c0_ingest.errors import C0Error
            from czero_core.receipts import snapshot
            try:
                if name=='objects_changes':return snapshot({'events':objects.events(actor,**values)})
                if name=='object_types_get':return snapshot(objects.get_type(actor,values['type_name']))
                if name=='objects_list':return snapshot({'objects':objects.list(actor,**values)})
                if name=='objects_get':return snapshot(objects.get(actor,values['object_id']))
                raise AssertionError('Unexpected source operation')
            except PermissionDenied:raise C0Error('permission_denied') from None
    definition=source_config({'id':'repo-subscription','adapter':'c0_space','source_space_id':str(source._space_id),
        'authorization_ref':'synthetic explicit subscription','include':['objects:'+name]})
    first=collect(definition,source_client=Reader(),root=tmp_path)
    assert first.status=='complete' and len(first.items)==1 and first.cursor['object_after']>0
    item=first.items[0];assert item.provenance['space_id']==str(source._space_id) and item.provenance['object_id']==str(saved['id'])
    assert item.provenance['revision']==1 and 'fixture-c0-lab/synthetic-project' in item.content.decode()
    assert not target.list_records(owner,'source_sync_v1') # Retrieval itself never writes a destination.
    spaces.set_grant(owner,str(source._space_id),actor.user_id,None,expected_revision=1,idempotency_key='revoke-source')
    denied=collect(definition,source_client=Reader(),cursor=first.cursor,root=tmp_path)
    assert denied.status=='partial' and not denied.items and not denied.cursor.get('complete')
    assert first.cursor['object_after']>0 # Prior successful receipt is unchanged.
