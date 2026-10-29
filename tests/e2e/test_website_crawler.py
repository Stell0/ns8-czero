# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from urllib.parse import urlencode

from playwright.sync_api import expect

from c0_projects.cli import bootstrap
from c0_projects.model import sha,source_config
from c0_projects.publish import publication_parts,sync_part,save_snapshot
from c0_projects.website import website


def html(marker):
    return '''<!doctype html><html><head><title>Documentation</title></head><body>
    <nav><a href="/manual/denied">Private navigation noise</a></nav>
    <main><h1>Controlled firewall manual</h1><p>BEGIN-CRAWLED-DOCUMENT</p>
    <h2>Configuration</h2><p>'''+marker+'''</p><table><tr><th>Port</th><th>Use</th></tr>
    <tr><td>443</td><td>HTTPS</td></tr></table><pre><code class="language-python">if ready:
        publish()
</code></pre><p>END-CRAWLED-DOCUMENT café 東京</p></main></body></html>'''


def test_real_crawl_publish_read_replace_and_unchanged(live,browser,documentation_site):
    site=documentation_site;site.state.body=html('OLD-ONLY-CRAWLER-MARKER')
    definition=source_config({'id':'website','adapter':'website','max_pages':20,'max_requests':30,
        'website':{'seeds':[site.origin+'/manual/article'],'allowed_roots':[site.origin+'/manual/'],
            'interval_ms':100,'language':'it','product':'Synthetic firewall','product_version':'14','manual':'Administrator manual'}})
    bootstrap(live.client,{'sources':[definition]},'explicit disposable website acceptance')
    def crawl_publish(show_pending=False):
        batch=website(definition,root=live.tmp)
        assert batch.status=='complete' and len(batch.items)==1
        item=batch.items[0]
        receipts=[sync_part(live.client,part,live.tmp/'website-publication.json',definition_hash=sha(definition),attempts=100,seconds=.1)
            for part in publication_parts(live.client,item)]
        if show_pending:
            browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':receipts[0]['source_id']}))
            expect(browser.locator('#reader-status')).to_have_text('Complete document unavailable: incomplete.',timeout=20000)
            expect(browser.locator('#reader-document')).to_be_empty()
        saved=save_snapshot(live.client,item,receipts)
        if show_pending:
            # The real reader polls the stable current link, without pinning an
            # unpublished part identity, and opens the complete parent.
            expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
            expect(browser.locator('#reader-document')).to_contain_text('BEGIN-CRAWLED-DOCUMENT')
        document=live.client.call('source_documents_get',logical_document_id=saved['id'])
        assert document['body'].encode()==item.content
        assert document['text_hash']==hashlib.sha256(item.content).hexdigest()
        return saved,document,batch
    first,document,_=crawl_publish(show_pending=True)
    chunk=live.client.call('document_chunks_list',document_id=document['parts'][0]['document_id'],limit=1)['chunks'][0]
    citation=live.client.call('citations_get',chunk_id=chunk['id'])
    browser.goto(live.origin+'/wiki?'+urlencode({'space_id':live.space}))
    browser.locator('#reader-sources').get_by_role('link',name='Controlled firewall manual',exact=True).click()
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
    body=browser.locator('#reader-document')
    expect(body.get_by_role('heading',name='Controlled firewall manual',exact=True)).to_be_visible()
    expect(body.locator('table')).to_have_count(1)
    expect(body.locator('pre code')).to_contain_text('publish()')
    expect(body).to_contain_text('BEGIN-CRAWLED-DOCUMENT')
    expect(body).to_contain_text('END-CRAWLED-DOCUMENT café 東京')
    expect(body).not_to_contain_text('Private navigation noise')
    expect(browser.locator('#reader-provenance')).to_contain_text('Synthetic firewall')
    expect(browser.locator('#reader-document-toc').get_by_role('link',name='Configuration',exact=True)).to_be_visible()
    assert browser.locator('#reader-version,#reader-history-panel').count()==0
    site.state.body=html('NEW-ONLY-CRAWLER-MARKER');site.state.etag='"generation-2"'
    second,updated,_=crawl_publish()
    assert second['id']==first['id'] and updated['revision_id']!=document['revision_id']
    browser.reload();expect(body).to_contain_text('NEW-ONLY-CRAWLER-MARKER',timeout=20000)
    expect(body).not_to_contain_text('OLD-ONLY-CRAWLER-MARKER')
    old=live.rest.get('/api/v1/chunks/'+chunk['id']+'/citation',params={'space_id':live.space})
    assert old.status_code==410 and old.json()['detail']=='content_superseded'
    retired=live.rest.get('/api/v1/source-versions/'+citation['version_id']+'/document',params={'space_id':live.space})
    assert retired.status_code==410
    assert live.client.call('sources_search',query='OLD-ONLY-CRAWLER-MARKER')['citations']==[]
    assert live.client.call('sources_search',query='NEW-ONLY-CRAWLER-MARKER')['citations']
    browser.goto(live.origin+'/search?'+urlencode({'space_id':live.space}))
    browser.locator('#knowledge-query').fill('OLD-ONLY-CRAWLER-MARKER')
    browser.locator('#knowledge-search-form button').click()
    expect(browser.locator('#knowledge-search-status')).to_have_text('0 results.',timeout=20000)
    expect(browser.locator('#knowledge-results')).to_have_text('')
    browser.locator('#knowledge-query').fill('NEW-ONLY-CRAWLER-MARKER')
    browser.locator('#knowledge-search-form button').click()
    browser.locator('#knowledge-results').get_by_role('link',name='Controlled firewall manual',exact=True).first.click()
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
    expect(browser.locator('#reader-document')).to_contain_text('NEW-ONLY-CRAWLER-MARKER')
    site.state.fail=True
    failed=website(definition,root=live.tmp)
    assert failed.status=='partial' and failed.items==[]
    assert live.client.call('source_documents_get',logical_document_id=second['id'])['revision_id']==updated['revision_id']
    site.state.fail=False
    stable,unchanged,batch=crawl_publish()
    assert stable['id']==second['id'] and unchanged['revision_id']==updated['revision_id']
    assert batch.cursor['metrics']['not_modified']==1
    assert not any(path=='/manual/denied' for path,_ in site.state.requests)


def test_website_private_scan_dry_run_resume_and_verified_cleanup(live,browser,documentation_site,monkeypatch):
    import json
    from types import SimpleNamespace
    from c0_ingest.client import C0
    from c0_ingest.state import read
    from c0_projects import cli
    site=documentation_site;site.state.body=html('SAVED-PENDING-SCAN-MARKER')
    definition=source_config({'id':'website-cli','adapter':'website','max_pages':20,'max_requests':30,
        'website':{'seeds':[site.origin+'/manual/article'],'allowed_roots':[site.origin+'/manual/'],'interval_ms':100}})
    bootstrap(live.client,{'sources':[definition]},'explicit disposable CLI approval')
    job=live.tmp/'private-cli-job';job.mkdir(mode=0o700);(job/'config').mkdir(mode=0o700)
    (job/'.env').write_text('C0_FIXTURE=synthetic\n');(job/'.env').chmod(0o600)
    path=job/'config/website.json';path.write_text(json.dumps({'schema_version':1,'server_url':live.origin+'/mcp',
        'project_space_id':live.space,'sources':[definition]}))
    config={**live.client.config,'space_name':'Synthetic documentation','poll_attempts':100,'poll_seconds':.1}
    monkeypatch.setattr(cli,'connection_settings',lambda _:config)
    writes=[]
    def factory(config,**kwargs):
        client=C0(config,**kwargs);close=client.close
        def finished():writes.append(client.writes);close()
        client.close=finished
        return client
    def run(operation,**changes):
        args=SimpleNamespace(group='sources',operation=operation,config=path,job=job,dry_run=False,apply=True,authorization_ref=None)
        for key,value in changes.items():setattr(args,key,value)
        return cli.run(args,client_factory=factory)
    assert run('scan')[0]['writes_c0']==0
    fetched=len(site.state.requests)
    site.state.body=html('CHANGED-AFTER-SCAN-MARKER');site.state.etag='"new-origin"'
    dry,code=run('sync',dry_run=True,apply=False)
    assert code==0 and dry['status']=='dry_run' and writes[-1]==0
    assert len(site.state.requests)==fetched and live.client.call('source_documents_list')['documents']==[]
    saved,code=run('resume');assert code==0 and saved['status']=='SAVED'
    assert len(site.state.requests)==fetched,'Resume recrawled instead of publishing the saved private scan'
    summary=live.client.call('source_documents_list')['documents'][0]
    current=live.client.call('source_documents_get',logical_document_id=summary['id'])
    assert 'SAVED-PENDING-SCAN-MARKER' in current['body'] and 'CHANGED-AFTER-SCAN-MARKER' not in current['body']
    assert {'publication_seconds','extraction_seconds','readback_seconds'}<=saved['timings'].keys()
    assert saved['crawl_metrics'][0]['conversion_seconds']>=0
    second,code=run('sync');assert code==0 and second['verified']==1
    current=live.client.call('source_documents_get',logical_document_id=summary['id'])
    assert 'CHANGED-AFTER-SCAN-MARKER' in current['body'] and 'SAVED-PENDING-SCAN-MARKER' not in current['body']
    scans=job/'data/c0-projects/scans'
    assert len(list(scans.iterdir()))==1 and read(job/'data/c0-projects/latest.json')['verified']
    assert len(list((job/'data/c0-projects/summaries').glob('*.json')))==1
    verified,code=run('verify');assert code==0 and verified['verified']==1 and writes[-1]==0
    assert run('status')[0]['connectors'][0]['data']['status']=='complete'
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':summary['id']}))
    expect(browser.locator('#reader-document')).to_contain_text('CHANGED-AFTER-SCAN-MARKER',timeout=20000)


def test_ingest_git_pinned_recipe_and_inert_code_reference(live,browser):
    import subprocess
    from c0_projects.recipe import PATHS,publish
    revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    payloads=[subprocess.check_output(['git','show',revision+':'+path]) for path in PATHS]
    before=live.client.writes
    preview=publish(live.client,revision,payloads,dry_run=True)
    assert preview['status']=='dry_run' and live.client.writes==before
    saved=publish(live.client,revision,payloads)
    assert saved['status']=='verified' and len(saved['documents'])==2
    repeated=publish(live.client,revision,payloads)
    assert [row['source_id'] for row in repeated['documents']]==[row['source_id'] for row in saved['documents']]
    code=saved['documents'][1]
    full=live.client.call('source_documents_get',logical_document_id=code['source_id'])
    assert revision in full['body'] and sha(payloads[1]) in full['body']
    assert 'Reference only.' in full['body'] and full['metadata']['provenance']['commit']==revision
    assert len(live.client.call('source_versions_list',source_id=code['source_id'])['versions'])==1
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':code['source_id']}))
    expect(browser.locator('#reader-document pre code')).to_contain_text('def website(',timeout=20000)
    assert browser.locator('#reader-document script,#reader-document iframe').count()==0
