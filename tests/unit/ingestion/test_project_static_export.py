# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from uuid import uuid4
import pytest
from c0_ingest.errors import C0Error
from c0_projects.exporting import Artifacts,canonical
from c0_projects.model import sha
from c0_projects.static_export import export_static


def snapshot(tmp_path,body):
    space,page,revision=[str(uuid4()) for _ in range(3)]
    root=tmp_path/'snapshot';archive=Artifacts(root,1024*1024)
    archive.add('page.json',canonical({'id':page,'slug':'public','revision':1,'deleted':False}),kind='wiki_pages',resource_id=page)
    archive.add('revision.json',canonical({'id':revision,'page_id':page,'number':1,'title':'Fixture','content_hash':sha(body.encode()),
        'metadata':{'static_publish':{'public':True}}}),kind='wiki_revisions',resource_id=revision)
    archive.add('body.md',body.encode(),kind='wiki_text',resource_id=revision)
    saved=archive.add('manifest.json',canonical({'kind':'c0-project-export','schema_version':1,'status':'validated',
        'project_id':space,'files':list(archive.files)}))
    archive.add('manifest.sha256',(saved['sha256']+'\n').encode())
    return root,{'schema_version':1,'project_id':space,'wiki_revisions':[revision],'report_references':[]},page


@pytest.mark.parametrize('body',[
    '[Unsafe](javascript:alert(1) "title")\n','[Unsafe](\njavascript:alert(1))\n',
    '![Tracking](\nhttps://example.org/image)\n','[Reference]: javascript:alert(1)\n',
    '[Private](./wiki?page_id='+str(uuid4())+')\n','[Other space](./wiki?space_id='+str(uuid4())+')\n',
])
def test_ambiguous_or_private_markdown_never_becomes_validated_public_output(tmp_path,body):
    root,selection,_=snapshot(tmp_path,body)
    with pytest.raises(C0Error):export_static(root,selection,tmp_path/'static')
    assert not (tmp_path/'static/static-manifest.json').exists()


def test_crlf_frontmatter_and_html_stay_inactive(tmp_path):
    root,selection,page=snapshot(tmp_path,'\ufeff---  \r\nunsafe: metadata\r\n---\r\n\n<script>example()</script>\n')
    assert export_static(root,selection,tmp_path/'static')['status']=='VALIDATED'
    body=(tmp_path/'static/content'/(page+'.md')).read_text()
    assert body.startswith('\\-\\-\\-\n') and '<script>' not in body
