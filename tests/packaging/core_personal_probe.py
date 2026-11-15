# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone installed-library proof; synthetic directory, no app/agent dependency."""
import json
import os
import time
from uuid import UUID,uuid4
from sqlalchemy import text
from czero_core import Database
from czero_core.access import AccessService
from czero_core.identity import PermissionDenied,Role,VerifiedIdentity
from czero_core.personal_data import PersonalDataService
from czero_core.spaces import SpaceService

assert os.environ.get('CZERO_DISPOSABLE_TEST')=='1'
db=Database()
try:
    issuer='https://directory.example.test/'+uuid4().hex
    key=uuid4();provider=uuid4();person=uuid4();instance=uuid4()
    access=AccessService(db,issuer,key,admit_readers=True)
    def login(key,name):return access.resolve(VerifiedIdentity(issuer,str(key),str(key),name,name,time.time()+300))
    owner=login(key,'owner')
    personal=PersonalDataService(db,access)
    personal.configure(owner,provider_id=provider,enabled=True,services={'webtop':str(instance)},expected_generation=0)
    spaces=personal.reconcile_directory(provider_id=provider,entries=[{'directory_id':str(person),'username':'person','active':True}],complete=True)
    with db.engine.connect() as c:assert c.execute(text('SELECT count(*) FROM c0_accounts WHERE issuer=:issuer'),{'issuer':issuer}).scalar_one()==1
    actor=login(person,'person');space=spaces[0]['space_id']
    reader=SpaceService(db,access)
    assert reader.get(actor,space)['role']=='editor' and reader.get(actor,space)['personal']
    assert access.profile(actor)['role']=='reader'
    with db.engine.connect() as c:
        assert reader.authorize(c,actor,Role.EDITOR,space_id=space).role is Role.EDITOR
        try:reader.authorize(c,actor,Role.EDITOR)
        except PermissionDenied:pass
        else:raise AssertionError('personal authority escaped to Shared')
    personal.reconcile_directory(provider_id=provider,entries=[],complete=True)
    try:reader.get(actor,space)
    except PermissionDenied:pass
    else:raise AssertionError('disabled owner retained personal access')
    assert reader.get(owner,space)['role']=='admin'
    print(json.dumps({'installed_personal_spaces':True,'no_fabricated_login':True,'personal_authorization':True,'directory_disable':True}))
finally:db.close()
