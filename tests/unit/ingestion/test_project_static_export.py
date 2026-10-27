# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_projects.exporting import Artifacts,canonical
from c0_projects.model import sha
from c0_projects.static_export import export_static


def snapshot(tmp_path,body):
    space,page,revision=[str(uuid4()) for _ in range(3)]
    body=body.replace('__SELF__',page)
    root=tmp_path/'snapshot';archive=Artifacts(root,1024*1024)
    archive.add('page.json',canonical({'id':page,'slug':'public','revision':1,'deleted':False}),kind='wiki_pages',resource_id=page)
    archive.add('revision.json',canonical({'id':revision,'page_id':page,'number':1,'title':'Fixture','content_hash':sha(body.encode()),
        'metadata':{'static_publish':{'public':True}}}),kind='wiki_revisions',resource_id=revision)
    archive.add('body.md',body.encode(),kind='wiki_text',resource_id=revision)
    saved=archive.add('manifest.json',canonical({'kind':'c0-project-export','schema_version':1,'status':'validated',
        'project_id':space,'instance_url':'https://knowledge.example.org/mcp','files':list(archive.files)}))
    archive.add('manifest.sha256',(saved['sha256']+'\n').encode())
    return root,{'schema_version':1,'project_id':space,'wiki_revisions':[revision],'report_references':[]},page


@pytest.mark.parametrize('body',[
    '[Unsafe](javascript:alert(1) "title")\n','[Unsafe](\njavascript:alert(1))\n',
    '![Tracking](\nhttps://example.org/image)\n','[Reference]: javascript:alert(1)\n',
    '[Private](./wiki?page_id='+str(uuid4())+')\n','[Other space](./wiki?space_id='+str(uuid4())+')\n',
    '[Absolute private](https://knowledge.example.org/wiki?page_id='+str(uuid4())+')\n',
    '[Absolute other space](https://knowledge.example.org/wiki?space_id='+str(uuid4())+')\n',
    '[Multiline\nlabel](javascript:alert(1))\n','![Multiline\nimage](https://example.org/tracker)\n',
    '[Nested [label]](javascript:alert(1))\n',
    '[Image omitted]\n(javascript:alert(1))\n',
    '- ```text\n  example\n  ```\n\n[Outside code](javascript:alert(1))\n',
    'https://knowledge.example.org/sources?source_id='+str(uuid4())+'\n',
])
def test_ambiguous_or_private_markdown_never_becomes_validated_public_output(tmp_path,body):
    root,selection,_=snapshot(tmp_path,body)
    with pytest.raises(C0Error):export_static(root,selection,tmp_path/'static')
    assert not (tmp_path/'static/static-manifest.json').exists()


@pytest.mark.parametrize('newline',['\n','\r\n','\r'])
def test_frontmatter_and_html_stay_inactive(tmp_path,newline):
    root,selection,page=snapshot(tmp_path,'\ufeff\n  ---  '+newline+'unsafe: metadata'+newline+'---'+newline+'\n<script>example()</script>\n')
    assert export_static(root,selection,tmp_path/'static')['status']=='VALIDATED'
    body=(tmp_path/'static/content'/(page+'.md')).read_text()
    assert body.lstrip().startswith('\\-\\-\\-') and '<script>' not in body


def test_absolute_protected_evidence_loses_destination_and_selected_page_links_map(tmp_path):
    root,selection,page=snapshot(tmp_path,'[Evidence](https://knowledge.example.org/sources?source_id='+str(uuid4())+
        ')\n\n[Self](https://knowledge.example.org/wiki?page_id=__SELF__&revision=1)\n')
    assert export_static(root,selection,tmp_path/'static')['status']=='VALIDATED'
    body=(tmp_path/'static/content'/(page+'.md')).read_text()
    assert 'evidence retained in C0' in body and 'knowledge.example.org' not in body and 'source_id' not in body
    assert '[Self]('+page+'.md)' in body


def test_large_unmatched_bracket_input_has_bounded_rejection(tmp_path):
    from time import perf_counter
    root,selection,_=snapshot(tmp_path,'['*131072)
    started=perf_counter()
    with pytest.raises(C0Error):export_static(root,selection,tmp_path/'static')
    assert perf_counter()-started<2
