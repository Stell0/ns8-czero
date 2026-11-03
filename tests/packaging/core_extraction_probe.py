# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Executed outside the checkout in each independently installed Core artifact."""
import json
import os
from io import BytesIO
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from sqlalchemy import text
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.extraction_queue import ExtractionQueue, ExtractionWorker
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore, SourceService, register_source_handlers

database = Database(os.environ['CZERO_DATABASE_URL'])
owner_key = uuid4()
access = AccessService(database,'https://idp.example.test/units/'+uuid4().hex,owner_key)
actor = access.resolve(VerifiedIdentity(access.issuer,'owner',str(owner_key),'owner','Owner',time.time()+300))
with tempfile.TemporaryDirectory() as directory:
    originals = OriginalStore(Path(directory)/'originals')
    registry = default_registry()
    register_source_handlers(registry,database,originals)
    sources = SourceService(database,access,registry,originals)
    version = sources.ingest(actor,BytesIO(b'Independent unit evidence'),title='Units',filename='units.txt',media_type='text/plain')
    queue = ExtractionQueue(database,access,originals,enabled=True)
    run = queue.enqueue(actor,version['id'],expected_generation=1)
    assert ExtractionWorker(queue).tick()==1
    assert queue.status(actor,run['id'])['state']=='assembling'
    with database.engine.connect() as connection:
        assert connection.execute(text('SELECT body FROM c0_extraction_units WHERE run_id=:id'),{'id':run['id']}).scalar_one()=='Independent unit evidence'
        assert connection.execute(text('SELECT count(*) FROM c0_documents WHERE version_id=:id'),{'id':version['id']}).scalar_one()==0
    sources.delete(actor,version['source_id'],expected_revision=1)
    assert queue.status(actor,run['id'])['state']=='superseded'
database.close()
print(json.dumps({'installed_extraction_staging':True}))
