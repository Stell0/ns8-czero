# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from c0_ingest.errors import C0Error
from c0_projects.model import source_config
from c0_projects.website import boundary,configuration,extract,normalize,website

HTML='''<!doctype html><html><head><title>Documentation</title>
<link rel="canonical" href="/it/docs/manual"/></head><body>
<nav><a href="/it/docs/next">Next chapter</a><a href="https://evil.example.org/manual">External</a></nav>
<article><div class="theme-doc-markdown"><h1>Firewall café 東京</h1><p>BEGIN-CONTENT</p>
<ol><li>First<ul><li>Nested</li></ul></li><li>Second</li></ol>
<table><tr><th>Port</th><th>Purpose</th></tr><tr><td>443</td><td>HTTPS</td></tr></table>
<pre><code class="language-python">if allowed:\n    connect()\n</code></pre><p><code>inline()</code>
<a href="../guide#install">Guide</a><img alt="Network diagram" src="./diagram.png"></p>
<div role="tablist"><button role="tab" id="linux">Linux</button><button role="tab" id="windows">Windows</button></div>
<div role="tabpanel" aria-labelledby="linux"><p>Linux variant</p></div>
<div role="tabpanel" aria-labelledby="windows" hidden><p>Windows variant</p></div>
<div class="admonition"><strong>Warning</strong><p>Verify the configuration.</p></div>
<script>bad()</script><button>Copy</button><footer>Navigation footer</footer><p>END-CONTENT</p></div></article></body></html>'''


def definition(**values):
    return source_config({'id':'manuals','adapter':'website','max_pages':20,'max_requests':40,
        'website':{'seeds':['https://docs.example.org/it/docs/manual'],
            'allowed_roots':['https://docs.example.org/it/docs/'],'profile':'docusaurus',**values}})


def test_markdown_keeps_structure_and_all_tab_variants():
    config=definition()['website']
    title,raw,canonical,links,metadata=extract(HTML.encode(),'https://docs.example.org/it/docs/manual',config)
    body=raw.decode()
    assert '# Firewall café 東京' in body and title=='Firewall café 東京'
    assert '| Port | Purpose |' in body and '| 443 | HTTPS |' in body
    assert '```python\nif allowed:\n    connect()' in body
    assert '`inline()`' in body and '1. First' in body and 'Nested' in body
    assert '### Linux' in body and '### Windows' in body and 'Windows variant' in body
    assert 'Network diagram' in body and 'https://docs.example.org/it/guide' in body
    assert 'Warning' in body and 'Navigation footer' not in body and 'bad()' not in body and 'Copy' not in body
    assert 'https://docs.example.org/it/docs/next' in links
    assert canonical=='https://docs.example.org/it/docs/manual' and metadata['source_type']=='website'


@pytest.mark.parametrize('url',['https://evil.example.org/it/docs/page','https://docs.example.org/en/docs/page',
    'https://docs.example.org/it/docs/%2e%2e/private','https://docs.example.org/it/docs-other/page',
    'https://'+'user:fixture-secret@docs.example.org/it/docs/page'])
def test_boundaries_are_exact(url):
    with pytest.raises(C0Error):boundary(url,definition()['website'])


def test_normalization_preserves_language_versions_queries_and_local_links():
    assert normalize('https://docs.example.org/it/v14/manual?edition=14&utm_source=mail#heading')=='https://docs.example.org/it/v14/manual?edition=14'
    assert normalize('https://docs.example.org/it/v8/manual')!='https://docs.example.org/it/v14/manual'
    with pytest.raises(C0Error):extract(HTML.replace('/it/docs/manual','https://evil.example.org/manual',1).encode(),
        'https://docs.example.org/it/docs/manual',definition()['website'])


class Site:
    def __init__(self):self.requests=0;self.downloaded=0;self.conditional=0;self.closed=False
    def close(self):self.closed=True
    def response(self,url,*,headers=None,allow_status=(200,),validate_url=None,**kwargs):
        validate_url(url);self.requests+=1
        if url.endswith('/robots.txt'):body=b'User-agent: *\nDisallow: /it/docs/denied\n';media='text/plain'
        elif url.endswith('/sitemap.xml'):
            body=b'<urlset><url><loc>https://docs.example.org/it/docs/manual</loc></url><url><loc>https://docs.example.org/it/docs/denied</loc></url></urlset>';media='application/xml'
        else:
            assert 'denied' not in url
            body=HTML.encode();media='text/html'
            if headers and headers.get('If-None-Match')=='"one"':
                self.conditional+=1
                return b'',url,media,{'status':304,'etag':'"one"','last_modified':''}
        self.downloaded+=len(body)
        return body,url,media,{'status':200,'etag':'"one"','last_modified':''}


def test_sitemap_navigation_robots_alias_dedup_and_304_reconversion(tmp_path):
    d=definition(exclude=['*/it/docs/next'])
    first=Site();batch=website(d,root=tmp_path,fetcher=first)
    assert batch.status=='complete' and len(batch.items)==1 and first.closed
    second=Site();again=website(d,root=tmp_path,fetcher=second)
    assert second.conditional==1 and again.items[0].content==batch.items[0].content
    changed=definition(exclude=['*/it/docs/next'],configuration_version='2')
    third=Site();upgraded=website(changed,root=tmp_path,fetcher=third)
    assert third.conditional==1 and upgraded.items[0].provenance['configuration_version']=='2'
    assert len(list((tmp_path/'data/c0-projects/website/manuals').glob('*.html')))==1


def test_empty_error_and_javascript_pages_do_not_become_replacements():
    for html in ('<main><h1>Page not found</h1></main>','<div id="app"></div>','<main><form><input type="password"></form></main>'):
        with pytest.raises(C0Error):extract(html.encode(),'https://docs.example.org/it/docs/manual',definition()['website'])


def test_heading_links_remain_useful_and_scripts_stay_inert():
    _,body,_,_,_=extract(HTML.encode(),'https://docs.example.org/it/docs/manual',definition()['website'])
    assert 'https://docs.example.org/it/guide#install' in body.decode()
    assert 'bad()' not in body.decode()


def test_short_valid_replacement_and_sphinx_structure():
    config=configuration({'seeds':['https://docs.example.org/en/v14/guide'],
        'allowed_roots':['https://docs.example.org/en/v14/'],'profile':'sphinx'})
    raw=b'<html><title>Guide</title><div role="main"><div class="body"><h1>Short guide</h1><p>Done.</p></div></div></html>'
    title,body,_,_,_=extract(raw,config['seeds'][0],config)
    assert title=='Short guide' and body==b'# Short guide\n\nDone.\n'


def test_limit_retains_frontier_and_resume_does_not_lose_discovery(tmp_path):
    config=definition(exclude=['*/it/docs/next'])
    config['max_requests']=2
    from c0_ingest.state import read
    from c0_ingest.errors import C0Error
    class Limited(Site):
        def response(self,*args,**kwargs):
            if self.requests>=2:raise C0Error('source_request_budget_exhausted')
            return super().response(*args,**kwargs)
    partial=website(config,root=tmp_path,fetcher=Limited())
    assert partial.status=='partial' and 'source_request_budget_exhausted' in partial.errors
    frontier=read(tmp_path/'data/c0-projects/website/manuals/frontier.json')
    assert frontier['pending'] and not frontier['complete']
    resumed=website(config,root=tmp_path,fetcher=Site())
    assert resumed.status=='complete' and len(resumed.items)==1


def test_denied_robots_and_network_failures_are_partial_without_items(tmp_path):
    from c0_projects.fetch import FetchError
    class Denied(Site):
        def response(self,url,**kwargs):
            self.requests+=1
            return b'',url,'text/plain',{'status':403}
    denied=website(definition(),root=tmp_path/'denied',fetcher=Denied())
    assert denied.items==[] and denied.cursor['metrics']['excluded']>=1
    class Busy(Site):
        def response(self,*args,**kwargs):raise FetchError('source_http_429','2099-01-01T00:00:00+00:00')
    failed=website(definition(),root=tmp_path/'busy',fetcher=Busy())
    assert failed.status=='partial' and failed.items==[] and failed.retry_after


def test_invalid_sitemap_is_reported_partial(tmp_path):
    class Invalid(Site):
        def response(self,url,**kwargs):
            if url.endswith('/sitemap.xml'):
                self.requests+=1
                return b'<urlset>broken',url,'application/xml',{'status':200}
            return super().response(url,**kwargs)
    batch=website(definition(),root=tmp_path,fetcher=Invalid())
    assert batch.status=='partial' and batch.items==[]


def test_private_scan_ownership_is_bounded_and_does_not_sweep_unrelated_jobs(tmp_path):
    from c0_ingest.state import atomic,read
    from c0_projects.website_state import remember_scan,verified_scan
    state=tmp_path/'state';unrelated=state/'scans'/'operator-data';unrelated.mkdir(parents=True)
    (unrelated/'body.md').write_text('Operator data stays private')
    manifest={'sources':[{'adapter':'website','items':[{'content_hash':'one'}]}]}
    first=state/'scans'/'a1';second=state/'scans'/'b2';third=state/'scans'/'c3'
    for directory in (first,second):
        directory.mkdir();atomic(directory/'manifest.json',manifest);(directory/'body.md').write_text('Current or pending body')
        remember_scan(state,directory,manifest)
    with pytest.raises(C0Error):remember_scan(state,third,manifest)
    verified_scan(state,second,manifest)
    assert not first.exists() and second.exists() and (unrelated/'body.md').read_text()=='Operator data stays private'
    assert 'body' not in read(state/'summaries/a1.json')
    assert read(state/'latest.json')['verified']


def test_changed_canonical_metadata_keeps_external_identity(tmp_path):
    d=definition(exclude=['*/it/docs/next'])
    first=website(d,root=tmp_path,fetcher=Site())
    class Changed(Site):
        def response(self,url,**kwargs):
            kwargs['headers']={}
            raw,final,media,head=super().response(url,**kwargs)
            if media=='text/html':
                raw=raw.replace(b'href="/it/docs/manual"',b'href="/it/docs/new-manual"',1)
                head={**head,'etag':'"two"','status':200}
            return raw,final,media,head
    again=website(d,root=tmp_path,fetcher=Changed())
    assert again.items[0].external_id==first.items[0].external_id
    assert again.items[0].canonical_url.endswith('/new-manual')


def test_canonical_cannot_merge_separately_approved_language_roots():
    config=definition(allowed_roots=['https://docs.example.org/it/docs/','https://docs.example.org/en/docs/'])['website']
    with pytest.raises(C0Error,match='partition'):
        extract(HTML.replace('href="/it/docs/manual"','href="/en/docs/manual"',1).encode(),
            'https://docs.example.org/it/docs/manual',config)


def test_robots_rates_cover_sitemaps_and_redirects_and_retry_is_persistent(tmp_path):
    from c0_projects.fetch import FetchError
    class Rates(Site):
        def __init__(self):super().__init__();self.delays=[]
        def response(self,url,**kwargs):
            if url.endswith('/robots.txt'):
                self.requests+=1
                return b'User-agent: *\nCrawl-delay: 3\nRequest-rate: 1/5\nDisallow: /it/docs/denied\n',url,'text/plain',{'status':200}
            self.delays.append((url,kwargs['interval'](url)))
            return super().response(url,**kwargs)
    rates=Rates();collected=website(definition(exclude=['*/it/docs/next']),root=tmp_path/'rates',fetcher=rates)
    assert collected.status=='complete'
    assert any(url.endswith('/sitemap.xml') for url,_ in rates.delays)
    assert all(delay==5 for _,delay in rates.delays)
    class Redirect(Site):
        def response(self,url,**kwargs):
            if url.endswith('/manual'):kwargs['validate_url']('https://docs.example.org/it/docs/denied')
            return super().response(url,**kwargs)
    denied=website(definition(),root=tmp_path/'redirect',fetcher=Redirect())
    assert denied.status=='partial' and denied.errors==['website_redirect_robots_denied'] and denied.items==[]
    class Busy(Site):
        def response(self,*args,**kwargs):raise FetchError('source_http_429','2099-01-01T00:00:00+00:00')
    blocked=tmp_path/'busy'
    assert website(definition(),root=blocked,fetcher=Busy()).retry_after
    retry=Site();deferred=website(definition(configuration_version='2'),root=blocked,fetcher=retry)
    assert deferred.status=='partial' and deferred.errors==['website_retry_deferred'] and retry.requests==0


def test_fetch_rechecks_shared_byte_budget_after_redirect_validation(monkeypatch):
    from c0_projects.fetch import Fetcher
    remaining=[4];delays=[]
    class Response:
        status=200
        def getheader(self,name,default=None):return '4' if name=='Content-Length' else default
        def read(self,*args):raise AssertionError('Oversized response must not be read')
    class Connection:
        sock=None
        def __init__(self,*args,**kwargs):pass
        def request(self,*args,**kwargs):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr('c0_projects.fetch.public_addresses',lambda *args:['1.1.1.1'])
    monkeypatch.setattr('c0_projects.fetch.http.client.HTTPSConnection',Connection)
    def validate(url):remaining[0]=2
    def interval(url):delays.append(url);return 0
    with pytest.raises(C0Error,match='content_length'):
        Fetcher(definition()).response('https://docs.example.org/it/docs/manual',validate_url=validate,
            interval=interval,remaining_bytes=lambda:remaining[0])
    assert len(delays)==1
