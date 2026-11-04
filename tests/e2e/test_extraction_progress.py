# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual 100-page progress and selective recovery in the browser."""
from collections import Counter
from urllib.parse import urlencode
from uuid import UUID
from pathlib import Path
from playwright.sync_api import expect
from czero_core.extraction import ExtractionError
from czero_core.extraction_queue import ExtractionQueue,ExtractionPool


def test_real_100_page_two_failure_progress_admin_retry_and_reader_boundaries(live,browser,monkeypatch):
    import czero_core.extraction_queue as implementation
    live.pause_worker()
    data=(Path(__file__).resolve().parents[1]/'fixtures/evidence/pipeline/readable-100.pdf').read_bytes()
    response=live.rest.post('/api/v1/sources/upload',params={'space_id':live.space},
        data={'title':'One hundred pages','media_type':'application/pdf','retain_original':'true'},files={'file':('pages.pdf',data)})
    assert response.status_code==202
    version=response.json()
    # Native producer handoff is deliberate; a browser session is never
    # promoted to native background authority by this acceptance fixture.
    auth=live.rest.get('/api/v1/me').json()
    # The trusted service and original store belong to this disposable app.
    from czero_core.access import AccessService
    from czero_core.database import Database
    from czero_core.identity import Actor,Role
    from sqlalchemy import text
    import os
    database=Database(os.environ['CZERO_TEST_DATABASE_URL'])
    try:
        with database.engine.connect() as c:
            account=c.execute(text('SELECT issuer,account_key FROM c0_accounts WHERE id=:id'),{'id':auth['id']}).mappings().one()
        access=AccessService(database,account['issuer'],UUID(str(account['account_key'])))
        queue=ExtractionQueue(database,access,live.originals,enabled=True).in_space(live.space)
        owner=Actor(UUID(auth['id']),Role.ADMIN)
        run=queue.enqueue(owner,version['id'],expected_generation=1)
        calls=Counter();parser=implementation.extract_page_isolated
        def parse(path,page):
            calls[page]+=1
            if page in (37,72):raise ExtractionError('parser_timeout')
            return parser(path,page)
        monkeypatch.setattr(implementation,'extract_page_isolated',parse)
        fail=queue.fail
        def parked_failure(claim,code):
            result=fail(claim,code)
            if claim.ordinal in (37,72):
                with database.engine.begin() as c:
                    c.execute(text("UPDATE c0_extraction_units SET available_at=clock_timestamp()+interval '1 day' WHERE id=:id"),{'id':claim.unit_id})
            return result
        monkeypatch.setattr(queue,'fail',parked_failure)
        ExtractionPool(queue).tick(max_units=20,budget_seconds=90)
        for _ in range(2):ExtractionPool(queue).tick(max_units=20,budget_seconds=90)
        # Freeze the two injected parser failures as terminal for deterministic
        # UI recovery. Actual timeout/backoff/kill fencing is covered by M2.
        with database.engine.begin() as c:
            c.execute(text("UPDATE c0_extraction_units SET state='failed' WHERE run_id=:id AND state='retry_wait'"),{'id':run['id']})
            c.execute(text("UPDATE c0_extraction_runs SET state='failed',error_code='parser_timeout',revision=revision+1 WHERE id=:id"),{'id':run['id']})
        status=queue.progress(owner,version['source_id'])
        assert status['run']['completed']==98 and status['run']['failed']==2
        browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':version['source_id']}))
        expect(browser.locator('#reader-extraction-status')).to_contain_text('98 of 100 units complete')
        expect(browser.locator('#reader-extraction-status')).to_contain_text('Failed')
        expect(browser.locator('#reader-document')).not_to_contain_text('Page 001')
        assert browser.locator('#retry-extraction').count()==0
        denied=live.rest.get('/api/v1/extraction-runs/'+str(run['id'])+'/units',params={'space_id':live.space},headers={'Authorization':'Bearer '+live.member})
        assert denied.status_code==403
        # Sign in as the actual owner in this same browser.
        browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
        browser.goto(live.origin+'/auth/login')
        browser.goto(live.origin+'/admin/work?'+urlencode({'space_id':live.space}))
        expect(browser.locator('#extraction-list')).to_contain_text(str(run['id']))
        browser.get_by_role('button',name='Inspect extraction',exact=True).click()
        expect(browser.locator('#extraction-summary')).to_contain_text('failed')
        browser.get_by_role('button',name='Next units',exact=True).click()
        expect(browser.locator('#extraction-units')).to_contain_text('Unit 37 · page 37 · failed')
        monkeypatch.setattr(implementation,'extract_page_isolated',lambda path,page:(calls.update([page]) or parser(path,page)))
        browser.get_by_role('button',name='Retry failed units',exact=True).click()
        expect(browser.locator('#extraction-summary')).to_contain_text('extracting')
        browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':version['source_id']}))
        expect(browser.locator('#reader-extraction-status')).to_contain_text('Processing')
        ExtractionPool(queue).tick(max_units=20,budget_seconds=90)
        assert calls[37]==calls[72]==2 and all(calls[p]==1 for p in range(1,101) if p not in (37,72))
        assert queue.progress(owner,version['source_id'])['state']=='ready'
        expect(browser.locator('#reader-extraction-status')).to_contain_text('Ready',timeout=10000)
        expect(browser.locator('#reader-document')).to_contain_text('Page 100',timeout=10000)
        # Mobile and keyboard inspection use actual controls and text.
        browser.set_viewport_size({'width':390,'height':844})
        assert browser.evaluate('document.documentElement.scrollWidth<=innerWidth')
    finally:
        database.close();live.resume_worker()


def test_source_tools_reindex_retains_current_until_complete_and_retires_citations(live,browser):
    body='# Retained original\n\nComplete original safety evidence.\n'
    version=live.upload(body,title='Explicit reindex fixture',retain_original='true')
    params={'space_id':live.space}
    path='/api/v1/source-documents/'+version['source_id']
    before=live.rest.get(path,params=params).json()
    document=before['parts'][0]['document_id']
    chunk=live.rest.get('/api/v1/documents/'+document+'/chunks',params=params).json()['chunks'][0]
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':version['source_id']}))
    expect(browser.locator('#reader-document')).to_contain_text('Complete original safety evidence.')
    expect(browser.locator('#source-reindex')).not_to_be_visible()
    browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'view':'tools'}))
    browser.get_by_role('button',name='Explicit reindex fixture',exact=True).click()
    details=browser.locator('#source-reindex')
    expect(details).to_be_visible()
    details.locator('summary').click()
    expect(details).to_contain_text('old citations become unavailable')
    live.pause_worker()
    try:
        browser.get_by_role('button',name='Reindex retained original',exact=True).click()
        expect(browser.locator('#source-status')).to_contain_text('Extraction queued')
        pending=live.rest.get(path,params=params).json()
        assert pending['body']==body and pending['revision_id']==before['revision_id']
        assert live.rest.get('/api/v1/chunks/'+chunk['id']+'/citation',params=params).status_code==200
    finally:
        live.resume_worker()
    expect(browser.locator('#source-status')).to_contain_text('Current content loaded',timeout=15000)
    after=live.rest.get(path,params=params).json()
    assert after['body']==body and after['revision_id']!=before['revision_id']
    assert after['parts'][0]['document_id']!=document
    retired=live.rest.get('/api/v1/chunks/'+chunk['id']+'/citation',params=params)
    assert retired.status_code==410 and retired.json()=={'detail':'content_superseded'}
