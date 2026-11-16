# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed Core fixture for a disposable native backup, never real knowledge."""
import json
import os
from pathlib import Path
import time
from uuid import UUID,uuid4
from sqlalchemy import text
from czero_core import Database
from czero_core.access import AccessService
from czero_core.current_content import ContentSuperseded
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.personal_data import PersonalDataService,guard_publication,record_checkpoint
from czero_core.sources import OriginalStore,SourceService,register_source_handlers
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService

assert os.environ.get('CZERO_DISPOSABLE_TEST')=='1'
mode=os.environ['CZERO_PERSONAL_STAGE'];assert mode in ('seed','verify')
path=Path(os.environ.get('CZERO_PERSONAL_STATE','/var/lib/czero/sources/personal-fixture.json'))
db=Database()
try:
    if mode=='seed':
        assert not path.exists(),'Preserve the existing fixture'
        state={k:str(uuid4()) for k in ('owner','person','provider','instance','voice_instance')}
        state['issuer']='https://personal-fixture.example.invalid/'+uuid4().hex
    else:state=json.loads(path.read_text())
    access=AccessService(db,state['issuer'],UUID(state['owner']),admit_readers=True)
    def login(key,name):return access.resolve(VerifiedIdentity(state['issuer'],key,key,name,name,time.time()+300))
    owner=login(state['owner'],'fixture-owner')
    originals=OriginalStore(path.parent);registry=default_registry()
    register_source_handlers(registry,db,originals)
    sources=SourceService(db,access,registry,originals)
    personal=PersonalDataService(db,access,sources)
    if mode=='seed':
        personal.configure(owner,provider_id=state['provider'],enabled=True,services={'webtop':state['instance'],'nethvoice':state['voice_instance']},expected_generation=0)
        personal.validate_binding(generation=1,provider_id=state['provider'],services={'webtop':state['instance'],'nethvoice':state['voice_instance']})
        row=personal.reconcile_directory(provider_id=state['provider'],entries=[{'directory_id':state['person'],'username':'fixture-person','active':True}],complete=True)[0]
        state.update(space=row['space_id'],mapping=row['id'])
    actor=login(state['person'],'fixture-person')
    selected=sources.in_space(state['space']);wiki=WikiService(db,access).in_space(state['space'])
    if mode=='seed':
        args=dict(owner_id=state['mapping'],generation=1,connector='webtop',instance_id=state['instance'],kind='message',title='Synthetic personal fixture')
        retained=personal.submit(**args,remote_key='retained',content=b'Synthetic retained import')
        state['import']=retained['source_id']
        excluded=personal.submit(**args,remote_key='excluded',content=b'Synthetic excluded import')
        voice=personal.submit(owner_id=state['mapping'],generation=1,connector='nethvoice',instance_id=state['voice_instance'],
            remote_key='101',kind='transcript',title='Synthetic call',content=b'Synthetic participated call',
            metadata={'uniqueid':'fixture.call.101','linkedid':'fixture.transfer'})
        state['voice_import']=voice['source_id']
        state['versions']=[retained['version_id'],excluded['version_id'],voice['version_id']]
        selected.delete(actor,excluded['source_id'],expected_revision=selected.get(actor,excluded['source_id'])['revision'])
        personal.cleanup()
        state['wiki']=wiki.upsert_page(actor,slug='personal-backup-fixture',title='Authored fixture',body='Separately authored fixture.',idempotency_key='authored')['id']
        record_checkpoint(personal,owner_id=state['mapping'],generation=1,connector='webtop',instance_id=state['instance'],
            cursor={'page_size':5,'page':3,'folder_index':0},status='backfill')
        path.write_text(json.dumps(state));path.chmod(0o600)
        print(json.dumps({'personal_backup_seeded':True}))
    else:
        with db.engine.connect() as c:
            config=c.execute(text('SELECT * FROM c0_personal_config WHERE issuer=:issuer'),{'issuer':state['issuer']}).mappings().one()
            assert config['enabled'] and not config['validated'],'Restore must invalidate source bindings'
            row=c.execute(text('SELECT * FROM c0_personal_owners WHERE id=:id'),{'id':UUID(state['mapping'])}).mappings().one()
            assert str(row['space_id'])==state['space'] and str(row['directory_id'])==state['person']
            cursor=c.execute(text('SELECT cursor FROM c0_personal_checkpoints WHERE owner_id=:id'),{'id':row['id']}).scalar_one()
            assert cursor=={'page_size':5,'page':3,'folder_index':0}
            excluded=c.execute(text("SELECT state,content_hash FROM c0_personal_imports WHERE owner_id=:id AND remote_key='excluded'"),{'id':row['id']}).one()
            assert tuple(excluded)==('excluded',None)
            call_identity=c.execute(text('SELECT slot_key FROM c0_personal_imports WHERE source_id=:id'),{'id':UUID(state['voice_import'])}).scalar_one()
            assert json.loads(call_identity)==['fixture.call.101','fixture.transfer']
            try:guard_publication(c,UUID(state['import']))
            except ContentSuperseded:pass
            else:raise AssertionError('Restored import could publish before binding validation')
        assert SpaceService(db,access).get(actor,state['space'])['role']=='editor'
        assert selected.get(actor,state['import'])['managed_import']['state']=='managed'
        personal.configure(owner,provider_id=state['provider'],enabled=False,services={'webtop':state['instance'],'nethvoice':state['voice_instance']},expected_generation=1)
        personal.cleanup()
        assert selected.get(actor,state['import'])['deleted'] and selected.get(actor,state['voice_import'])['deleted']
        assert wiki.get_page(actor,state['wiki'])['content']['body']=='Separately authored fixture.'
        with db.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':UUID(state['import'])}).scalar_one()==0
        with db.engine.begin() as c:registry.get('source.cleanup').execute(c,{'version_id':str(UUID(int=0))})
        assert not any(originals.path(version).exists() for version in state['versions'])
        path.unlink()
        print(json.dumps({'personal_mapping_checkpoint_exclusion_restored':True,'personal_restore_fenced':True,'personal_import_cleanup':True,'personal_authored_retained':True}))
finally:db.close()
