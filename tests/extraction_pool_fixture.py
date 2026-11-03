# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Run inside the installed app on an explicitly disposable native instance."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from uuid import UUID,uuid4

from sqlalchemy import text
from czero_core.access import AccessService
from czero_core.database import Database
from czero_core.extraction_queue import ExtractionQueue
from czero_core.identity import Actor,Role
from czero_core.jobs import default_registry
from czero_core.sources import OriginalStore,SourceService,register_source_handlers
from czero_core.spaces import SpaceService


def main(stage,workers):
    assert os.getenv('CZERO_DISPOSABLE_TEST')=='1' and stage in ('seed','verify','reindex') and workers in (2,4)
    database=Database()
    access=AccessService(database,os.environ['CZERO_OIDC_ISSUER'],UUID(os.environ['CZERO_OWNER_LDAP_UUID']))
    assert '.test' in access.issuer,'Disposable identity provider required'
    with database.engine.connect() as c:
        identifier=c.execute(text('SELECT id FROM c0_accounts WHERE issuer=:issuer AND account_key=:key'),
            {'issuer':access.issuer,'key':access.owner_account_key}).scalar_one()
    actor=Actor(identifier,Role.READER)
    originals=OriginalStore('/var/lib/czero/sources')
    saved=originals.root/('.c0-extraction-acceptance-'+str(workers)+'.json')
    # Before each explicitly requested operation, the only extraction runs
    # may be this fixture's existing checkpoints. Upgrade/default reads must
    # never manufacture a corpus-wide extraction backfill.
    owned={UUID(json.loads(path.read_text())['run']) for path in
        (originals.root/'.c0-extraction-acceptance-2.json',originals.root/'.c0-extraction-acceptance-4.json') if path.exists()}
    with database.engine.connect() as c:
        assert set(c.execute(text('SELECT id FROM c0_extraction_runs')).scalars())==owned,'Unrequested extraction backfill'
    labels=['Synthetic pool page '+str(page).zfill(3)+'.' for page in range(1,9)]
    expected='\n\n'.join([*labels,PHRASE])
    if stage=='seed':
        assert not saved.exists(),'Native pool checkpoint already exists'
        space=SpaceService(database,access).create(actor,'Disposable extraction '+uuid4().hex,idempotency_key=uuid4().hex)
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject,DictionaryObject,NameObject
        writer=PdfWriter()
        for label in labels:
            page=writer.add_blank_page(width=612,height=792)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject(); stream.set_data(('BT /F1 12 Tf 72 720 Td ('+label+') Tj ET').encode())
            page[NameObject('/Contents')]=writer._add_object(stream)
        from pypdf import PdfReader
        writer.add_page(PdfReader(BytesIO(scanned_original())).pages[0])
        stream=BytesIO(); writer.write(stream); stream.seek(0)
        registry=default_registry(); register_source_handlers(registry,database,originals)
        sources=SourceService(database,access,registry,originals).in_space(space['id'])
        version=sources.ingest(actor,stream,title='Disposable pool original',filename='pool.pdf',media_type='application/pdf',retain_original=True)
        queue=ExtractionQueue(database,access,originals,enabled=True,ocr_language='eng').in_space(space['id'])
        run=queue.enqueue(actor,version['id'],expected_generation=1)
        value={'space':str(space['id']),'version':str(version['id']),'run':str(run['id'])}
        descriptor=os.open(saved,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'w') as out: json.dump(value,out)
        assert run['expected_units']==9 and run['succeeded']==0
    else:
        value=json.loads(saved.read_text())
        queue=ExtractionQueue(database,access,originals,enabled=True,ocr_language='eng').in_space(value['space'])
        assert queue.status(actor,value['run'])['state']=='ready'
        registry=default_registry(); register_source_handlers(registry,database,originals)
        sources=SourceService(database,access,registry,originals).in_space(value['space'])
        document=sources.document(actor,value['version'],include_derivatives=True)
        assert document['body']==expected and document['text_hash']==hashlib.sha256(expected.encode()).hexdigest()
        assert [row['index'] for row in document['locations']]==list(range(1,10))
        assert len(document['structure']['ocr']['pages'])==1 and document['structure']['ocr']['pages'][0]['page']==9
        chunks=sources.chunks(actor,document['id'])
        assert chunks
        for chunk in chunks:
            assert chunk['body']==expected[chunk['start_offset']:chunk['end_offset']]
            assert sources.citation(actor,chunk['id'])['body']==chunk['body']
        with database.engine.connect() as c:
            assert c.execute(text('SELECT count(*) FROM c0_extraction_units WHERE run_id=:id AND body IS NOT NULL'),{'id':UUID(value['run'])}).scalar_one()==0
        if stage=='reindex':
            before=sources.versions(actor,sources.citation(actor,chunks[0]['id'])['source_id'])[0]
            original=sources.originals.check(before).read_bytes()
            source=sources.get(actor,before['source_id'])
            replacement=sources.reindex(actor,before['source_id'],expected_revision=source['revision'],idempotency_key='native-explicit-reindex-'+str(workers))
            queue=ExtractionQueue(database,access,originals,enabled=True,ocr_language='eng',instance_workers=workers,
                document_workers=workers,space_workers=workers).in_space(value['space'])
            later=queue.enqueue(actor,replacement['id'],expected_generation=1)
            from czero_core.extraction_queue import ExtractionPool
            assert ExtractionPool(queue,workers=workers).tick()['processed']==9
            status=queue.status(actor,later['id'])
            assert status['state']=='ready' and status['cache_hits']==9
            current=sources.document(actor,replacement['id'])
            assert current['body']==expected and current['id']!=document['id']
            assert sources.originals.check(sources.versions(actor,before['source_id'])[0]).read_bytes()==original
            from czero_core.current_content import ContentSuperseded
            for chunk in chunks:
                try:sources.citation(actor,chunk['id'])
                except ContentSuperseded:pass
                else:raise AssertionError('Reindex retained superseded exact evidence')
            with database.engine.begin() as c:
                # Advance only this fixture's retired cleanup intent; normal
                # production delay and GC ownership checks remain unchanged.
                c.execute(text('UPDATE c0_original_cleanup SET available_at=now() WHERE version_id=:id'),{'id':before['id']})
                registry.get('source.cleanup').execute(c,{'version_id':str(UUID(int=0))})
                assert c.execute(text('SELECT count(*) FROM c0_source_versions WHERE source_id=:id'),{'id':before['source_id']}).scalar_one()==1
            assert not originals.path(before['id']).exists()
            assert queue.progress(actor,before['source_id'])['run']['completed']==9
            value.update(version=str(replacement['id']),run=str(later['id']))
            saved.write_text(json.dumps(value))
    database.close()
    print(json.dumps({'stage':stage,'workers':workers,'units':9,'verified':True}))


if __name__=='__main__':
    try: main(sys.argv[1],int(sys.argv[2]))
    except Exception as error:
        print('Disposable extraction pool proof failed ('+type(error).__name__+')',file=sys.stderr)
        sys.exit(1)
