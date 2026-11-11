# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed wheel/archive navigation and migration proof on a disposable DB."""
import json
import os
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
db=Database()
key=uuid4()
access=AccessService(db,'https://idp.example.test/realms/'+uuid4().hex,key)
owner=access.resolve(VerifiedIdentity(access.issuer,'owner',str(key),'owner','Owner',time.time()+300))
spaces=SpaceService(db,access)
source_space=spaces.create(owner,'Support '+uuid4().hex,idempotency_key=uuid4().hex)['id']
target_space=spaces.create(owner,'Documentation '+uuid4().hex,idempotency_key=uuid4().hex)['id']
objects=ObjectService(db,access)
type_name='reference-'+uuid4().hex
objects.register_type(owner,type_name,'Ticket',{'type':'object'},[])
source=objects.in_space(source_space).create(owner,type_name,{})
page=WikiService(db,access).in_space(target_space).create_page(owner,'guide','Guide','Original guide.',idempotency_key=uuid4().hex)
service=CrossSpaceReferenceService(db,access)
source={'kind':'object','id':str(source['id']),'type_name':type_name}
args={'space_id':source_space,'source':source,'target':{'space_id':target_space,'kind':'page','id':page['id']},'idempotency_key':uuid4().hex}
ack=service.create(owner,**args)
assert service.create(owner,**args)==ack
result=service.list(owner,space_id=source_space,source=source,target_space_ids=[target_space])
assert result['references'][0]['target']['label']=='Guide'
assert service.delete(owner,space_id=source_space,source=source,reference_id=ack['reference_id'],idempotency_key=uuid4().hex) is None
assert service.create(owner,**args)==ack
assert service.list(owner,space_id=source_space,source=source,target_space_ids=[target_space])['references']==[]
with db.engine.connect() as c:
    assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0038_cross_space_references'
print(json.dumps({'installed_references':True,'payload_free_replay':True,'packaged_schema0038':True}))
db.close()
