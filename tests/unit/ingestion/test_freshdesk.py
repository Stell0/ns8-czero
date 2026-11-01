# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from c0_freshdesk import API,collect,markdown,settings,scan
from c0_ingest.errors import C0Error
from c0_projects.cli import state_directory
from c0_projects.model import source_config
from c0_projects.fetch import FetchError


def configuration():
    return {'api_origin':'https://example.freshdesk.com','portal_origin':'https://help.example.org',
            'api_key':'synthetic-key','excluded_categories':['Archived'],'excluded_articles':[99]}


def test_literal_env_filters_other_credentials_and_honors_blacklists(tmp_path):
    env=tmp_path/'.env';env.write_text('FRESHDESK_DOMAIN=example.freshdesk.com\n'
        'FRESHDESK_API_KEY="synthetic-key"\nFRESHDESK_SOLUTIONS_DOMAIN=help.example.org\n'
        'OPENAI_API_KEY=not-used\nwwOTHER_KEY=not-used\n'
        'CATEGORY_BLACKLIST=Archived, Internal\nARTICLE_ID_BLACKLIST=99,100\n')
    result=settings(env)
    assert result['excluded_articles']==[99,100] and result['excluded_categories']==['Archived','Internal']
    assert 'OPENAI_API_KEY' not in json.dumps(result) and 'not-used' not in json.dumps(result)
    for line in ('FRESHDESK_DOMAIN=127.0.0.1','ARTICLE_ID_BLACKLIST=99,invalid',
                 'FRESHDESK_SOLUTIONS_DOMAIN=https://example.org/?token=secret'):
        env.write_text(env.read_text()+'\n'+line+'\n')
        with pytest.raises(C0Error):settings(env)


class Transport:
    def __init__(self):self.calls=[];self.requests=0;self.fail=False;self.redirect=False
    def response(self,url,**kwargs):
        kwargs['validate_url'](url)
        if self.redirect:kwargs['validate_url']('https://unrelated.example.org/api/v2/solutions/categories')
        if self.fail:raise FetchError('source_http_429','2099-01-01T00:00:00+00:00')
        self.calls.append((url,kwargs));self.requests+=1
        return b'[{"id":1}]',url,'application/json',{}
    def close(self):pass


def test_get_only_pinned_api_cache_has_no_credentials_and_resume_avoids_refetch(tmp_path):
    transport=Transport();api=API(configuration(),tmp_path,fetcher=transport)
    assert api.get('/api/v2/solutions/categories',1)==[{'id':1}]
    assert api.get('/api/v2/solutions/categories',1)==[{'id':1}] and transport.requests==1
    assert transport.calls[0][1]['headers']['Authorization'].startswith('Basic ')
    assert 'synthetic-key' not in ''.join(p.read_text() for p in tmp_path.glob('*.json'))
    for path in ('/api/v2/tickets','/api/v2/solutions/../tickets','https://elsewhere.example.org'):
        with pytest.raises(C0Error):api.get(path)
    transport.redirect=True
    with pytest.raises(C0Error,match='redirect'):api.get('/api/v2/solutions/articles/2')


def test_retry_after_and_repeated_pages_fail_explicitly(tmp_path):
    t=Transport();t.fail=True;api=API(configuration(),tmp_path/'rate',fetcher=t)
    with pytest.raises(FetchError) as error:api.get('/api/v2/solutions/categories',1)
    assert error.value.retry_after=='2099-01-01T00:00:00+00:00'
    assert not list((tmp_path/'rate').glob('*.json'))
    api.get=lambda path,page:[{'id':i} for i in range(100)]
    with pytest.raises(C0Error,match='repeated_inventory_page'):list(api.pages('/api/v2/solutions/categories'))


def test_markdown_preserves_tables_links_code_and_excludes_active_content():
    raw={'title':'Router procedure','description':'<p><strong>Warning</strong>: save first.</p>'
        '<table><tr><th>Port</th><th>Mode</th></tr><tr><td>7443</td><td>TLS</td></tr></table>'
        '<pre><code class="language-sh">configure \\\n  --safe</code></pre>'
        '<a href="/manual">Manual</a><script>steal()</script><a href="javascript:steal()">Ignore</a>'}
    body=markdown(raw,'https://help.example.org/support/solutions/articles/2').decode()
    assert body.startswith('# Router procedure\n') and '**Warning**' in body
    assert '| Port | Mode |' in body and '```sh\nconfigure \\\n  --safe' in body
    assert 'https://help.example.org/manual' in body and 'steal' not in body
    for description in ('','<script>only()</script>','<input type="password">'):
        with pytest.raises(C0Error):markdown({'title':'Invalid','description':description},'https://example.org')


class Inventory:
    def __init__(self):self.read=[]
    def pages(self,path):
        self.read.append(path)
        values={
            '/api/v2/solutions/categories':[{'id':1,'name':'Router'},{'id':2,'name':'Archived'}],
            '/api/v2/solutions/categories/1/folders':[
                {'id':10,'name':'Public','visibility':1,'sub_folders_count':1},
                {'id':11,'name':'Staff','visibility':3},
                {'id':12,'name':'Child of staff','visibility':1,'parent_folder_id':11}],
            '/api/v2/solutions/folders/10/articles':[
                {'id':1,'status':2},{'id':2,'status':1},{'id':99,'status':2}],
            '/api/v2/solutions/folders/10/subfolders':[{'id':13,'name':'Nested','visibility':1,'parent_folder_id':10}],
            '/api/v2/solutions/folders/13/articles':[{'id':3,'status':2}],
        }
        return iter(values[path])
    def get(self,path):
        self.read.append(path)
        if path=='/api/v2/solutions/folders/11':return {'id':11,'visibility':3}
        if path=='/api/v2/solutions/folders/10':return {'id':10,'visibility':1}
        aid=int(path.rsplit('/',1)[1])
        return {'id':aid,'status':2,'title':'Procedure '+str(aid),'description':'<p>Save configuration first.</p>',
                'folder_id':10 if aid==1 else 13,'created_at':'2026-01-01T00:00:00Z','tags':[]}


def test_published_public_selection_nested_permissions_and_stable_identity():
    api=Inventory();definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export'})
    batch,inventory=collect(api,definition,configuration())
    assert [i.external_id for i in batch.items]==['1.md','3.md']
    assert all(i.provenance['source_type']=='freshdesk_faq' for i in batch.items)
    assert all(i.canonical_url.startswith('https://help.example.org/support/solutions/articles/') for i in batch.items)
    assert not any('/11/articles' in p or '/12/articles' in p or '/articles/99' in p or '/articles/2'==p for p in api.read)
    assert {r.get('reason') for r in inventory if r['status']=='excluded'}=={
        'restricted_or_unknown_visibility','draft_or_unknown_status','article_blacklist','category_blacklist'}
    assert collect(Inventory(),definition,configuration())[0].items[0].content_hash==batch.items[0].content_hash


def test_separate_state_does_not_alias_default_or_escape_private_data(tmp_path):
    assert state_directory(tmp_path)==tmp_path/'data/c0-projects'
    assert state_directory(tmp_path,'data/faq')==tmp_path/'data/faq'
    for name in ('/etc/other','../other','data/../../other','oauth.json','data'):
        with pytest.raises((C0Error,ValueError)):state_directory(tmp_path,name)
    (tmp_path/'data').mkdir();(tmp_path/'data/link').symlink_to(tmp_path/'data/c0-projects')
    with pytest.raises(C0Error):state_directory(tmp_path,'data/link/child')
