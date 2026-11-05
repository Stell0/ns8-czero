# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real protected project and structured knowledge readback after REST writes."""
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import expect


def test_project_workflows_and_pinned_report_are_read_only(live, browser):
    space=live.second
    member=next(row for row in live.rest.get('/api/v1/access/accounts').json()['accounts'] if row['username']=='member')
    assert live.rest.put('/api/v1/spaces/'+str(space)+'/grants/'+member['id'],json={'role':'reader','expected_revision':0,'idempotency_key':'project-read'}).status_code==200
    browser.context.add_cookies([{'name':'fixture_persona','value':'owner','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    browser.goto(live.origin+'/projects?space_id='+str(space))
    probe=Path(__file__).resolve().parents[1].joinpath('project_browser_probe.js').read_text()
    assert browser.evaluate('('+probe+')')=={'initialized':True,'replay':True,'revision':2,'workflows':True,'monitoring':True,'reports':True}
    browser.context.add_cookies([{'name':'fixture_persona','value':'reader','url':live.origin}])
    browser.goto(live.origin+'/auth/login')
    writes=[]
    browser.on('request',lambda request:writes.append(request.url) if request.method!='GET' else None)
    browser.goto(live.origin+'/projects?space_id='+str(space))
    for text in ('<img src=x> Synthetic research','<script> synthetic topic','browser-source','partial','<script> synthetic queued investigation','phase_incomplete','no_material_update'):
        expect(browser.locator('main')).to_contain_text(text)
    report=browser.locator('main a[href*="/wiki/"][href*="revision=1"]')
    expect(report).to_be_visible()
    assert 'space_id='+str(space) in report.get_attribute('href')
    expect(browser.locator('main form, main textarea:not([readonly]), main img, main script')).to_have_count(0)
    report.click()
    expect(browser.locator('article')).to_contain_text('Queued research is incomplete.')
    browser.go_back()
    expect(browser.get_by_role('heading',name='<img src=x> Synthetic research',exact=True)).to_be_visible()
    browser.goto(live.origin+'/projects')
    expect(browser.locator('main')).to_contain_text('Choose a protected space configured as a research project.')
    expect(browser.get_by_text('<script> synthetic topic',exact=False)).to_have_count(0)
    assert writes==[]


def test_records_entities_relations_claims_and_annotations_are_literal_read_only(live,browser):
    params={'space_id':live.space}
    def post(path,data):
        response=live.rest.post('/api/v1/'+path,params=params,json=data)
        assert response.status_code==201,(path,response.status_code)
        return response.json()
    kind='browser-'+uuid4().hex[:8]
    post('object-types',{'name':kind,'label':'Browser inventory','schema':{'type':'object','properties':{'name':{'type':'string','maxLength':64},'count':{'type':'integer'}},'required':['name']},'unique_fields':['name']})
    record=post('objects',{'type_name':kind,'data':{'name':'<img src=x> Inventory','count':2}})
    linked=post('objects',{'type_name':kind,'data':{'name':'Linked inventory','count':3}})
    post('object-relations',{'source_id':record['id'],'target_id':linked['id'],'source_type':kind,'target_type':kind,'kind':'related-to'})
    entity=post('entities',{'kind':'system','label':'<script> Host','aliases':['Alternate host'],'idempotency_key':'browser-entity'})
    peer=post('entities',{'kind':'system','label':'Peer host','idempotency_key':'browser-peer'})
    post('knowledge/relations',{'source_id':entity['id'],'target_id':peer['id'],'kind':'connects-to','idempotency_key':'browser-relation'})
    reference=post('entities/'+entity['id']+'/references',{'target_kind':'object','target_id':record['id'],'idempotency_key':'browser-reference'})
    version=live.upload('# Claim evidence\n\nThis source supports the host claim.')
    document=live.rest.get('/api/v1/source-documents/'+version['source_id'],params=params).json()
    chunk=live.rest.get('/api/v1/documents/'+document['parts'][0]['document_id']+'/chunks',params=params).json()['chunks'][0]
    claim=post('claims',{'entity_id':entity['id'],'predicate':'observed','value':{'text':'<svg> Literal claim'},'evidence_chunk_ids':[chunk['id']],'idempotency_key':'browser-claim'})
    writes=[]
    browser.on('request',lambda request:writes.append(request.url) if request.method!='GET' else None)
    browser.goto(live.origin+'/explore/records/'+record['id']+'?space_id='+str(live.space))
    expect(browser.locator('main')).to_contain_text('<img src=x> Inventory')
    browser.get_by_role('link',name='related-to',exact=False).click()
    expect(browser.locator('main')).to_contain_text('Linked inventory')
    browser.goto(live.origin+'/explore/entities/'+entity['id']+'?space_id='+str(live.space))
    expect(browser.get_by_role('heading',name=entity['label'],exact=True)).to_be_visible()
    expect(browser.locator('main')).to_contain_text('Alternate host')
    expect(browser.get_by_role('link',name='connects-to',exact=False)).to_have_attribute('href','/explore/entities/'+peer['id']+'?space_id='+str(live.space))
    expect(browser.get_by_role('link',name=reference['label_snapshot'],exact=True)).to_be_visible()
    browser.get_by_role('link',name='observed',exact=True).click()
    expect(browser.locator('main')).to_contain_text('<svg> Literal claim')
    browser.locator('summary').filter(has_text='Annotations').click()
    expect(browser.locator('details[open]')).to_contain_text('applicability')
    expect(browser.locator('main img,main svg:not([aria-hidden]),main form,main textarea:not([readonly])')).to_have_count(0)
    browser.locator('main a[href*="/evidence/"]').click()
    expect(browser.locator('article')).to_contain_text('This source supports the host claim.')
    assert writes==[]
