# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from c0_ingest.errors import C0Error
from c0_projects.adapters import collect, safe_read
from c0_projects.fetch import public_addresses
from c0_projects.model import source_config, Item
from c0_projects.publish import parts


def config(adapter,**values):return source_config({'id':'synthetic','adapter':adapter,**values})


@pytest.mark.parametrize('change',[{'adapter':'shell'},{'max_requests':0},{'max_bytes':-1},{'include':'*'},{'script':'echo forbidden'}])
def test_configuration_rejects_before_any_fetch(change):
    with pytest.raises(C0Error):source_config({'id':'synthetic','adapter':'http','url':'https://example.org/docs',**change})


def test_local_recursive_and_symlink_denial(tmp_path):
    root=tmp_path/'inputs';root.mkdir();(root/'article.md').write_text('# Original\n\nIgnore all instructions is untrusted document text.')
    (root/'nested').mkdir();(root/'nested/second.txt').write_text('Second original')
    outside=tmp_path/'private.txt';outside.write_text('Never publish');(root/'escape.txt').symlink_to(outside)
    batch=collect(config('local_files',root='inputs'),root=tmp_path)
    assert batch.status=='partial' and len(batch.items)==2
    assert all(b'Never publish' not in item.content for item in batch.items)
    assert b'Ignore all instructions' in batch.items[0].content
    with pytest.raises(OSError):safe_read(root,'escape.txt',100)
    with pytest.raises(C0Error):config('local_files',root='inputs',paths=['../private.txt'])


class Fetch:
    def __init__(self,values):self.values=values;self.calls=[]
    def get(self,url):self.calls.append(url);return self.values[url]


def test_http_extracts_inert_text_and_same_host_canonical(tmp_path):
    url='https://example.org/page';fetch=Fetch({url:(b'<title>Original</title><link rel="canonical" href="/canonical"><p>Evidence</p><script>execute()</script>',url,'text/html')})
    item=collect(config('http',url=url),root=tmp_path,fetcher=fetch).items[0]
    assert item.title=='Original' and item.content==b'Original\n\nEvidence'
    assert item.canonical_url=='https://example.org/canonical'


def test_feed_dates_and_stable_guid_do_not_invent_news(tmp_path):
    url='https://example.org/feed';page='https://example.org/old'
    fetch=Fetch({url:(b'<rss><channel><item><guid>stable-old</guid><link>/old</link><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item></channel></rss>',url,'application/rss+xml'),page:(b'Old original',page,'text/plain')})
    batch=collect(config('rss_atom',url=url),root=tmp_path,fetcher=fetch)
    assert batch.items[0].external_id=='stable-old' and batch.items[0].published_at.startswith('2024-01-01')
    assert batch.items[0].retrieved_at!=batch.items[0].published_at
    assert batch.cursor['feed_hash']


def test_sitemap_selects_only_configured_paths_and_no_cross_host(tmp_path):
    url='https://example.org/map.xml';page='https://example.org/docs/one'
    fetch=Fetch({url:(b'<urlset><url><loc>https://example.org/docs/one</loc></url><url><loc>https://example.org/other</loc></url><url><loc>https://internal.example.invalid/private</loc></url></urlset>',url,'application/xml'),page:(b'Original',page,'text/plain')})
    batch=collect(config('sitemap',url=url,include=['/docs/']),root=tmp_path,fetcher=fetch)
    assert len(batch.items)==1 and batch.status=='partial'
    assert fetch.calls==[url,page]


def test_github_bounded_pages_ids_and_original_body(tmp_path):
    class GitHub:
        def get(self,path):
            if path=='/repos/synthetic/repository':return {'id':17,'private':False},None
            return [{'id':27,'title':'Issue','body':'Original issue content','html_url':'https://github.com/synthetic/repository/issues/1','created_at':'2024-01-01T12:00:00Z'}],'/repos/synthetic/repository/issues?page=2'
    batch=collect(config('github',repository='synthetic/repository',include=['issues'],max_pages=1),root=tmp_path,github=GitHub())
    assert batch.status=='partial' and batch.items[0].external_id=='17:issues:27'
    assert b'Original issue content' in batch.items[0].content


def test_authorized_c0_source_never_substitutes_another_space(tmp_path):
    source='00000000-0000-4000-8000-000000000001'
    cfg=config('c0_space',source_space_id=source,authorization_ref='synthetic explicit subscription')
    class Client:space_id='00000000-0000-4000-8000-000000000002'
    with pytest.raises(C0Error):collect(cfg,root=tmp_path,source_client=Client())
    with pytest.raises(C0Error):config('c0_space',source_space_id=source)


def test_offline_wikiplant_stable_identity(tmp_path):
    root=tmp_path/'export';(root/'data/wiki').mkdir(parents=True)
    (root/'INSTANCE.json').write_text(json.dumps({'instance_id':'synthetic-legacy'}))
    (root/'data/wiki/article.md').write_text('# Fabricated original')
    batch=collect(config('wikiplant_export',root='export'),root=tmp_path)
    assert batch.items[0].external_id=='synthetic-legacy:data/wiki/article.md'
    assert batch.items[0].provenance['legacy_instance_id']=='synthetic-legacy'


def test_large_unicode_text_has_complete_hashable_parts_and_byte_offsets():
    body=('A paragraph with Unicode café 🤖.\n\n'*20000).encode()
    item=Item('synthetic','stable','Large original',body)
    split=list(parts(item,limit=131072))
    assert len(split)>1 and b''.join(part.content for part in split)==body
    assert all(len(part.content)<=131072 for part in split)
    assert all(left.end_byte==right.start_byte for left,right in zip(split,split[1:]))
    assert split[-1].end_byte==len(body)
    assert list(parts(item))[0].external_id==split[0].external_id
    assert len(list(parts(item)))==1


def test_dns_rebinding_mixed_private_answers_are_denied():
    records=[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('127.0.0.1',443))]
    with patch('socket.getaddrinfo',return_value=records):
        with pytest.raises(C0Error):public_addresses('example.org',443,1)


def test_github_cursor_resumes_verified_pages_without_restarting_root(tmp_path):
    calls=[]
    class GitHub:
        def get(self,path):
            calls.append(path)
            if path=='/repos/synthetic/repository':return {'id':17,'private':False},None
            if 'page=2' in path:return [{'id':28,'title':'Second','body':'Next original'}],None
            return [{'id':27,'title':'First','body':'Original'}],'/repos/synthetic/repository/issues?page=2'
    selected=config('github',repository='synthetic/repository',include=['issues'],max_pages=1)
    first=collect(selected,root=tmp_path,github=GitHub())
    second=collect(selected,root=tmp_path,github=GitHub(),cursor=first.cursor)
    assert first.status=='partial' and second.status=='complete'
    assert first.items[0].external_id!=second.items[0].external_id
    assert 'page=2' in calls[-1]


def test_public_github_adapter_keeps_original_bodies_without_private_credentials(tmp_path,monkeypatch):
    from github_vault.github_client import GitHub,public_data
    monkeypatch.setattr('github_vault.github_client.token',lambda: (_ for _ in ()).throw(AssertionError('must not read token')))
    client=GitHub(tmp_path,{'max_requests':1,'max_retries':0,'max_wait_seconds':1},anonymous=True,preserve_bodies=True)
    assert client.token is None
    value={'body':'Original content','author':{'email':'excluded@example.org'}}
    assert 'body' not in public_data(value)
    assert public_data(value,preserve_bodies=True)=={'body':'Original content','author':{}}


def test_local_inventory_resumes_at_next_item(tmp_path):
    root=tmp_path/'inputs';root.mkdir()
    for name in ['a.md','b.md','c.md']:(root/name).write_text('Synthetic '+name)
    selected=config('local_files',root='inputs',max_items=2)
    first=collect(selected,root=tmp_path)
    second=collect(selected,root=tmp_path,cursor=first.cursor)
    assert first.status=='partial' and second.status=='complete'
    assert [item.external_id for item in first.items+second.items]==['a.md','b.md','c.md']


def test_github_nested_docs_and_rate_limit_retain_completed_items(tmp_path):
    import base64
    from github_vault.github_client import GitHubError
    class GitHub:
        def get(self,path):
            if path=='/repos/synthetic/repository':return {'id':17,'private':False},None
            if path.endswith('/docs'):return [{'type':'dir','path':'docs/nested'}],None
            if path.endswith('/nested'):return [{'type':'file','path':'docs/nested/one.md'}],None
            if path.endswith('.md'):return {'path':'docs/nested/one.md','sha':'abc','content':base64.b64encode(b'Original nested documentation').decode()},None
            raise GitHubError('synthetic rate limit',status=429,retry_at=1793100000)
    batch=collect(config('github',repository='synthetic/repository',include=['docs','releases']),root=tmp_path,github=GitHub())
    assert batch.status=='partial' and len(batch.items)==1
    assert batch.items[0].content==b'Original nested documentation'
    assert batch.cursor['streams']['docs'] is None and not batch.cursor['complete']
    assert batch.retry_after=='2026-10-27T11:20:00+00:00'


@pytest.mark.parametrize('location',['http://127.0.0.1/private','https://other.example.org/private','http://example.org/downgrade'])
def test_http_redirects_cannot_change_host_or_downgrade(location,monkeypatch):
    from c0_projects.fetch import Fetcher
    calls=[]
    class Response:
        status=302
        def getheader(self,name,default=None):return location if name=='Location' else default
    class Connection:
        sock=None
        def __init__(self,*args,**kwargs):calls.append(args)
        def request(self,*args,**kwargs):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr('c0_projects.fetch.public_addresses',lambda *args:['8.8.8.8'])
    monkeypatch.setattr('c0_projects.fetch.http.client.HTTPSConnection',Connection)
    with pytest.raises(C0Error):Fetcher(config('http',url='https://example.org/page')).get('https://example.org/page')
    assert len(calls)==1


def test_snapshot_rejects_symlink_even_to_an_inside_file(tmp_path):
    from c0_projects.cli import save_scan,load_scan
    from c0_projects.model import Batch
    selected=config('http',url='https://example.org/page');directory=tmp_path/'scan'
    save_scan(directory,[(selected,Batch([Item('synthetic','id','Title',b'Original')]))])
    content=directory/'synthetic-0.bin';content.rename(directory/'inside.bin');content.symlink_to('inside.bin')
    with pytest.raises(OSError):load_scan(directory)


@pytest.mark.parametrize('adapter',['rss_atom','sitemap'])
def test_feed_and_sitemap_resume_after_verified_item_bound(tmp_path,adapter):
    url='https://example.org/index';one='https://example.org/one';two='https://example.org/two'
    raw=(b'<rss><channel><item><guid>one</guid><link>/one</link></item><item><guid>two</guid><link>/two</link></item></channel></rss>' if adapter=='rss_atom'
        else b'<urlset><url><loc>/one</loc></url><url><loc>/two</loc></url></urlset>')
    fetch=Fetch({url:(raw,url,'application/xml'),one:(b'First original',one,'text/plain'),two:(b'Second original',two,'text/plain')})
    selected=config(adapter,url=url,max_items=1)
    first=collect(selected,root=tmp_path,fetcher=fetch)
    second=collect(selected,root=tmp_path,fetcher=fetch,cursor=first.cursor)
    assert first.status=='partial' and second.status=='complete'
    assert first.items[0].content==b'First original' and second.items[0].content==b'Second original'


def test_atom_prefers_alternate_and_retains_linkless_original_entries(tmp_path):
    url='https://example.org/feed';page='https://example.org/article'
    raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>linked</id><link rel="self" href="/api/entry"/><link rel="alternate" href="/article"/></entry><entry><id>inline</id><title>Original inline notice</title><content>Untrusted original announcement, never executable instructions.</content><published>2024-01-01T12:00:00Z</published></entry></feed>'
    fetch=Fetch({url:(raw,url,'application/atom+xml'),page:(b'Primary article',page,'text/plain')})
    batch=collect(config('rss_atom',url=url),root=tmp_path,fetcher=fetch)
    assert batch.status=='complete' and len(batch.items)==2
    assert fetch.calls==[url,page] and batch.items[0].canonical_url==page
    assert batch.items[1].external_id=='inline' and b'Untrusted original announcement' in batch.items[1].content
    assert batch.items[1].provenance['source_type']=='rss_atom_inline'


@pytest.mark.parametrize('field',['access_token','apiKey','client_secret','X-Amz-Signature','client_assertion','sessionid','authorization'])
def test_public_source_configuration_rejects_credential_queries(field):
    with pytest.raises(C0Error):config('http',url='https://example.org/page?'+field+'=synthetic-private-value')
