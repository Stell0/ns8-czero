# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Executed by the independently installed, immutable Core 0.35.2 only."""
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

from sqlalchemy import text
from czero_core.access import AccessService
from czero_core.annotations import AnnotationService,ContentTarget
from czero_core.database import Database
from czero_core.identity import VerifiedIdentity
from czero_core.jobs import default_registry
from czero_core.knowledge import KnowledgeService
from czero_core.migrate import migrate_database
from czero_core.projects import ProjectService
from czero_core.project_schema import normalize_manifest
from czero_core.receipts import snapshot
from czero_core.sources import OriginalStore,SourceService,register_source_handlers
from czero_core.spaces import SpaceService


def seed(directory):
    directory=Path(directory);database=Database();migrate_database(database)
    assert database.health()['schema_revision']=='0022_remembered_browsers'
    issuer='https://idp.example.org/'+uuid4().hex;key=uuid4()
    access=AccessService(database,issuer,key)
    actor=access.resolve(VerifiedIdentity(issuer,'owner',str(key),'owner','Owner',time.time()+3600))
    space=SpaceService(database,access).create(actor,'Disposable migration',idempotency_key='space')
    registry=default_registry();originals=OriginalStore(directory/'originals');register_source_handlers(registry,database,originals)
    sources=SourceService(database,access,registry,originals).in_space(space['id'])
    wiki=KnowledgeService(database,access).in_space(space['id'])
    def extract(version):
        with database.engine.begin() as connection:registry.get('source.extract').execute(connection,{'version_id':version['id']})
    first=sources.ingest(actor,BytesIO(b'RETIRED-SOURCE-A-UNIQUE'),title='Original source',filename='source.md',media_type='text/markdown',retain_original=True)
    extract(first)
    document=sources.document(actor,first['id']);chunk=sources.chunks(actor,document['id'])[0]
    second=sources.ingest(actor,BytesIO(b'CURRENT-SOURCE-B-UNIQUE'),title='Original source',filename='source.md',media_type='text/markdown',retain_original=True,source_id=first['source_id'],expected_revision=1)
    extract(second)
    queued=sources.ingest(actor,BytesIO(b'QUEUED-MUST-NOT-DISPLACE-CURRENT'),title='Original source',filename='source.md',media_type='text/markdown',retain_original=True,source_id=first['source_id'],expected_revision=2)
    page=wiki.create_page(actor,'retained-article','Authored article','RETIRED-WIKI-A-UNIQUE',idempotency_key='wiki-first')
    updated=wiki.update_page(actor,page['id'],'Authored article','CURRENT-WIKI-B-UNIQUE\n\nIntentional quotation: RETIRED-SOURCE-A-UNIQUE',expected_revision=1,idempotency_key='wiki-second')
    entity=wiki.create_entity(actor,'product','Synthetic product',idempotency_key='entity')
    claim=wiki.create_claim(actor,entity['id'],'observed',{'text':'Authored assertion remains'},evidence_chunk_ids=[chunk['id']],page_id=page['id'],idempotency_key='claim')
    annotations=AnnotationService(database,access).in_space(space['id'])
    annotations.update(actor,ContentTarget('source_version',first['id'],1),'verification',{'status':'verified'},expected_revision=0,idempotency_key='verified')
    dated=sources.ingest(actor,BytesIO(b'CURRENT-INDEPENDENT-VERSION-14-MANUAL'),title='Version 14 manual',filename='v14.md',media_type='text/markdown',retain_original=True,metadata={'product_version':'14','published_at':'2009-01-01T00:00:00Z'})
    extract(dated)
    project=ProjectService(database,access).in_space(space['id'])
    manifest=normalize_manifest({'project_id':space['id'],'space_id':space['id'],'name':'Synthetic migration','purpose':'Seed complete predecessor content','scope':'Synthetic only','connector_ids':['documents']})
    project.initialize(actor,manifest,authorization_ref='disposable migration seed',idempotency_key='project')
    definition={'id':'documents','adapter':'local_files','enabled':True,'include':[],'root':'inputs','max_items':100,'max_requests':40,'max_bytes':8388608,'max_pages':5,'max_depth':2,'timeout':15}
    project.set_connector(actor,definition,authorization_ref='disposable migration seed',idempotency_key='connector')
    definition_hash=hashlib.sha256(json.dumps(definition,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    previous=[];snapshots=[];obsolete_part=None
    for generation,parts in enumerate(([b'# Original multipart\n\nOLD-PART-1\n',b'OLD-PART-2\n',b'OLD-REMOVED-LAST-PART\n'],[b'# Current multipart\n\nCURRENT-PART-1\n',b'CURRENT-PART-2\n']),1):
        parent_hash=hashlib.sha256(b''.join(parts)).hexdigest();offset=0;receipts=[];new=[]
        for number,body in enumerate(parts,1):
            external='part-'+str(number);source=previous[number-1] if previous else None
            version=sources.ingest(actor,BytesIO(body),title='Multipart manual',filename='part.md',media_type='text/markdown',retain_original=True,
                metadata={'parent_external_id':'multipart.md','connector_id':'documents'},source_id=source['source_id'] if source else None,expected_revision=1 if source else None)
            extract(version);stamp=datetime.now(timezone.utc).isoformat()
            data={'connector_id':'documents','definition_hash':definition_hash,'external_id':external,'parent_external_id':'multipart.md','parent_content_hash':parent_hash,
                'part_number':number,'start_byte':offset,'end_byte':offset+len(body),'last_attempt_at':stamp,'last_success_at':'','last_content_hash':version['content_hash'],
                'source_id':str(version['source_id']),'version_id':str(version['id']),'extraction_status':'ready','sync_status':'verified','last_error':'','retry_after':'','remote_cursor':'',
                'provenance':{'original_url':'https://docs.example.org/manual','canonical_url':'https://docs.example.org/manual','retrieved_at':stamp,'published_at':'','updated_at':'','details':'{}'}}
            receipt=project.save_source_status(actor,data,expected_revision=generation-1,idempotency_key='part-'+str(generation)+'-'+str(number))
            receipts.append(receipt['id']);offset+=len(body);new.append(version)
        snapshots.append(project.save_source_snapshot(actor,'documents','multipart.md',parent_hash,receipts,expected_revision=generation-1,idempotency_key='snapshot-'+str(generation)))
        if generation==1:obsolete_part=new[-1]
        previous=new
    archived=wiki.create_page(actor,'archived-current','Archived article','CURRENT-ARCHIVED-BODY',idempotency_key='archived')
    wiki.delete_page(actor,archived['id'],expected_revision=1,idempotency_key='archive')
    # Deterministic real pgvector derivatives, including a superseded chunk.
    with database.engine.begin() as connection:
        profile=uuid4()
        connection.execute(text('INSERT INTO c0_embedding_profiles(id,fingerprint,model,dimensions) VALUES (:id,:hash,\'synthetic\',2)'),{'id':profile,'hash':'a'*64})
        connection.execute(text('''INSERT INTO c0_embeddings(space_id,id,profile_id,generation,source_chunk_id,input_hash,embedding)
            VALUES (:space,:id,:profile,1,:chunk,:hash,CAST(:vector AS vector))'''),{'space':space['id'],'id':uuid4(),'profile':profile,'chunk':chunk['id'],'hash':'b'*64,'vector':'[1,'+','.join(['0']*1999)+']'})
    result=snapshot({'issuer':issuer,'owner_key':key,'space':space['id'],'source':first['source_id'],'retired_version':first['id'],'current_version':second['id'],
        'obsolete_part':obsolete_part['id'],'queued_version':queued['id'],'chunk':chunk['id'],'page':page['id'],'current_wiki':updated['content']['id'],'dated_source':dated['source_id'],
        'parent':snapshots[-1]['id'],'claim':claim['id'],'archived':archived['id']})
    (directory/'identities.json').write_text(json.dumps(result));database.close()


if __name__=='__main__':seed(sys.argv[1])
