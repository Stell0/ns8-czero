# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Actual 100-page progress and selective recovery in the browser."""
from collections import Counter
from urllib.parse import urlencode
from uuid import UUID
from pathlib import Path
import pytest
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
        browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
        expect(browser.locator('main [role=status]')).to_contain_text('98 of 100 units complete')
        expect(browser.locator('main [role=status]')).to_contain_text('Failed')
        expect(browser.get_by_role('article')).to_have_count(0)
        expect(browser.get_by_role('button',name='Retry processing',exact=True)).to_have_count(0)
        denied=live.rest.get('/api/v1/extraction-runs/'+str(run['id'])+'/units',params={'space_id':live.space},headers={'Authorization':'Bearer '+live.member})
        assert denied.status_code==403
        # Sign in as the actual owner in this same browser.
        browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
        browser.goto(live.origin+'/auth/login')
        browser.goto(live.origin+'/admin/work?'+urlencode({'space_id':live.space}))
        browser.get_by_role('button',name='Background work Jobs',exact=True).click()
        browser.get_by_role('option',name='Extractions',exact=True).click()
        item=browser.locator('main li').filter(has_text=str(run['id']))
        item.get_by_role('button',name='Details',exact=True).click()
        details=browser.get_by_test_id('extraction-details')
        expect(details.locator('p[role=status]')).to_contain_text('failed')
        row=details.get_by_role('row').filter(has_text='page 37')
        expect(row).to_contain_text('failed')
        details.get_by_role('button',name='Next',exact=True).click()
        expect(details.get_by_role('row').filter(has_text='page 72')).to_contain_text('failed')
        monkeypatch.setattr(implementation,'extract_page_isolated',lambda path,page:(calls.update([page]) or parser(path,page)))
        details.get_by_role('button',name='Retry processing',exact=True).click()
        expect(details.locator('p[role=status]')).to_contain_text('extracting')
        browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
        expect(browser.locator('main [role=status]')).to_contain_text('Processing')
        ExtractionPool(queue).tick(max_units=20,budget_seconds=90)
        assert calls[37]==calls[72]==2 and all(calls[p]==1 for p in range(1,101) if p not in (37,72))
        assert queue.progress(owner,version['source_id'])['state']=='ready'
        expect(browser.locator('main [role=status]')).to_contain_text('Ready',timeout=10000)
        expect(browser.get_by_role('article')).to_contain_text('Page 100',timeout=10000)
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
    browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
    expect(browser.get_by_role('article')).to_contain_text('Complete original safety evidence.')
    expect(browser.get_by_role('button',name='Reprocess original',exact=True)).to_have_count(0)
    browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode({'space_id':live.space}))
    live.pause_worker()
    try:
        browser.get_by_role('button',name='Reprocess original',exact=True).click()
        dialog=browser.get_by_role('dialog')
        expect(dialog).to_contain_text('citations')
        dialog.get_by_role('button',name='Reprocess original',exact=True).click()
        expect(browser.locator('main [role=status]')).to_contain_text('Queued')
        pending=live.rest.get(path,params=params).json()
        assert pending['body']==body and pending['revision_id']==before['revision_id']
        assert live.rest.get('/api/v1/chunks/'+chunk['id']+'/citation',params=params).status_code==200
    finally:
        live.resume_worker()
    expect(browser.locator('main [role=status]')).to_contain_text('Ready',timeout=15000)
    after=live.rest.get(path,params=params).json()
    assert after['body']==body and after['revision_id']!=before['revision_id']
    assert after['parts'][0]['document_id']!=document
    retired=live.rest.get('/api/v1/chunks/'+chunk['id']+'/citation',params=params)
    assert retired.status_code==410 and retired.json()=={'detail':'content_superseded'}


@pytest.mark.parametrize('retain_original', [False, True])
def test_source_failed_original_retry_and_queued_extraction_cancel(live,browser,retain_original):
    """Recovery buttons use actual revisions and retain Reader boundaries."""
    import os
    from sqlalchemy import text
    from czero_core.access import AccessService
    from czero_core.database import Database
    from czero_core.identity import Actor,Role
    params={'space_id':live.space}
    browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    response=live.rest.post('/api/v1/sources/upload',params=params,
        data={'title':'Unreadable original','media_type':'text/plain','retain_original':str(retain_original).lower()},
        files={'file':('invalid.txt',b'\xff\xfeinvalid')})
    assert response.status_code==202
    version=response.json()
    browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode(params))
    expect(browser.locator('main div[role=status]')).to_contain_text('Failed',timeout=15000)
    # The API preserves failed staging for recovery, independently of the user's
    # original-retention choice. Browser downloads honor that explicit choice.
    original='/api/v1/source-versions/'+version['id']+'/original'
    assert live.rest.get(original,params=params).status_code==200
    for persona in ('reader','owner'):
        browser.context.add_cookies([{'name':'fixture_persona','value':persona,'url':live.origin}])
        browser.goto(live.origin+'/auth/login')
        browser.goto(live.origin+'/sources/'+version['source_id']+'?'+urlencode(params))
        expect(browser.locator('main div[role=status]')).to_contain_text('Failed')
        link=browser.get_by_role('link',name='Download original',exact=True)
        if retain_original and persona=='owner':
            expect(link).to_be_visible()
            response=browser.request.get(live.origin+link.get_attribute('href'))
            assert response.status==200 and response.body()==b'\xff\xfeinvalid'
        else:
            expect(link).to_have_count(0)
            expect(browser.get_by_text('The original file is unavailable.',exact=True)).to_be_visible()
        expect(browser.get_by_role('article')).to_have_count(0)
        if persona=='reader':
            # Unpublished staging versions are private to writers, including
            # retained originals. Never advertise a download the API denies.
            assert browser.request.get(live.origin+original+'?'+urlencode(params)).status==404
            expect(browser.get_by_role('button',name='Retry processing',exact=True)).to_have_count(0)
            expect(browser.get_by_role('button',name='Upload replacement',exact=True)).to_have_count(0)
    expect(browser.get_by_role('article')).to_have_count(0)
    live.pause_worker()
    try:
        browser.get_by_role('button',name='Retry processing',exact=True).click()
        expect(browser.locator('main div[role=status]')).to_contain_text('Queued')
        current=live.rest.get('/api/v1/sources/'+version['source_id']+'/versions',params=params).json()['versions'][0]
        assert current['generation']==version['generation']+1
    finally:live.resume_worker()
    expect(browser.locator('main div[role=status]')).to_contain_text('Failed',timeout=15000)
    # A registered producer prepares a pending page run; cancellation itself is
    # the website's ordinary revision-bound operation, with no worker race.
    live.pause_worker()
    database=Database(os.environ['CZERO_TEST_DATABASE_URL'])
    try:
        data=(Path(__file__).resolve().parents[1]/'fixtures/evidence/pipeline/readable-100.pdf').read_bytes()
        response=live.rest.post('/api/v1/sources/upload',params=params,
            data={'title':'Cancelled pending extraction','media_type':'application/pdf','retain_original':'true'},
            files={'file':('pages.pdf',data)})
        assert response.status_code==202
        pending=response.json();auth=live.rest.get('/api/v1/me').json()
        with database.engine.connect() as connection:
            account=connection.execute(text('SELECT issuer,account_key FROM c0_accounts WHERE id=:id'),{'id':auth['id']}).mappings().one()
        access=AccessService(database,account['issuer'],UUID(str(account['account_key'])))
        queue=ExtractionQueue(database,access,live.originals,enabled=True).in_space(live.space)
        owner=Actor(UUID(auth['id']),Role.ADMIN)
        run=queue.enqueue(owner,pending['id'],expected_generation=1)
        browser.goto(live.origin+'/sources/'+pending['source_id']+'?'+urlencode(params))
        expect(browser.locator('main div[role=status]')).to_contain_text('Queued')
        browser.get_by_role('button',name='Cancel processing',exact=True).click()
        expect(browser.locator('main div[role=status]')).to_contain_text('Cancelled')
        result=queue.progress(owner,pending['source_id'])
        assert result['run']['id']==run['id'] and result['run']['error_code']=='cancelled'
        expect(browser.get_by_role('article')).to_have_count(0)
        expect(browser.get_by_role('button',name='Cancel processing',exact=True)).to_have_count(0)
    finally:
        database.close();live.resume_worker()
