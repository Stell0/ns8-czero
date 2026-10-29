# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable genuine-predecessor content proof through authenticated HTTPS."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

CURRENT_SOURCE='CURRENT-PREDECESSOR-SOURCE-B café 東京'
OLD_SOURCE='RETIRED-PREDECESSOR-SOURCE-A'
CURRENT_WIKI='# Current predecessor article\n\nPreserve authored knowledge.'
OLD_WIKI='# Retired predecessor article\n\nOLD-WIKI-BODY-MARKER'


def request(browser,profile,path,data=None,method=None,status=200):
    actual,body,_=browser.api('/api/v1/'+path,data,method,profile['csrf_token'])
    assert actual==status,'Predecessor content operation failed (HTTP '+str(actual)+')'
    return json.loads(body) if body else None


def ready(browser,profile,version):
    deadline=time.monotonic()+95
    while time.monotonic()<deadline:
        rows=request(browser,profile,'sources/'+version['source_id']+'/versions?limit=100')['versions']
        found=next((row for row in rows if row['id']==version['id']),None)
        assert found and found['state']!='failed','Predecessor extraction failed'
        if found['state']=='ready':return found
        time.sleep(1)
    raise AssertionError('Predecessor extraction did not finish within its bound')


def seed(browser,profile,*,require_history=False):
    assert urlsplit(browser.origin).hostname.endswith('.test'),'Disposable host required'
    first=request(browser,profile,'sources/ingest-text',{'title':'Disposable predecessor source','body':OLD_SOURCE,
        'media_type':'text/plain','metadata':{'fixture':'predecessor current content'},'idempotency_key':'predecessor-content-source-a'},'POST',202)
    ready(browser,profile,first)
    old=request(browser,profile,'source-versions/'+first['id']+'/document')
    chunk=request(browser,profile,'documents/'+old['id']+'/chunks')['chunks'][0]
    entity=request(browser,profile,'entities',{'kind':'observation','label':'Disposable predecessor claim',
        'idempotency_key':'predecessor-content-entity'},'POST',201)
    assertion=request(browser,profile,'claims',{'entity_id':entity['id'],'predicate':'observed',
        'value':{'authored':'Preserve this assertion'},'evidence_chunk_ids':[chunk['id']],
        'idempotency_key':'predecessor-content-claim'},'POST',201)
    second=request(browser,profile,'sources/ingest-text',{'title':'Disposable predecessor source','body':CURRENT_SOURCE,
        'media_type':'text/plain','metadata':{'fixture':'predecessor current content'},'source_id':first['source_id'],
        'expected_revision':1,'idempotency_key':'predecessor-content-source-b'},'POST',202)
    ready(browser,profile,second)
    current=request(browser,profile,'source-versions/'+second['id']+'/document')
    page=request(browser,profile,'wiki/pages/upsert',{'slug':'disposable-predecessor-content','title':'Predecessor article','body':OLD_WIKI,
        'idempotency_key':'predecessor-content-wiki-a'},'POST')
    changed=request(browser,profile,'wiki/pages/upsert',{'slug':page['slug'],'title':'Predecessor article','body':CURRENT_WIKI,
        'expected_revision':1,'idempotency_key':'predecessor-content-wiki-b'},'POST')
    if require_history:
        assert request(browser,profile,'source-versions/'+first['id']+'/document')['body']==OLD_SOURCE,'Genuine predecessor source history was not seeded'
        assert request(browser,profile,'wiki/pages/'+page['id']+'?revision=1')['content']['body']==OLD_WIKI,'Genuine predecessor Wiki history was not seeded'
    return {'source_id':first['source_id'],'retired_version':first['id'],'current_version':second['id'],
        'current_document':current['id'],'old_chunk':chunk['id'],'page_id':page['id'],
        'current_wiki_revision':changed['content']['id'],'claim_id':assertion['id']}


def verify(browser,profile,expected):
    assert urlsplit(browser.origin).hostname.endswith('.test'),'Disposable host required'
    doc=request(browser,profile,'source-documents/'+expected['source_id'])
    assert doc['body']==CURRENT_SOURCE and doc['text_hash']==hashlib.sha256(CURRENT_SOURCE.encode()).hexdigest()
    current=request(browser,profile,'source-versions/'+expected['current_version']+'/document')
    assert current['id']==expected['current_document'] and current['body']==CURRENT_SOURCE
    versions=request(browser,profile,'sources/'+expected['source_id']+'/versions?limit=100')['versions']
    assert [row['id'] for row in versions]==[expected['current_version']],'Superseded source version survived upgrade'
    for path in ('source-versions/'+expected['retired_version']+'/document',
            'source-versions/'+expected['retired_version']+'/original','chunks/'+expected['old_chunk']+'/citation'):
        request(browser,profile,path,status=410)
    page=request(browser,profile,'wiki/pages/'+expected['page_id'])
    assert page['content']['id']==expected['current_wiki_revision'] and page['content']['body']==CURRENT_WIKI
    assert len(request(browser,profile,'wiki/pages/'+page['id']+'/revisions')['revisions'])==1
    request(browser,profile,'wiki/pages/'+page['id']+'?revision=1',status=410)
    claim=request(browser,profile,'claims/'+expected['claim_id'])
    assert claim['value']=={'authored':'Preserve this assertion'} and claim['evidence_stale']
    assert claim['evidence'][0]['status']=='superseded' and claim['evidence'][0]['body'] is None
    assert request(browser,profile,'sources/search?query='+OLD_SOURCE)['citations']==[]


def main():
    from oidc_fixture import STATE
    from oidc_probe import Browser
    stage=sys.argv[1];assert stage in ('seed','verify')
    personas=json.loads((STATE/'personas.json').read_text());browser=Browser('https://'+personas['host'])
    profile=browser.login('c0owner',personas['password']);path=STATE/'predecessor-content.json'
    try:
        if stage=='seed':
            assert not path.exists(),'Predecessor seed already exists; inspect its phase before retrying'
            expected=seed(browser,profile,require_history=True)
            old=os.umask(0o077)
            try:path.write_text(json.dumps(expected))
            finally:os.umask(old)
            path.chmod(0o600)
        else:verify(browser,profile,json.loads(path.read_text()))
        print('Disposable predecessor current-content '+stage+' passed')
    finally:browser.logout(profile)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(str(error) if isinstance(error,AssertionError) else type(error).__name__,file=sys.stderr)
        raise SystemExit(1)
