# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

from c0_freshdesk import API,collect,markdown,settings,scan
from c0_ingest.errors import C0Error
from c0_projects.cli import state_directory
from c0_projects.model import source_config
from c0_projects.fetch import FetchError


def configuration():
    return {'api_origin':'https://example.freshdesk.com','portal_origin':'https://help.example.org',
            'api_key':'synthetic-key','category_ids':[1,2],'excluded_categories':['Archived'],'excluded_articles':[99]}


def test_literal_env_filters_other_credentials_and_honors_blacklists(tmp_path):
    env=tmp_path/'.env';env.write_text('FRESHDESK_DOMAIN=example.freshdesk.com\n'
        'FRESHDESK_API_KEY="synthetic-key"\nFRESHDESK_SOLUTIONS_DOMAIN=help.example.org\n'
        'OPENAI_API_KEY=not-used\nwwOTHER_KEY=not-used\n'
        'FRESHDESK_CATEGORY_IDS=2,1,2\nCATEGORY_BLACKLIST=Archived, Internal\nARTICLE_ID_BLACKLIST=99,100\n')
    result=settings(env)
    assert result['category_ids']==[1,2]
    assert result['excluded_articles']==[99,100] and result['excluded_categories']==['Archived','Internal']
    assert 'OPENAI_API_KEY' not in json.dumps(result) and 'not-used' not in json.dumps(result)
    valid=env.read_text()
    for line,code in (
        ('FRESHDESK_CATEGORY_IDS=','explicit_freshdesk_category_ids_required'),
        ('FRESHDESK_CATEGORY_IDS=1,all','explicit_freshdesk_category_ids_required'),
        ('FRESHDESK_DOMAIN=127.0.0.1','explicit_freshdesk_api_host_required'),
        ('ARTICLE_ID_BLACKLIST=99,invalid','invalid_article_blacklist'),
        ('FRESHDESK_SOLUTIONS_DOMAIN=https://example.org/?q=ordinary','explicit_https_portal_origin_required'),
        ('FRESHDESK_SOLUTIONS_DOMAIN=https://example.org/?token=synthetic','invalid_public_url'),
    ):
        key=line.partition('=')[0]
        env.write_text('\n'.join(row for row in valid.splitlines() if not row.startswith(key+'='))+'\n'+line+'\n')
        with pytest.raises(C0Error,match=code):settings(env)
    env.write_text(valid+'FRESHDESK_DOMAIN=example.freshdesk.com\n')
    with pytest.raises(C0Error,match='duplicate_freshdesk_environment_key'):settings(env)


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
            '/api/v2/solutions/categories':[{'id':1,'name':'Router'},{'id':2,'name':'Archived'},{'id':3,'name':'Unselected'}],
            '/api/v2/solutions/categories/1/folders':[
                {'id':10,'name':'Public','visibility':1,'sub_folders_count':1},
                {'id':11,'name':'Staff','visibility':3},
                {'id':12,'name':'Child of staff','visibility':1,'parent_folder_id':11}],
            '/api/v2/solutions/folders/10/articles':[
                {'id':1,'status':2},{'id':2,'status':1},{'id':99,'status':2}],
            '/api/v2/solutions/folders/11/articles':[{'id':4,'status':2}],
            '/api/v2/solutions/folders/12/articles':[{'id':5,'status':2}],
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
                'folder_id':{1:10,3:13,4:11,5:12}[aid],'created_at':'2026-01-01T00:00:00Z','tags':[]}


def test_reference_folder_selection_with_publication_and_blacklist_checks():
    api=Inventory();definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export'})
    batch,inventory=collect(api,definition,configuration())
    assert [i.external_id for i in batch.items]==['1.md','3.md','4.md','5.md']
    assert all(i.provenance['source_type']=='freshdesk_faq' for i in batch.items)
    assert all(i.canonical_url.startswith('https://help.example.org/support/solutions/articles/') for i in batch.items)
    assert '/api/v2/solutions/folders/11/articles' in api.read and '/api/v2/solutions/folders/12/articles' in api.read
    assert not any('/articles/99' in p or '/articles/2'==p for p in api.read)
    assert {r.get('reason') for r in inventory if r['status']=='excluded'}=={
        'draft_or_unknown_status','article_blacklist','category_blacklist','category_not_selected'}
    assert collect(Inventory(),definition,configuration())[0].items[0].content_hash==batch.items[0].content_hash


def test_missing_selected_category_fails_before_fetching_articles():
    api=Inventory()
    definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export'})
    with pytest.raises(C0Error,match='freshdesk_selected_category_unavailable'):
        collect(api,definition,configuration()|{'category_ids':[1,42]})
    assert api.read==['/api/v2/solutions/categories']


def test_separate_state_does_not_alias_default_or_escape_private_data(tmp_path):
    assert state_directory(tmp_path)==tmp_path/'data/c0-projects'
    assert state_directory(tmp_path,'data/faq')==tmp_path/'data/faq'
    for name in ('/etc/other','../other','data/../../other','oauth.json','data'):
        with pytest.raises((C0Error,ValueError)):state_directory(tmp_path,name)
    (tmp_path/'data').mkdir();(tmp_path/'data/link').symlink_to(tmp_path/'data/c0-projects')
    with pytest.raises(C0Error):state_directory(tmp_path,'data/link/child')


def test_scan_resumes_after_saving_manifest_with_connector_bounds(tmp_path,monkeypatch):
    import c0_freshdesk as faq
    from c0_ingest.state import atomic,read

    state=tmp_path/'data/faq'
    env=tmp_path/'freshdesk.env'
    env.write_text('FRESHDESK_DOMAIN=example.freshdesk.com\nFRESHDESK_API_KEY=synthetic-key\n'
        'FRESHDESK_CATEGORY_IDS=1\nARTICLE_ID_BLACKLIST=99\n')
    definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export','max_requests':1})
    monkeypatch.setattr(faq,'binding',lambda *_:(definition,state,'expected-binding'))

    env.chmod(0o644)
    with pytest.raises(C0Error,match='credentials_require_private_job_file'):
        faq.scan(tmp_path,None,env,'data/faq')
    env.chmod(0o600)
    state.mkdir(parents=True)
    export=state/'export'
    export.symlink_to(tmp_path)
    with pytest.raises(C0Error,match='unsafe_private_state_path'):
        faq.scan(tmp_path,None,env,'data/faq')
    export.unlink()

    def api(settings,cache,**bounds):
        assert bounds['maximum']==1
        source=Inventory()
        source.close=lambda:None
        source.fetcher=type('Counters',(),{'requests':1})()
        return source

    def fail_latest(path,value):
        if path.name=='latest.json':raise OSError('synthetic interruption')
        atomic(path,value)

    monkeypatch.setattr(faq,'API',api)
    with monkeypatch.context() as interrupted:
        interrupted.setattr(faq,'atomic',fail_latest)
        with pytest.raises(OSError,match='synthetic interruption'):
            faq.scan(tmp_path,None,env,'data/faq')
    cycle=read(state/'crawl.json')['cycle']
    frozen=(state/'scans'/cycle/'manifest.json').read_bytes()
    assert faq.scan(tmp_path,None,env,'data/faq',resume=True)['status']=='scanned'
    assert (state/'scans'/cycle/'manifest.json').read_bytes()==frozen
    assert read(state/'latest.json')['freshdesk_binding_hash']=='expected-binding'
    assert read(state/'crawl.json')['complete']

    pending=read(state/'crawl.json')
    pending['complete']=False
    atomic(state/'crawl.json',pending)
    monkeypatch.setattr(faq,'binding',lambda *_:(definition,state,'new-binding'))
    with pytest.raises(C0Error,match='resume_selection_changed'):
        faq.scan(tmp_path,None,env,'data/faq',resume=True)
    assert faq.scan(tmp_path,None,env,'data/faq',restart=True)['status']=='scanned'
    assert read(state/'crawl.json')['cycle']!=cycle
    assert (state/'scans'/cycle/'manifest.json').read_bytes()==frozen


def test_restrictive_file_selector_is_rejected_before_publication(tmp_path,monkeypatch,capsys):
    import c0_freshdesk as faq

    definition=source_config({'id':'faq','adapter':'local_files','root':'data/freshdesk-faq/export',
        'include':['17.md']})
    monkeypatch.setattr(faq,'check_job',lambda _:None)
    monkeypatch.setattr(faq,'load_config',lambda _: {'server_url':'https://c0.example.org/mcp',
        'project_space_id':'synthetic-space','sources':[definition]})
    monkeypatch.setattr(faq,'connection_settings',lambda _: {'url':'https://c0.example.org/mcp',
        'space_id':'synthetic-space'})
    assert faq.main(['resume','--apply','--job',str(tmp_path),'--config',str(tmp_path/'config.json')])==1
    assert json.loads(capsys.readouterr().out)['error']=='freshdesk_export_requires_all_markdown_from_selected_categories'


def test_item_limit_does_not_cap_the_whole_batch():
    definition=source_config({'id':'faq','adapter':'local_files','root':'data/faq/export','max_bytes':70})
    batch,_=collect(Inventory(),definition,configuration())
    assert len(batch.items)==4
    assert max(len(item.content) for item in batch.items)<=70
    assert sum(len(item.content) for item in batch.items)>70
