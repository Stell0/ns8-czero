# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
import pytest
from czero_core.source_collectors import validate,collect
from czero_core.source_http import CollectionError


@pytest.mark.parametrize('kind,config',[
    ('shell',{}),('github',{'repositories':['a/b'],'command':'touch anything'}),
    ('github',{'repositories':['a/b'],'include':['anything']}),
    ('github',{'repositories':['a/b'],'github_token':'synthetic-unit-only-token'}),
    ('github',{'repositories':['a/b'],'max_requests':True}),
    ('github',{'repositories':['https://example.org']}),
    ('website',{'website':{'seeds':['https://example.org/docs'],'allowed_roots':['https://elsewhere.org']}}),
])
def test_invalid_configuration_rejects_before_fetch(kind,config):
    with pytest.raises((ValueError,CollectionError)):validate(kind,config)


class Fetch:
    def __init__(self,responses):self.responses=responses;self.requests=0;self.closed=False
    def response(self,url,**kwargs):
        self.requests+=1
        if kwargs.get('validate_url'):kwargs['validate_url'](url)
        response=self.responses[url]
        return response[0],url,response[1],{'status':response[2] if len(response)>2 else 200}
    def get(self,url):return self.response(url)[:3]
    def close(self):self.closed=True


def encoded(value):return json.dumps(value).encode(),'application/json'


def test_github_file_selection_and_cursor_resume():
    root='https://api.github.com/repos/a/b'
    fetch=Fetch({root:encoded({'id':23,'private':False}),root+'/commits/HEAD':encoded({'sha':'abcdef'}),
        root+'/git/trees/abcdef?recursive=1':encoded({'tree':[{'type':'blob','path':'docs/first.md','sha':'one'},{'type':'blob','path':'docs/second.md','sha':'two'},{'type':'blob','path':'private.txt','sha':'three'},{'type':'blob','path':'docs/logo.png','sha':'image'}]}),
        root+'/git/blobs/one':encoded({'content':base64.b64encode(b'first complete document').decode()}),
        root+'/git/blobs/two':encoded({'content':base64.b64encode(b'second complete document').decode()})})
    config={'repositories':['a/b'],'max_items':1}
    first,cursor,complete=collect('github',config,{},fetcher=fetch)
    assert not complete and len(first)==1 and fetch.closed
    second,_,complete=collect('github',config,cursor,fetcher=fetch)
    assert complete and second[0]['body']==b'second complete document' and first[0]['key']!=second[0]['key']


def test_website_robots_exclusion_and_bounded_resume():
    root='https://example.org/docs'
    responses={'https://example.org/robots.txt':(b'User-agent: *\nDisallow: /docs/denied','text/plain'),
        root:(b'<article><h1>First</h1><p>Evidence</p><a href="/docs/second">Next</a><a href="/docs/denied">Denied</a><a href="https://elsewhere.org/">Outside</a></article>','text/html'),
        root+'/second':(b'<article><h1>Second</h1><p>More evidence</p></article>','text/html')}
    config={'website':{'seeds':[root],'allowed_roots':[root]},'max_items':1}
    first,cursor,done=collect('website',config,{},fetcher=Fetch(responses))
    assert not done and len(first)==1
    second,cursor,done=collect('website',config,cursor,fetcher=Fetch(responses))
    assert second[0]['title']=='Second'
    _,_,done=collect('website',config,cursor,fetcher=Fetch(responses))
    assert done


def test_private_repository_rejected():
    fetch=Fetch({'https://api.github.com/repos/a/b':encoded({'id':23,'private':True})})
    with pytest.raises(CollectionError,match='github_repository_unavailable'):
        collect('github',{'repositories':['a/b']},{},fetcher=fetch,github_token='synthetic-unit-only-token')
    assert fetch.closed
    class Missing(Fetch):
        def get(self,url):raise CollectionError('source_http_404')
    missing=Missing({})
    with pytest.raises(CollectionError,match='github_repository_unavailable'):
        collect('github',{'repositories':['a/b']},{},fetcher=missing,github_token='synthetic-unit-only-token')
    assert missing.closed


def test_core_public_transport_denies_any_private_dns_peer(monkeypatch):
    from czero_core.source_http import public_addresses
    monkeypatch.setattr('czero_core.source_http.socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('1.1.1.1',443)),(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(CollectionError,match='source_private_destination_denied'):public_addresses('example.org',443,1)


def test_sitemap_robots_and_exclusions_apply_before_collection():
    config={'website':{'seeds':['https://example.org/docs'],'allowed_roots':['https://example.org/docs'],'sitemaps':['https://example.org/private.xml']}}
    fetch=Fetch({'https://example.org/robots.txt':(b'User-agent: *\nDisallow: /private.xml\nDisallow: /docs','text/plain')})
    items,_,complete=collect('website',config,{},fetcher=fetch)
    assert items==[] and complete and fetch.requests==1


def test_native_worker_reserves_time_for_source_collection(monkeypatch,capsys):
    from czero_core import worker
    recorded=[]
    class Database:
        def close(self):pass
    class Worker:
        def __init__(self,*args):pass
        def tick(self,**kwargs):recorded.append(kwargs);return 0
    monkeypatch.setattr(worker,'Database',Database)
    monkeypatch.setattr(worker,'Worker',Worker)
    assert worker.main(budget_seconds=60)==0
    assert recorded==[{'budget_seconds':60}]
    assert json.loads(capsys.readouterr().out)=={'processed':0}


def test_http_preview_reads_title_without_article_conversion(monkeypatch):
    monkeypatch.setattr('czero_core.source_collectors.extract',lambda *args:pytest.fail('Article conversion belongs in the bounded worker'))
    config={'website':{'seeds':['https://example.org/docs'],'allowed_roots':['https://example.org/docs']}}
    fetch=Fetch({'https://example.org/robots.txt':(b'','text/plain',404),'https://example.org/docs':(b'<title>Original title</title><article>Actual remote body</article>','text/html')})
    items,_,_=collect('website',config,{},fetcher=fetch,preview=True)
    assert items==[{'title':'Original title','metadata':{'original_url':'https://example.org/docs'}}]


def test_source_worker_failure_does_not_log_configuration_or_traceback(monkeypatch,caplog):
    from czero_app.worker import update_sources
    monkeypatch.setenv('CZERO_OIDC_ISSUER','https://idp.example.test')
    monkeypatch.setenv('CZERO_OWNER_LDAP_UUID','11111111-1111-4111-8111-111111111111')
    def unavailable():raise RuntimeError('PRIVATE_WORKER_CONFIGURATION_MARKER')
    monkeypatch.setattr('czero_core.database.Database',unavailable)
    update_sources()
    assert 'C0 source update unavailable' in caplog.text
    assert 'PRIVATE_WORKER_CONFIGURATION_MARKER' not in caplog.text and 'Traceback' not in caplog.text


@pytest.mark.parametrize('ref',['..','../other','refs//heads/main'])
def test_github_reference_cannot_escape_its_api_namespace(ref):
    with pytest.raises(ValueError):validate('github',{'repositories':['synthetic/example'],'ref':ref})


def test_operator_github_credential_never_reaches_other_origins(monkeypatch):
    from czero_core.source_http import Fetcher
    calls=[]
    class Response:
        status=200
        def getheader(self,name,default=None):
            return {'Content-Length':'2','Content-Type':'application/json','Location':'https://other.example.org/leak'}.get(name,default)
        def read(self,limit):return b'{}'
    class Connection:
        sock=None
        def __init__(self,host,*args,**kwargs):self.host=host
        def request(self,method,path,headers):
            self.path=path;calls.append((self.host,headers))
        def getresponse(self):
            response=Response()
            if self.path=='/redirect':response.status=302
            return response
        def close(self):pass
    monkeypatch.setattr('czero_core.source_http.public_addresses',lambda *args:['1.1.1.1'])
    monkeypatch.setattr('czero_core.source_http.http.client.HTTPSConnection',Connection)
    monkeypatch.setattr('czero_core.source_http.http.client.HTTPConnection',Connection)
    config={'timeout':1,'max_requests':6,'max_bytes':128}
    fetcher=Fetcher(config,accept_json=True,github_token='synthetic-unit-only-github-token')
    try:
        for url in ('https://api.github.com/repos/synthetic/example','https://example.org/docs',
                    'http://api.github.com/repos/synthetic/example'):
            fetcher.get(url)
        with pytest.raises(CollectionError,match='source_cross_host_redirect_denied'):
            fetcher.get('https://api.github.com/redirect')
    finally:fetcher.close()
    assert calls[0][1]['Authorization']=='Bearer synthetic-unit-only-github-token'
    assert all('Authorization' not in headers for host,headers in calls if host!='api.github.com')
    assert 'Authorization' not in calls[2][1]
    assert not any(host=='other.example.org' for host,_ in calls)
    website=Fetcher(config,github_token='synthetic-unit-only-github-token')
    try:website.get('https://api.github.com/docs')
    finally:website.close()
    assert 'Authorization' not in calls[-1][1]


def test_worker_github_credential_file_is_private_bounded_and_not_followed(tmp_path,monkeypatch):
    from czero_app.worker import github_token
    credential=tmp_path/'github-token'
    credential.write_text('synthetic-unit-only-github-token\n');credential.chmod(0o600)
    monkeypatch.setenv('CZERO_GITHUB_TOKEN_FILE',str(credential))
    assert github_token()=='synthetic-unit-only-github-token'
    credential.chmod(0o644)
    with pytest.raises(ValueError,match='invalid_github_credential_file'):github_token()
    credential.chmod(0o600);credential.write_text('x'*4097)
    with pytest.raises(ValueError,match='invalid_github_credential_file'):github_token()
    alias=tmp_path/'alias';alias.symlink_to(credential)
    monkeypatch.setenv('CZERO_GITHUB_TOKEN_FILE',str(alias))
    with pytest.raises(OSError):github_token()
    monkeypatch.delenv('CZERO_GITHUB_TOKEN_FILE')
    assert github_token() is None


def test_pdf_sitemap_discovery_uses_attachment_roots():
    origin = 'https://example.org'
    listing = origin + '/notices'
    sitemap = origin + '/sitemap.xml'
    denied = origin + '/notices/inside-html-only.pdf'
    selected = origin + '/files/notice.pdf'
    fetch = Fetch({
        origin + '/robots.txt': (b'User-agent: *\nAllow: /', 'text/plain'),
        sitemap: (f'<urlset><url><loc>{denied}</loc></url><url><loc>{selected}</loc></url></urlset>'.encode(), 'application/xml'),
        listing: (b'<article><h1>Official notices</h1></article>', 'text/html'),
        selected: (b'%PDF-1.4 fixture', 'application/pdf'),
    })
    config = {'website': {'seeds': [listing], 'allowed_roots': [listing], 'sitemaps': [sitemap]},
              'attachments': {'allowed_roots': [origin + '/files']}}
    items, _, done = collect('website', config, {}, fetcher=fetch)
    assert done and [item['media_type'] for item in items] == ['text/markdown', 'application/pdf']
    assert items[1]['metadata']['parent_discovery_url'] == sitemap


@pytest.mark.parametrize('remaining,reason', [
    (20, 'source_byte_budget_exhausted'), (128, 'source_content_too_large'),
])
def test_chunked_body_distinguishes_remaining_batch_from_file_limit(monkeypatch, remaining, reason):
    from czero_core.source_http import Fetcher

    class Response:
        status = 200

        def getheader(self, name, default=None):
            return {'Content-Type': 'application/pdf'}.get(name, default)

        def read(self, size):
            return b'x' * size

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr('czero_core.source_http.public_addresses', lambda *a: ['1.1.1.1'])
    monkeypatch.setattr('czero_core.source_http.http.client.HTTPSConnection', Connection)
    fetch = Fetcher({'max_requests': 4, 'timeout': 1, 'max_bytes': 128})
    with pytest.raises(CollectionError, match=reason):
        fetch.response('https://example.org/attachment', remaining_bytes=remaining, batch_limit=512)
    assert fetch.downloaded == remaining + 1


@pytest.mark.parametrize('variant', ['weak', 'redirect'])
def test_pdf_revalidates_exact_strong_etag_and_never_caches_redirect_alias(variant):
    origin = 'https://example.org'
    listing = origin + '/notices'
    pdf = origin + '/files/notice.pdf'
    seen = []

    class Publisher(Fetch):
        def response(self, url, **options):
            if url != pdf:
                return super().response(url, **options)
            self.requests += 1
            headers = options.get('first_request_headers') or {}
            seen.append(headers)
            if variant == 'weak' and headers:
                return b'', url, '', {'status': 304, 'etag': 'W/"old"'}
            if variant == 'redirect':
                destination = url + '?utm_source=listing'
                options['validate_url'](destination)
                return b'%PDF-1.4 fixture', destination, 'application/pdf', {'status': 200, 'etag': '"new"', 'redirects': 1}
            return b'%PDF-1.4 fixture', url, 'application/pdf', {'status': 200, 'etag': '"new"'}

    fetch = Publisher({
        origin + '/robots.txt': (b'User-agent: *\nAllow: /', 'text/plain'),
        listing: (b'<article><h1>Official notices</h1><a href="/files/notice.pdf">Notice</a></article>', 'text/html'),
    })
    config = {'website': {'seeds': [listing], 'allowed_roots': [listing]},
              'attachments': {'allowed_roots': [origin + '/files']}}
    items, _, done = collect('website', config, {}, fetcher=fetch,
        attachment_validator=(lambda _: '"old"') if variant == 'weak' else None)
    assert done
    assert items[-1]['metadata']['canonical_url'] == pdf
    if variant == 'weak':
        assert seen == [{'If-None-Match': '"old"'}, {}]
        assert items[-1]['metadata']['http_etag'] == '"new"'
    else:
        assert seen == [{}] and 'http_etag' not in items[-1]['metadata']
