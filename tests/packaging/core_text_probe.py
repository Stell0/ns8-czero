# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent installed-package client; identities are disposable trusted fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from czero_core import Database
from czero_core.access import AccessService
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore, SourceService, register_source_handlers
from czero_core.worker import Worker
from czero_core.wiki import WikiService, KnowledgeConflict

assert importlib.util.find_spec('agent') is None
assert importlib.util.find_spec('czero_app') is None
issuer='https://fixture.example.invalid/'+uuid4().hex
key=uuid4()
body='Packaged Core evidence café 東京'
database=Database()
access=AccessService(database,issuer,key)
actor=access.resolve(VerifiedIdentity(issuer,'fixture',str(key),'fixture','Synthetic fixture',time.time()+300))
with tempfile.TemporaryDirectory(prefix='core-text-') as directory:
    originals=OriginalStore(Path(directory)/'originals')
    registry=default_registry();register_source_handlers(registry,database,originals)
    service=SourceService(database,access,registry,originals)
    values={'title':'Packaged text','body':body,'idempotency_key':'packaged-ingest'}
    receipt=service.ingest_text(actor,**values)
    assert receipt['state']=='queued'
    wiki=WikiService(database,access)
    page_values={'slug':'packaged-procedure','title':'Procedure','body':'Original observation',
                 'metadata':{'status':'unverified'},'idempotency_key':'packaged-wiki'}
    first=wiki.upsert_page(actor,**page_values)
    second=wiki.upsert_page(actor,**{**page_values,'body':'Revised observation','expected_revision':1,
                                   'idempotency_key':'packaged-revise'})
    Worker(database,registry).tick()
    database.close()
    later=Database()
    try:
        acl=AccessService(later,issuer,key)
        wiki=WikiService(later,acl)
        assert wiki.resolve_page(actor,page_values['slug'])==second
        assert wiki.upsert_page(actor,**page_values)==first
        assert wiki.get_page(actor,first['id'],revision=1)['content']==first['content']
        assert [v['number'] for v in wiki.page_history(actor,first['id'])]==[2,1]
        try:
            wiki.upsert_page(actor,**{**page_values,'idempotency_key':'different'})
        except KnowledgeConflict: pass
        else: raise AssertionError('Installed package silently overwrote a page')
        service=SourceService(later,acl,registry,originals)
        assert service.ingest_text(actor,**values)==receipt
        assert service.versions(actor,receipt['source_id'])[0]['state']=='ready'
        document=service.document(actor,receipt['id'])
        assert document['body']==body
        citation=service.citation(actor,service.chunks(actor,document['id'])[0]['id'])
        assert citation['source_hash']==hashlib.sha256(body.encode()).hexdigest()
        assert not list(originals.root.iterdir())
    finally: later.close()
print(json.dumps({'ready_evidence':True,'replay_after_reconnect':True,'original_cleanup':True,'independent_package':True,'wiki_revisions_replay_reconnect':True}))
