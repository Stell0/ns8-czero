# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed distribution and retained-reference native backup/restore proof."""
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from sqlalchemy import text
from czero_core import Database
from czero_core.access import AccessService
from czero_core.cross_space_references import CrossSpaceReferenceService
from czero_core.identity import VerifiedIdentity
from czero_core.objects import ObjectService
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService

assert os.environ.get('CZERO_DISPOSABLE_TEST') == '1'
mode=os.environ.get('CZERO_REFERENCE_STAGE','once')
assert mode in ('once','seed','verify')
state_path=Path(os.environ.get('CZERO_REFERENCE_STATE','/var/lib/czero/sources/reference-fixture.json'))
db=Database()
try:
    if mode=='verify':
        state=json.loads(state_path.read_text())
        key,issuer=state['key'],state['issuer']
    else:
        if mode=='seed':assert not state_path.exists(), 'Preserve the earlier fixture'
        key,issuer=str(uuid4()),'https://idp.example.test/realms/'+uuid4().hex
    access=AccessService(db,issuer,key)
    owner=access.resolve(VerifiedIdentity(issuer,'owner',key,'owner','Owner',time.time()+300))
    service=CrossSpaceReferenceService(db,access)
    if mode=='verify':
        args,ack=state['request'],state['ack']
        retained,retained_ack=state['retained'],state['retained_ack']
        source_space,source,target_space=args['space_id'],args['source'],args['target']['space_id']
        assert service.create(owner,**args)==ack
        assert service.create(owner,**retained)==retained_ack
        result=service.list(owner,space_id=source_space,source=source,target_space_ids=[target_space])
        assert [row['id'] for row in result['references']]==[retained_ack['reference_id']]
        assert result['references'][0]['target']['id']==args['target']['id']
        assert retained_ack!=ack  # Restored original receipts cannot resurrect deleted edges.
        page=WikiService(db,access).in_space(target_space).get_page(owner,args['target']['id'])
        assert page['content']['body']=='Original guide.'
        state_path.unlink()
    else:
        spaces=SpaceService(db,access)
        source_space=spaces.create(owner,'Support '+uuid4().hex,idempotency_key=uuid4().hex)['id']
        target_space=spaces.create(owner,'Documentation '+uuid4().hex,idempotency_key=uuid4().hex)['id']
        objects=ObjectService(db,access)
        type_name='reference-'+uuid4().hex
        objects.register_type(owner,type_name,'Ticket',{'type':'object'},[])
        source=objects.in_space(source_space).create(owner,type_name,{})
        page=WikiService(db,access).in_space(target_space).create_page(owner,'guide','Guide','Original guide.',idempotency_key=uuid4().hex)
        source={'kind':'object','id':str(source['id']),'type_name':type_name}
        args={'space_id':source_space,'source':source,'target':{'space_id':target_space,'kind':'page','id':page['id']},'idempotency_key':uuid4().hex}
        ack=service.create(owner,**args)
        assert service.create(owner,**args)==ack
        result=service.list(owner,space_id=source_space,source=source,target_space_ids=[target_space])
        assert result['references'][0]['target']['label']=='Guide'
        assert service.delete(owner,space_id=source_space,source=source,reference_id=ack['reference_id'],idempotency_key=uuid4().hex) is None
        assert service.create(owner,**args)==ack
        assert service.list(owner,space_id=source_space,source=source,target_space_ids=[target_space])['references']==[]
        if mode=='seed':
            retained={**args,'idempotency_key':uuid4().hex}
            retained_ack=service.create(owner,**retained)
            state={'key':key,'issuer':issuer,'request':args,'ack':ack,'retained':retained,'retained_ack':retained_ack}
            state_path.write_text(json.dumps(state))
            state_path.chmod(0o600)
    with db.engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0039_space_audiences'
    print(json.dumps({'installed_references':True,'payload_free_replay':True,'packaged_schema0039':True,
        **({'retained_reference_seeded':True} if mode=='seed' else {}),
        **({'restored_reference_verified':True} if mode=='verify' else {})}))
finally:db.close()
