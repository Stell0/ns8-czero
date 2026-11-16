# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Public-source batches over the existing DNS-pinned transport and HTML converter."""
import base64
from html.parser import HTMLParser
import fnmatch
import hashlib
import json
import re
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlsplit, urljoin
from urllib.robotparser import RobotFileParser

from .source_http import Fetcher, CollectionError
from .source_html import configuration, boundary, extract, normalize


def validate(kind, config):
    if type(config) is not dict or len(json.dumps(config, allow_nan=False).encode())>16384:
        raise ValueError('invalid_source_configuration')
    allowed = {'max_bytes', 'max_requests', 'max_items', 'timeout'}
    allowed |= {'website', 'include'} if kind == 'website' else {'repositories', 'include', 'paths', 'exclude', 'ref'}
    if kind not in ('website','github') or set(config)-allowed:
        raise ValueError('invalid_source_configuration')
    result = {'max_bytes': 2*1024*1024, 'max_requests': 12, 'max_items': 5, 'timeout': 5, **config}
    for key, maximum in (('max_bytes',2*1024*1024),('max_requests',30),('max_items',20),('timeout',10)):
        if type(result[key]) is not int or not (4 if key=='max_requests' else 1)<=result[key]<=maximum:
            raise ValueError('invalid_source_limit')
    for key in ('include','paths','exclude'):
        values=result.get(key,[])
        if type(values) is not list or len(values)>100 or any(type(v) is not str or not v or len(v)>512 for v in values):
            raise ValueError('invalid_source_selection')
    if kind == 'website':
        result['website']=configuration(config.get('website'))
        result['include']=config.get('include',[])
    else:
        repos=config.get('repositories')
        if type(repos) is not list or not 1<=len(repos)<=100 or any(type(v) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}',v) for v in repos):
            raise ValueError('invalid_github_repositories')
        if len(set(repos))!=len(repos):raise ValueError('invalid_github_repositories')
        result['include']=config.get('include',['files'])
        if not result['include'] or set(result['include'])-{'files','issues','pull_requests','releases'}:
            raise ValueError('invalid_github_selection')
        result['paths']=config.get('paths',['README*','docs/*'])
        result['exclude']=config.get('exclude',[])
        result['ref']=config.get('ref','HEAD')
        if type(result['ref']) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]{1,128}',result['ref']) or any(part in ('','.','..') for part in result['ref'].split('/')):
            raise ValueError('invalid_github_ref')
    return result


def item(key, title, body, url, media='text/markdown', **provenance):
    if not body or len(body)>2*1024*1024:
        raise CollectionError('source_content_too_large')
    try:body.decode('utf-8')
    except UnicodeError:raise CollectionError('source_non_text_file') from None
    return {'key':hashlib.sha256(key.encode()).hexdigest(), 'title':title[:256], 'body':body,
            'media_type':media, 'metadata':{'original_url':url, **provenance}}


def collect(kind, config, cursor, *, fetcher=None, preview=False):
    config=validate(kind,config)
    fetcher=fetcher or Fetcher(config,accept_json=kind=='github')
    try:
        return website(config,cursor,fetcher,preview=preview) if kind=='website' else github(config,cursor,fetcher)
    finally:
        fetcher.close()


def website(config,cursor,fetcher,*,preview=False):
    options=config['website']
    pending=list(cursor.get('pending',options['seeds']))
    inventories=list(cursor.get('inventories',options['sitemaps']))
    inventories_seen=list(cursor.get('inventories_seen',[]))
    seen=set(cursor.get('seen',[]));items=[];robots={}
    initial_bytes=getattr(fetcher,'downloaded',0)
    def response(url,**kwargs):
        return fetcher.response(url,remaining_bytes=lambda:options['max_total_bytes']-(getattr(fetcher,'downloaded',0)-initial_bytes),**kwargs)
    def rules(url):
        parsed=urlsplit(url);origin=parsed.scheme+'://'+parsed.netloc
        if origin not in robots:
            boundary(origin+'/robots.txt',options,inventory=True)
            raw,_,_,head=response(origin+'/robots.txt',allow_status=(200,404,410,401,403))
            rule=RobotFileParser()
            if head['status'] in (401,403):raise CollectionError('website_robots_access_denied')
            if head['status'] in (404,410):rule.allow_all=True
            else:rule.parse(raw.decode('utf-8-sig').splitlines())
            robots[origin]=rule
        return robots[origin]
    def delay_for(url):
        rule=rules(url)
        delay=max(options['interval_ms']/1000,rule.crawl_delay('c0-projects') or rule.crawl_delay('*') or 0)
        rate=rule.request_rate('c0-projects') or rule.request_rate('*')
        if rate:
            if rate.requests<=0 or rate.seconds<0:raise CollectionError('website_invalid_robots_rate')
            delay=max(delay,rate.seconds/rate.requests)
        if delay>10:raise CollectionError('website_robots_delay_exceeds_run_budget')
        return delay
    # Inventory URLs are explicit configuration and obey the same public boundary.
    while inventories and fetcher.requests < config['max_requests']-2:
        url=inventories[0]
        boundary(url,options,inventory=True)
        rule=rules(url)
        if not rule.can_fetch('c0-projects',url):
            inventories.pop(0);inventories_seen.append(url);continue
        def checked_inventory(target):
            boundary(target,options,inventory=True)
            if not rules(target).can_fetch('c0-projects',target):
                raise CollectionError('website_redirect_robots_denied')
        raw,_,_,_=response(url,validate_url=checked_inventory,interval=delay_for)
        if len(raw)>2*1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise CollectionError('website_invalid_sitemap')
        try:tree=ET.fromstring(raw)
        except ET.ParseError:raise CollectionError('website_invalid_sitemap') from None
        index=tree.tag.rsplit('}',1)[-1]=='sitemapindex'
        for node in tree:
            location=next((v.text for v in node if v.tag.rsplit('}',1)[-1]=='loc'),None)
            if not location:continue
            try:target=boundary(location,options,inventory=index)
            except CollectionError:continue
            if index:
                if target not in inventories and target not in inventories_seen:inventories.append(target)
            elif target not in pending and target not in seen:pending.append(target)
        inventories.pop(0);inventories_seen.append(url)
        if len(inventories)+len(inventories_seen)+len(pending)>10000:raise CollectionError('website_frontier_limit')
    while pending and len(items)<config['max_items'] and fetcher.requests<config['max_requests']-1:
        url=pending[0]
        if url in seen:
            pending.pop(0);continue
        boundary(url,options)
        parsed=urlsplit(url);rule=rules(url)
        if (not rule.can_fetch('c0-projects',url) or
                any(fnmatch.fnmatch(url,p) or fnmatch.fnmatch(parsed.path,p) for p in options['exclude'])):
            pending.pop(0);seen.add(url);continue
        def checked(target):
            boundary(target,options)
            if not rules(target).can_fetch('c0-projects',target):
                raise CollectionError('website_redirect_robots_denied')
        raw,final,media,_=response(url,validate_url=checked,interval=delay_for)
        if media not in ('text/html','application/xhtml+xml'):
            raise CollectionError('website_unsupported_media')
        if preview:
            # HTTP previews never run article selectors; the worker owns conversion.
            class Title(HTMLParser):
                inside=False
                text=''
                def handle_starttag(self,tag,attrs):
                    if tag=='title':self.inside=True
                def handle_endtag(self,tag):
                    if tag=='title':self.inside=False
                def handle_data(self,data):
                    if self.inside:self.text=(self.text+data)[:256]
            title=Title();title.feed(raw.decode('utf-8-sig'))
            items.append({'title':title.text or final,'metadata':{'original_url':final}})
            links=[]
        else:
            title,body,canonical,links,metadata=extract(raw,final,options)
            if not config['include'] or any(fnmatch.fnmatch(url,p) or fnmatch.fnmatch(parsed.path,p) for p in config['include']):
                items.append(item(canonical,title,body,canonical,**metadata))
        pending.pop(0);seen.add(url)
        for target in links:
            try:target=boundary(normalize(target,final),options)
            except CollectionError:continue
            if target not in seen and target not in pending:pending.append(target)
        if len(pending)+len(seen)>10000:raise CollectionError('website_frontier_limit')
        if fetcher.requests>=config['max_requests']-1:break
    return items,{'pending':pending,'seen':sorted(seen),'inventories':inventories,'inventories_seen':inventories_seen},not pending and not inventories


def github(config,cursor,fetcher):
    state=dict(cursor);repo_index=state.get('repo',0)
    if repo_index>=len(config['repositories']):return [],{},True
    repo=config['repositories'][repo_index];base='https://api.github.com/repos/'+repo
    def get(path):
        raw,_,media=fetcher.get(base+path)
        if media not in ('application/json','text/json'):raise CollectionError('github_response_invalid')
        return json.loads(raw)
    metadata=get('')
    if metadata.get('private') is not False or type(metadata.get('id')) is not int or metadata['id']<=0:
        raise CollectionError('public_github_repository_required')
    if state.get('repository_id',metadata['id'])!=metadata['id']:raise CollectionError('github_identity_changed')
    state['repository_id']=metadata['id'];stream=state.get('stream',0);kind=config['include'][stream]
    items=[]
    if kind=='files':
        commit=state.get('commit') or get('/commits/'+quote(config['ref'],safe=''))['sha'];state['commit']=commit
        tree=get('/git/trees/'+commit+'?recursive=1')
        if tree.get('truncated'):raise CollectionError('github_inventory_incomplete')
        binary={'.png','.jpg','.jpeg','.gif','.webp','.ico','.pdf','.docx','.zip','.gz','.bz2','.xz','.7z','.woff','.woff2','.ttf','.otf','.mp3','.mp4','.ogg','.exe','.dll','.so','.o','.a','.jar','.pyc','.class','.sqlite','.db','.iso'}
        files=[v for v in tree.get('tree',[]) if v.get('type')=='blob' and PurePosixPath(v['path']).suffix.lower() not in binary
               and any(fnmatch.fnmatch(v['path'],p) for p in config['paths'])
               and not any(fnmatch.fnmatch(v['path'],p) for p in config['exclude'])]
        index=state.get('index',0)
        for record in files[index:index+min(config['max_items'],max(1,config['max_requests']-3))]:
            if record.get('size',0)>config['max_bytes']:raise CollectionError('github_file_too_large')
            blob=get('/git/blobs/'+record['sha'])
            body=base64.b64decode(blob['content'].replace('\n',''),validate=True)
            url='https://github.com/'+repo+'/blob/'+commit+'/'+quote(record['path'],safe='/')
            items.append(item(str(metadata['id'])+':file:'+record['path'],record['path'],body,url,
                              'text/markdown' if record['path'].endswith(('.md','.markdown')) else 'text/plain',
                              repository_id=metadata['id'],commit=commit,path=record['path']))
            index+=1
        state['index']=index;done=index>=len(files)
    else:
        endpoint={'issues':'issues','pull_requests':'pulls','releases':'releases'}[kind]
        page=state.get('page',1)
        rows=get('/'+endpoint+'?state=all&per_page='+str(config['max_items'])+'&page='+str(page))
        if type(rows) is not list:raise CollectionError('github_response_invalid')
        for row in rows:
            if kind=='issues' and 'pull_request' in row:continue
            body=(row.get('title') or row.get('name') or kind)+'\n\n'+(row.get('body') or '')
            items.append(item(str(metadata['id'])+':'+kind+':'+str(row['id']),row.get('title') or row.get('name') or kind,
                              body.encode(),row['html_url'],repository_id=metadata['id'],updated_at=row.get('updated_at')))
        state['page']=page+1;done=len(rows)<config['max_items']
    if done:
        state={'repo':repo_index,'stream':stream+1,'repository_id':metadata['id']}
        if stream+1>=len(config['include']):state={'repo':repo_index+1}
    return items,state,state.get('repo',0)>=len(config['repositories'])
