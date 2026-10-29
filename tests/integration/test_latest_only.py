# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Publication, deletion and payload-free retries against real PostgreSQL."""
import json
from uuid import UUID

import pytest
from sqlalchemy import text

from czero_core.current_content import ContentSuperseded
from czero_core.documents import DocumentService
from test_access import access
from test_sources import sources,upload,execute
from test_wiki import wiki,create_page,create_entity
from test_knowledge import knowledge,evidence
from test_knowledge_http import knowledge_http
from test_auth_http import application


def test_source_atomic_failure_replacement_and_a_b_a(sources):
    service,actor,_,_=sources
    documents=DocumentService(service.database,service.access)
    first=upload(sources,b'OLD-ONLY-MARKER current A',retain_original=True)
    execute(sources,'source.extract',first['id'])
    current=service.get(actor,first['source_id'])
    first_body=service.document(actor,first['id'])
    citation=service.chunks(actor,first_body['id'])[0]
    broken=upload(sources,b'\xff',source_id=current['id'],expected_revision=current['revision'],retain_original=True)
    assert documents.read_document(actor,current['id'])['body']=='OLD-ONLY-MARKER current A'
    assert execute(sources,'source.extract',broken['id'])['state']=='failed'
    assert documents.read_document(actor,current['id'])['body']=='OLD-ONLY-MARKER current A'
    current=service.get(actor,current['id'])
    second=upload(sources,b'NEW-ONLY-MARKER current B',source_id=current['id'],expected_revision=current['revision'],retain_original=True)
    assert documents.read_document(actor,current['id'])['body']=='OLD-ONLY-MARKER current A'
    execute(sources,'source.extract',second['id'])
    assert documents.read_document(actor,current['id'])['body']=='NEW-ONLY-MARKER current B'
    assert service.search(actor,'OLD-ONLY-MARKER')==[]
    with pytest.raises(ContentSuperseded):service.citation(actor,citation['id'])
    with pytest.raises(ContentSuperseded):service.document(actor,first['id'])
    current=service.get(actor,current['id'])
    third=upload(sources,b'OLD-ONLY-MARKER current A',source_id=current['id'],expected_revision=current['revision'],retain_original=True)
    execute(sources,'source.extract',third['id'])
    assert third['id']!=first['id'] and third['number']>second['number']
    assert len(service.versions(actor,current['id']))==1
    execute(sources,'source.cleanup',UUID(int=0))
    assert not service.originals.path(first['id']).exists()
    assert not service.originals.path(second['id']).exists()
    assert not service.originals.path(broken['id']).exists()
    assert service.originals.path(third['id']).read_bytes()==b'OLD-ONLY-MARKER current A'


def test_wiki_removes_bodies_and_receipt_copies_without_replaying_old_content(wiki):
    service,actor,*_=wiki
    first=create_page(wiki,body='FIRST-RETIRED-SECRET-BODY')
    changed=service.update_page(actor,first['id'],'Latest article','CURRENT-ARTICLE',expected_revision=1,idempotency_key='replace')
    assert service.update_page(actor,first['id'],'Latest article','CURRENT-ARTICLE',expected_revision=1,idempotency_key='replace')==changed
    with service.database.engine.connect() as connection:
        bodies=connection.execute(text('SELECT body FROM c0_wiki_revisions WHERE page_id=:id'),{'id':first['id']}).scalars().all()
        receipts=connection.execute(text('SELECT result FROM c0_knowledge_receipts WHERE actor_id=:id'),{'id':actor.user_id}).scalars().all()
    assert bodies==['CURRENT-ARTICLE']
    assert 'FIRST-RETIRED-SECRET-BODY' not in json.dumps(receipts)
    assert 'CURRENT-ARTICLE' not in json.dumps(receipts)
    with pytest.raises(ContentSuperseded):service.get_page(actor,first['id'],revision=1)
    restored=service.update_page(actor,first['id'],'Latest article','FIRST-RETIRED-SECRET-BODY',expected_revision=2,idempotency_key='restore-by-new-write')
    assert restored['revision']==3
    with pytest.raises(ContentSuperseded):service.update_page(actor,first['id'],'Latest article','CURRENT-ARTICLE',expected_revision=1,idempotency_key='replace')
    assert service.get_page(actor,first['id'])==restored


def test_unchanged_wiki_and_metadata_updates_reuse_content_generation(wiki):
    service,actor,*_=wiki
    first=create_page(wiki,body='Stable authored content')
    same=service.update_page(actor,first['id'],first['title'],first['content']['body'],expected_revision=1,idempotency_key='same-bytes')
    assert same==first
    changed=service.update_page(actor,first['id'],'New current title',first['content']['body'],expected_revision=1,idempotency_key='new-title')
    assert changed['revision']==2 and changed['content']['id']==first['content']['id']
    assert changed['content']['content_hash']==first['content']['content_hash']
    service.delete_page(actor,first['id'],expected_revision=2,idempotency_key='archive-same-bytes')
    retained=service.get_page(actor,first['id'])
    assert retained['deleted'] and retained['content']['id']==first['content']['id']
    assert len(service.page_history(actor,first['id']))==1


def test_normalized_text_reconciliation_keeps_current_chunks(sources):
    service,actor,*_=sources
    first=upload(sources,b'Line one\nLine two\n',retain_original=True)
    execute(sources,'source.extract',first['id'])
    before=service.document(actor,first['id']);chunks=service.chunks(actor,before['id'])
    staged=upload(sources,b'Line one\r\nLine two\r\n',source_id=first['source_id'],expected_revision=1,retain_original=True)
    result=execute(sources,'source.extract',staged['id'])
    assert result['state']=='unchanged' and result['current_version_id']==str(first['id'])
    assert service.document(actor,first['id'])==before
    assert service.chunks(actor,before['id'])==chunks
    assert [row['id'] for row in service.versions(actor,first['source_id'])]==[first['id']]
    with pytest.raises(ContentSuperseded):service.document(actor,staged['id'])


def test_claim_publication_race_invalidates_evidence_after_committed_claim(knowledge,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor,TimeoutError
    from threading import Event
    service,wiki,sources=knowledge;actor=wiki[1]
    version,document,chunk=evidence(knowledge)
    entity=create_entity(wiki)
    replacement=upload(sources,b'Replacement evidence',source_id=version['source_id'],expected_revision=1)
    observed=Event();release=Event();original=service._evidence
    def hold(connection,values):
        result=original(connection,values);observed.set()
        assert release.wait(10),'Controlled evidence reader was not released'
        return result
    monkeypatch.setattr(service,'_evidence',hold)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claiming=pool.submit(service.create_claim,actor,entity['id'],'observed',{'current':True},
            evidence_chunk_ids=[str(chunk['id'])],idempotency_key='raced-evidence')
        try:
            assert observed.wait(5)
            publishing=pool.submit(execute,sources,'source.extract',replacement['id'])
            with pytest.raises(TimeoutError):publishing.result(timeout=.2)
        finally:release.set()
        assertion=claiming.result(timeout=10);publishing.result(timeout=10)
    current=service.get_claim(actor,assertion['id'])
    assert current['evidence_stale'] and current['evidence'][0]['status']=='superseded'
    assert current['evidence'][0]['body'] is None


def test_exact_native_content_upgrade_verifier_uses_signed_http(knowledge_http):
    import runpy
    from pathlib import Path
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from czero_core.worker import Worker
    probe=runpy.run_path(str(Path(__file__).parents[1]/'current_content_fixture.py'))
    app,owner,*_=knowledge_http
    with TestClient(app,headers={'Authorization':'Bearer '+owner}) as http:
        def api(path,data=None,method=None,csrf=None):
            if '/versions' in path:Worker(knowledge_http[4],app.state.jobs.registry).tick()
            response=http.request(method or 'GET',path,json=data)
            return response.status_code,response.content,str(response.url)
        browser=SimpleNamespace(origin='https://c0.example.test',api=api);profile={'csrf_token':None}
        saved=probe['seed'](browser,profile)
        probe['verify'](browser,profile,saved)
