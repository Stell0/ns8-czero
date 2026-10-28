# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Release-blocking browser acceptance: actual application, database and worker."""
import hashlib
import json
import time
from urllib.parse import urlencode

from playwright.sync_api import expect

MARKDOWN='''# Synthetic administrator manual

BEGIN-DOCUMENT-MARKER

Read the original, complete configuration below.

## Firewall configuration

Several paragraphs precede the configuration. This is retained source evidence.

### Required ports

| Port | Protocol | Purpose |
| --- | --- | --- |
| 443 | TCP | Web |
| 5060 | UDP | Signalling |
| 10000 | UDP | Media |

```ini
[firewall]
  allow_https = true
  allow_media = true
```

- Apply the configuration.
- Verify connectivity.

> A quoted observation remains evidence.

[Ordinary reference](https://example.org/configuration)

<script>window.documentExecuted=true</script>
<img src="https://example.org/tracker" onerror="window.documentExecuted=true">
[Unsafe link](javascript:alert(1))

## Verify the configuration

MIDDLESEARCHZEUS appears in the middle of this full document.

Continue reading after the matched passage.

## Final checks

END-DOCUMENT-MARKER
'''


def large_body():
    configuration='  allow_media = true\n'+''.join(f'  # retained cross-part configuration line {i:05d}\n' for i in range(3200))
    original=MARKDOWN.replace('  allow_media = true\n',configuration)
    return original+'\n\n'+''.join(f'Paragraph {i:05d}: unique retained configuration evidence.\n\n' for i in range(6500))+'\n## Last storage part\n\nLAST-PART-MARKER\n'


def open_document(page,live,identifier,revision=None,chunk=None):
    query={'space_id':live.space,'document':identifier}
    if revision:query['snapshot']=revision
    if chunk:query['chunk']=chunk
    page.goto(live.origin+'/sources?'+urlencode(query))
    expect(page.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)


def assert_markdown(page):
    body=page.locator('#reader-document')
    expect(body.get_by_role('heading',name='Firewall configuration',exact=True)).to_be_visible()
    expect(body.locator('table')).to_have_count(1)
    expect(body.locator('tbody tr')).to_have_count(3)
    expect(body.locator('pre code')).to_contain_text('  allow_https = true')
    expect(body.locator('ul li')).to_have_count(2)
    expect(body.locator('blockquote')).to_contain_text('quoted observation')
    expect(body).to_contain_text('BEGIN-DOCUMENT-MARKER')
    expect(body).to_contain_text('END-DOCUMENT-MARKER')
    expect(body.locator('script,img,iframe,object,embed')).to_have_count(0)
    expect(body.locator('a[href^="javascript:"],a[href^="data:"]')).to_have_count(0)
    assert page.evaluate('window.documentExecuted') is None
    page.locator('#reader-document-toc').get_by_role('link',name='Firewall configuration',exact=True).click()
    heading=body.get_by_role('heading',name='Firewall configuration',exact=True)
    assert page.evaluate('location.hash')=='#'+heading.get_attribute('id')
    expect(page.locator('#reader-provenance')).to_contain_text('Imported source')
    expect(page.locator('#reader-document-version')).to_contain_text('ready')
    expect(page.get_by_role('link',name='Canonical document',exact=True)).to_have_attribute('href','https://example.org/manual')


def test_complete_markdown_and_plain_text(live,browser):
    version=live.upload(MARKDOWN)
    live.client.call('wiki_pages_create',data={'slug':'authored-article','title':'Authored Wiki article','body':'# Authored knowledge\n\nWiki remains separate.','idempotency_key':'article'})
    live.upload('## Literal heading\n\n<script>literal</script>','Literal text',media='text/plain')
    # Genuine Knowledge -> Sources -> title navigation.
    browser.goto(live.origin+'/wiki?'+urlencode({'space_id':live.space}))
    expect(browser.locator('#reader-content').get_by_role('link',name='Authored Wiki article',exact=True)).to_be_visible()
    browser.get_by_role('navigation',name='Knowledge categories').get_by_role('link',name='Sources',exact=True).click()
    browser.locator('#reader-sources').get_by_role('link',name='Firewall manual',exact=True).click()
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
    assert_markdown(browser)
    expect(browser.locator('#reader-document-version')).to_contain_text('Version 1')
    browser.locator('#reader-sources').get_by_role('link',name='Literal text',exact=True).click()
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.')
    expect(browser.locator('#reader-document')).to_have_text('## Literal heading\n\n<script>literal</script>')
    expect(browser.locator('#reader-document h1,#reader-document h2,#reader-document h3')).to_have_count(0)
    hostile={'toString':None,'valueOf':None}
    malformed=live.upload(MARKDOWN,'Malformed optional metadata',metadata=json.dumps({
        'canonical_url':hostile,'published_at':hostile,'provenance':{'path':['Configuration',hostile]}}))
    open_document(browser,live,malformed['source_id'])
    expect(browser.locator('#reader-document')).to_contain_text('END-DOCUMENT-MARKER')
    expect(browser.locator('#reader-document').get_by_role('heading',name='Firewall configuration',exact=True)).to_be_visible()
    expect(browser.get_by_role('link',name='Canonical document',exact=True)).to_have_count(0)


def test_legacy_multipart_is_one_exact_complete_document(live,browser):
    body=large_body();snapshot,receipts=live.publish(body)
    assert len(body.encode())>262144 and len(receipts)>=3
    first_part=live.client.call('documents_get',version_id=receipts[0]['version_id'])
    assert first_part['body'].count('```')==1, 'The real storage boundary must split the code fence'
    started=time.perf_counter()
    browser.goto(live.origin+'/wiki?'+urlencode({'space_id':live.space}))
    links=browser.locator('#reader-sources').get_by_role('link',name='Complete legacy manual',exact=True)
    expect(links).to_have_count(1)
    directory_ms=(time.perf_counter()-started)*1000
    browser.add_init_script("window.documentRenderTicks=[];setInterval(()=>{documentRenderTicks.push(performance.now());if(documentRenderTicks.length>1000)documentRenderTicks.shift();},16);")
    started=time.perf_counter()
    links.click();expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
    load_ms=(time.perf_counter()-started)*1000
    text=browser.locator('#reader-document').text_content()
    assert text.count('BEGIN-DOCUMENT-MARKER')==text.count('END-DOCUMENT-MARKER')==text.count('LAST-PART-MARKER')==1
    assert text.index('BEGIN-DOCUMENT-MARKER')<text.index('Paragraph 00000')<text.index('Paragraph 03000')<text.index('Paragraph 06499')<text.index('LAST-PART-MARKER')
    for i in range(6500):assert text.count(f'Paragraph {i:05d}:')==1
    # Read the actual selected API response in this authenticated browser; compare
    # its original Markdown bytes, not rendered text or overlapping search chunks.
    actual=browser.evaluate('''async id=>{
      const response=await fetch(window.C0Space.apiURL('source-documents/'+id),{cache:'no-store'});
      if(!response.ok)throw Error('Full document denied');
      const doc=await response.json();
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(doc.body)))).map(b=>b.toString(16).padStart(2,'0')).join('');
      return {body:doc.body,hash,text_hash:doc.text_hash,parts:doc.parts.length};
    }''',snapshot['id'])
    assert actual['body']==body and actual['hash']==actual['text_hash']==hashlib.sha256(body.encode()).hexdigest()
    assert actual['parts']==len(receipts)
    expect(browser.locator('#reader-document table')).to_have_count(1)
    expect(browser.locator('#reader-document pre code')).to_contain_text('allow_https = true')
    expect(browser.locator('#reader-document pre code')).to_contain_text('configuration line 03199')
    browser.locator('#reader-document-toc').get_by_role('link',name='Last storage part',exact=True).click()
    expect(browser.locator('#reader-document').get_by_role('heading',name='Last storage part',exact=True)).to_be_in_viewport()
    metrics=browser.evaluate("performance.getEntriesByType('resource').filter(e=>e.name.includes('/source-documents/')).map(e=>({duration_ms:e.duration,bytes:e.decodedBodySize}))")
    responsiveness=browser.evaluate("(()=>{const entry=performance.getEntriesByName('c0-document-render').at(-1),ticks=documentRenderTicks.filter(t=>t>=entry.startTime && t<=entry.startTime+entry.duration);return {render_ms:entry.duration,ticks:ticks.length,max_tick_gap_ms:Math.max(0,...ticks.slice(1).map((t,i)=>t-ticks[i]))};})()")
    assert responsiveness['ticks']>=2, 'The real browser must service timers while rendering'
    print(json.dumps({'fixture_bytes':len(body.encode()),'directory_ms':round(directory_ms,2),'initial_document_load_ms':round(load_ms,2),'responsiveness':responsiveness,'full_document_resources':metrics}))


def test_updates_history_shrink_and_historical_part_citation(live,browser):
    body=large_body();first,receipts=live.publish(body)
    full=live.client.call('source_documents_get',logical_document_id=first['id'])
    doc=live.client.call('documents_get',version_id=receipts[-1]['version_id'])
    chunk=live.client.call('document_chunks_list',document_id=doc['id'],limit=1)['chunks'][0]
    citation=live.client.call('citations_get',chunk_id=chunk['id'])
    short='# Updated manual\n\nCHANGED-CONTENT-MARKER\n\nNo obsolete parts.\n'
    second,_=live.publish(short)
    assert second['id']==first['id']
    open_document(browser,live,second['id'])
    expect(browser.locator('#reader-document')).to_contain_text('CHANGED-CONTENT-MARKER')
    expect(browser.locator('#reader-document')).not_to_contain_text('LAST-PART-MARKER')
    browser.select_option('#reader-version',full['revision_id'])
    expect(browser.locator('#reader-status')).to_have_text('Complete document loaded.',timeout=20000)
    expect(browser.locator('#reader-document')).to_contain_text('LAST-PART-MARKER')
    expect(browser.locator('#reader-document')).not_to_contain_text('CHANGED-CONTENT-MARKER')
    # Preserve the pre-existing source/version/chunk URL, with no latest-version substitution.
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'source':citation['source_id'],'version':citation['version_id'],'chunk':citation['chunk_id']}))
    expect(browser.locator('#reader-excerpt')).to_contain_text(citation['body'],timeout=20000)
    expect(browser.locator('#reader-document')).to_contain_text('Paragraph 00000')
    expect(browser.locator('#reader-document')).to_contain_text('LAST-PART-MARKER')
    assert browser.locator('#reader-version').input_value()==full['revision_id']


def test_search_navigates_to_full_historical_evidence(live,browser):
    body=large_body().replace('MIDDLESEARCHZEUS','Retained observation')
    body=body.replace('Paragraph 03250:','MIDDLESEARCHZEUS Paragraph 03250:')
    snapshot,receipts=live.publish(body)
    assert len(receipts)>=3
    live.legacy_metadata(receipts)
    browser.goto(live.origin+'/search?'+urlencode({'space_id':live.space}))
    browser.locator('#knowledge-query').fill('MIDDLESEARCHZEUS')
    browser.locator('#knowledge-search-form button').click()
    browser.locator('#knowledge-results').get_by_role('link',name='Complete legacy manual',exact=True).first.click()
    expect(browser.locator('#reader-excerpt')).to_contain_text('MIDDLESEARCHZEUS',timeout=20000)
    expect(browser.locator('#reader-document')).to_contain_text('BEGIN-DOCUMENT-MARKER')
    expect(browser.locator('#reader-document')).to_contain_text('Paragraph 00000')
    expect(browser.locator('#reader-document')).to_contain_text('Paragraph 06499')
    expect(browser.locator('#reader-document')).to_contain_text('LAST-PART-MARKER')
    from urllib.parse import parse_qs,urlsplit
    selected=parse_qs(urlsplit(browser.url).query)
    citation=live.client.call('citations_get',chunk_id=selected['chunk'][0])
    assert citation['source_id']==selected['source'][0] and citation['version_id']==selected['version'][0]
    browser.locator('#reader-source-details summary').click()
    expect(browser.locator('#reader-source-metadata')).to_contain_text(citation['chunk_id'])
    expect(browser.locator('#reader-source-metadata')).to_contain_text(citation['content_hash'])
    part=next(row for row in receipts if row['version_id']==citation['version_id'])
    doc=live.client.call('documents_get',version_id=part['version_id'])
    assert citation['start_offset']>0 and citation['end_offset']<len(doc['body'])


def test_protected_spaces_logout_and_late_revoked_response(live,browser):
    private=live.upload(MARKDOWN)
    foreign=live.upload('# Other protected evidence\n\nOTHER-SPACE-SECRET','Other protected manual',space=live.second)
    denied=live.rest.get('/api/v1/source-documents/'+foreign['source_id'],params={'space_id':live.second},headers={'Authorization':'Bearer '+live.member})
    assert denied.status_code==403 and 'OTHER-SPACE-SECRET' not in denied.text
    open_document(browser,live,private['source_id'])
    shared=browser.locator('#space-selector option').filter(has_text='(shared)').get_attribute('value')
    browser.select_option('#space-selector',shared)
    browser.wait_for_url(lambda url:'space_id' not in url)
    expect(browser.locator('#space-status')).to_contain_text('Shared space')
    expect(browser.locator('#reader-document')).not_to_contain_text('BEGIN-DOCUMENT-MARKER')
    # A genuine server response is held after authorization/readback, simulating
    # a slow connection. Revocation and Refresh access must invalidate it.
    live.delay.id=private['source_id']
    # Observe the genuine late body independently: the application's correct
    # generation guard rejects its Response before consuming the body stream.
    browser.add_init_script("""(() => {
      const original=window.fetch;window.lateDocumentRead=null;
      window.fetch=async(...args)=>{
        const response=await original(...args);
        if(new URL(response.url).pathname==='/api/v1/source-documents/'+"""+json.dumps(private['source_id'])+""")
          response.clone().arrayBuffer().then(body=>{window.lateDocumentRead={status:response.status,bytes:body.byteLength};});
        return response;
      };
    })();""")
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':private['source_id']}),wait_until='domcontentloaded')
    assert live.delay.captured.wait(10)
    assert live.rest.put(live.grant_path,json={'role':None,'expected_revision':1,'idempotency_key':'revoke'}).status_code==200
    browser.get_by_role('button',name='Refresh access',exact=True).click()
    expect(browser.locator('#reader-root')).to_be_hidden()
    live.delay.release.set()
    browser.wait_for_function("window.lateDocumentRead?.status===200 && window.lateDocumentRead.bytes>0",timeout=10000)
    browser.wait_for_function("document.getElementById('reader-root').hidden && document.getElementById('reader-document').textContent===''")
    expect(browser.locator('#reader-document')).to_have_text('')
    expect(browser.locator('#reader-provenance')).to_have_text('')
    expect(browser.locator('#reader-source-metadata')).to_have_text('')
    assert live.rest.put(live.grant_path,json={'role':'reader','expected_revision':2,'idempotency_key':'regrant'}).status_code==200
    live.delay.id=None
    open_document(browser,live,private['source_id'])
    browser.get_by_role('link',name='Account',exact=True).click()
    browser.locator('#sign-out').click()
    expect(browser.get_by_role('heading',name='Signed out of disposable provider')).to_be_visible()
    browser.goto(live.origin+'/sources?'+urlencode({'space_id':live.space,'document':private['source_id']}))
    expect(browser.locator('#reader-document')).to_have_text('')
    assert browser.locator('#reader-root').is_hidden()


def test_large_markdown_prefers_one_real_rest_upload(live,browser):
    body=large_body()
    first,receipts=live.publish(body,legacy=False)
    assert len(receipts)==1
    second,repeated=live.publish(body,legacy=False)
    assert first==second and receipts[0]['version_id']==repeated[0]['version_id']
    assert len(live.client.call('source_versions_list',source_id=receipts[0]['source_id'])['versions'])==1
    open_document(browser,live,first['id'])
    expect(browser.locator('#reader-document')).to_contain_text('BEGIN-DOCUMENT-MARKER')
    expect(browser.locator('#reader-document')).to_contain_text('LAST-PART-MARKER')
    expect(browser.locator('#reader-document pre code')).to_contain_text('allow_https = true')
