# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the installed library without importing the application or collectors."""
import importlib.util
import json
import os
import time
from uuid import uuid4
from czero_core.access import AccessService
from czero_core.automatic_sources import AutomaticSourceService,UpdateConflict
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.spaces import SpaceService

assert os.environ.get('CZERO_DISPOSABLE_TEST')=='1'
assert importlib.util.find_spec('czero_app') is None
key=uuid4();issuer='https://idp.example.test/'+uuid4().hex
database=Database()
try:
    access=AccessService(database,issuer,key)
    owner=access.resolve(VerifiedIdentity(issuer,'synthetic-owner',str(key),'owner','Owner',time.time()+300))
    space=SpaceService(database,access).create(owner,'Native sources '+uuid4().hex,idempotency_key=uuid4().hex)['id']
    service=AutomaticSourceService(database,access).in_space(space)
    draft={'name':'Public repository','kind':'github','config':{'repositories':['synthetic/example']},'enabled':True,'interval_seconds':3600,'idempotency_key':uuid4().hex}
    saved=service.save(owner,**draft)
    assert service.save(owner,**draft)==saved
    assert str(service.list(owner)[0]['id'])==saved['id']
    run=service.claim()
    assert str(run['id'])==saved['id'] and str(run['space_id'])==str(space)
    with database.engine.begin() as connection:service.fenced(connection,run)
    service.command(owner,saved['id'],action='pause',expected_revision=1,idempotency_key=uuid4().hex)
    assert service.runs(owner,saved['id'])[0]['state']=='cancelled'
    with database.engine.begin() as connection:
        try:service.fenced(connection,run)
        except UpdateConflict:pass
        else:raise AssertionError('Paused source retained a publication fence')
    service.command(owner,saved['id'],action='remove',expected_revision=2,idempotency_key=uuid4().hex)
    assert service.list(owner)==[]
    print(json.dumps({'installed_automatic_sources':True,'background_fence':True,'source_configuration_replay':True}))
finally:database.close()
