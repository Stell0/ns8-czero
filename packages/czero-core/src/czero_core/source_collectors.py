# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Public-source batches over the existing DNS-pinned transport and HTML converter."""
import base64
from html.parser import HTMLParser
import fnmatch
import hashlib
import json
import re
import time
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote, urlsplit
from urllib.robotparser import RobotFileParser

from .source_http import Fetcher, CollectionError
from .source_html import configuration, boundary, extract, normalize, parse_page


def validate(kind, config):
    if type(config) is not dict or len(json.dumps(config, allow_nan=False).encode())>16384:
        raise ValueError('invalid_source_configuration')
    allowed = {'max_bytes', 'max_requests', 'max_items', 'timeout'}
    allowed |= {'website', 'include', 'attachments'} if kind == 'website' else {'repositories', 'include', 'paths', 'exclude', 'ref'}
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
        if 'attachments' in config:
            result['attachments'] = attachment_configuration(config['attachments'])
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


def attachment_configuration(value):
    if type(value) is not dict or set(value) - {'allowed_roots', 'seeds', 'include', 'media_types', 'max_depth', 'page_queue'}:
        raise ValueError('invalid_website_attachments')
    result = {'seeds': [], 'include': [], 'media_types': ['application/pdf'], 'max_depth': 10, 'page_queue': False, **value}
    if type(result['page_queue']) is not bool or result['media_types'] != ['application/pdf'] or type(result['max_depth']) is not int or not 0 <= result['max_depth'] <= 20:
        raise ValueError('invalid_website_attachments')
    for name in ('allowed_roots', 'seeds', 'include'):
        values = result.get(name)
        if type(values) is not list or len(values) > 100 or any(type(v) is not str or not v or len(v) > 512 for v in values):
            raise ValueError('invalid_website_attachments')
    if not result['allowed_roots']:
        raise ValueError('invalid_website_attachments')
    for name in ('allowed_roots', 'seeds'):
        result[name] = [normalize(url) for url in result[name]]
        if any(urlsplit(url).scheme != 'https' for url in result[name]):
            raise ValueError('invalid_website_attachments')
    if any(urlsplit(url).query for url in result['allowed_roots']):
        raise ValueError('invalid_website_attachments')
    for url in result['seeds']:
        attachment_boundary(url, result)
    return result


def matches(url, patterns):
    path = urlsplit(url).path
    return any(fnmatch.fnmatchcase(url, pattern) or fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def attachment_boundary(url, options):
    url = boundary(url, options)
    if options['include'] and not matches(url, options['include']):
        raise CollectionError('website_attachment_path_excluded')
    return url


def attachment_candidate(url, options):
    if unquote(urlsplit(url).path).lower().endswith('.pdf'):
        return True
    if not matches(url, options['include']):
        return False
    try:
        boundary(url, options)
    except CollectionError:
        return False
    return True


def attachment_key(url):
    return hashlib.sha256(('pdf:' + url).encode()).hexdigest()


def strong_etag(value):
    return value if isinstance(value, str) and re.fullmatch(r'"[!#-~]{1,128}"', value) else None


def attachment(url, parent, raw, *, requested):
    if not raw.startswith(b'%PDF-'):
        raise CollectionError('website_attachment_invalid_signature')
    digest = hashlib.sha256(raw).hexdigest()
    name = unquote(urlsplit(url).path.rsplit('/', 1)[-1]) or url
    return {
        'key': attachment_key(url),
        'title': (''.join(ch for ch in name if ch.isprintable()).strip() or 'PDF')[:256],
        'body': raw,
        'media_type': 'application/pdf',
        'metadata': {
            'source_type': 'website_attachment', 'attachment_type': 'application/pdf',
            'original_url': requested, 'canonical_url': url, 'parent_discovery_url': parent,
            'original_sha256': digest,
        },
    }


def item(key, title, body, url, media='text/markdown', **provenance):
    if not body or len(body)>2*1024*1024:
        raise CollectionError('source_content_too_large')
    try:body.decode('utf-8')
    except UnicodeError:raise CollectionError('source_non_text_file') from None
    return {'key':hashlib.sha256(key.encode()).hexdigest(), 'title':title[:256], 'body':body,
            'media_type':media, 'metadata':{'original_url':url, **provenance}}


def collect(kind, config, cursor, *, fetcher=None, preview=False, github_token=None, attachment_validator=None):
    config=validate(kind,config)
    fetcher=fetcher or Fetcher(config,accept_json=kind=='github',github_token=github_token if kind=='github' else None)
    try:
        return website(config,cursor,fetcher,preview=preview,attachment_validator=attachment_validator) if kind=='website' else github(config,cursor,fetcher)
    finally:
        fetcher.close()


def website(config,cursor,fetcher,*,preview=False,attachment_validator=None):
    options=config['website']
    attachments = config.get('attachments')
    attachment_pending = dict(cursor.get('attachment_pending', {url: None for url in attachments['seeds']} if attachments else {}))
    attachment_retry_after = cursor.get('attachment_retry_after', '')
    attachment_seen = set(cursor.get('attachment_seen', ()))
    attachment_failures = dict(cursor.get('attachment_failures', {}))
    html_failures = dict(cursor.get('html_failures', {}))
    attachment_selected = cursor.get('attachment_selected', len(attachment_pending))
    depths = dict(cursor.get('depths', {}))
    depth_limited = cursor.get('depth_limited', False)
    deadline = time.monotonic() + (10 if preview else 20) if attachments else None
    pending=list(cursor.get('pending',options['seeds']))
    inventories=list(cursor.get('inventories',options['sitemaps']))
    inventories_seen=list(cursor.get('inventories_seen',[]))
    seen=set(cursor.get('seen',[]));items=[];robots={}
    initial_bytes=getattr(fetcher,'downloaded',0)
    def response(url,**kwargs):
        if deadline is not None:
            kwargs['deadline'] = deadline
            kwargs['batch_limit'] = options['max_total_bytes']
        return fetcher.response(url,remaining_bytes=lambda:options['max_total_bytes']-(getattr(fetcher,'downloaded',0)-initial_bytes),**kwargs)
    def rules(url):
        parsed=urlsplit(url);origin=parsed.scheme+'://'+parsed.netloc
        if origin not in robots:
            robots_url = origin + '/robots.txt'
            if attachments:
                # Robots redirects stay on the same origin and remain DNS-pinned.
                boundary(robots_url, {'allowed_roots': options['allowed_roots'] + attachments['allowed_roots']}, inventory=True)
            else:
                boundary(robots_url, options, inventory=True)
            raw,_,_,head=response(robots_url,allow_status=(200,404,410,401,403),
                                  **({'reject_media': ('application/pdf',)} if attachments else {}))
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
    def budget_error(error):
        return str(error) in ('source_request_budget_exhausted', 'source_time_budget_exhausted',
                              'source_byte_budget_exhausted')

    def record_html_failure(error):
        nonlocal attachment_retry_after
        code = str(error)
        if code.startswith('source_http_'):
            code = 'source_http_error'
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
            code = 'website_collection_incomplete'
        html_failures[code] = html_failures.get(code, 0) + 1
        attachment_retry_after = max(attachment_retry_after, getattr(error, 'retry_after', ''))

    def discover_attachment(target, parent, *, required=False):
        nonlocal attachment_selected
        if not attachments or not attachment_candidate(target, attachments):
            return False
        try:
            target = attachment_boundary(target, attachments)
        except CollectionError as error:
            if required:
                code = 'website_attachment_destination_not_approved'
                attachment_failures[code] = 1 + attachment_failures.get(code, 0)
            if preview and len(items) < config['max_items']:
                items.append({'title': target, 'metadata': {'original_url': target}, 'kind': 'pdf',
                              'selection': 'skipped', 'reason': str(error)})
        else:
            if target not in attachment_seen and target not in attachment_pending:
                attachment_pending[target] = parent
                attachment_selected += 1
        return True

    def draw_attachments():
        nonlocal attachment_retry_after
        while (attachment_pending and len(items) < config['max_items']
               and fetcher.requests < config['max_requests'] - 1):
            url = next(iter(attachment_pending))
            parent = attachment_pending[url]
            if url in attachment_seen:
                del attachment_pending[url]
                continue
            def checked_attachment(target):
                attachment_boundary(target, attachments)
                if not rules(target).can_fetch('c0-projects', target):
                    raise CollectionError('website_attachment_robots_denied')
            result = None
            try:
                etag = strong_etag(attachment_validator(url)) if attachment_validator else None
                raw, final, media, head = response(url, validate_url=checked_attachment, interval=delay_for,
                    headers={'Accept': 'application/pdf'}, allow_status=(200, 304) if etag else (200,),
                    first_request_headers={'If-None-Match': etag} if etag else None)
                if head['status'] == 304:
                    if etag and final == url and not head.get('redirects') and strong_etag(head.get('etag')) == etag:
                        items.append({'key': attachment_key(url), 'media_type': 'application/pdf',
                                      'not_modified': True})
                        del attachment_pending[url]
                        attachment_seen.add(url)
                        continue
                    # Weak comparison is allowed by HTTP for If-None-Match.
                    # Exact retained bytes need an exact strong validator.
                    raw, final, media, head = response(url, validate_url=checked_attachment, interval=delay_for,
                        headers={'Accept': 'application/pdf'})
                if media != 'application/pdf':
                    raise CollectionError('website_attachment_unsupported_media')
                direct = final == url and not head.get('redirects')
                final = attachment_boundary(final, attachments)
                if final not in attachment_seen:
                    result = attachment(final, parent, raw, requested=url)
                    validator = strong_etag(head.get('etag'))
                    if validator and direct:
                        result['metadata']['http_etag'] = validator
                    attachment_seen.add(final)
                    if preview:
                        result.update(kind='pdf', selection='selected')
            except CollectionError as error:
                if budget_error(error):
                    break
                code = str(error)
                if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', code):
                    code = 'website_attachment_failed'
                attachment_retry_after = max(attachment_retry_after, getattr(error, 'retry_after', ''))
                group = 'source_http_error' if code.startswith('source_http_') else code
                attachment_failures[group] = 1 + attachment_failures.get(group, 0)
                if preview:
                    result = {'title': url, 'metadata': {'original_url': url}, 'kind': 'pdf',
                              'selection': 'skipped', 'reason': code}
            if result:
                items.append(result)
            del attachment_pending[url]
            attachment_seen.add(url)

    if attachments:
        draw_attachments()
    # Inventory URLs are explicit configuration and obey the same public boundary.
    while inventories and fetcher.requests < config['max_requests']-2:
        url=inventories[0]
        boundary(url,options,inventory=True)
        try:
            rule=rules(url)
        except CollectionError as error:
            if attachments and budget_error(error): break
            raise
        if not rule.can_fetch('c0-projects',url):
            inventories.pop(0);inventories_seen.append(url);continue
        def checked_inventory(target):
            if attachments and attachment_candidate(normalize(target), attachments):
                raise CollectionError('website_invalid_sitemap')
            boundary(target,options,inventory=True)
            if not rules(target).can_fetch('c0-projects',target):
                raise CollectionError('website_redirect_robots_denied')
        try:
            raw,_,_,_=response(url,validate_url=checked_inventory,interval=delay_for,
                               **({'reject_media': ('application/pdf',)} if attachments else {}))
        except CollectionError as error:
            if attachments and budget_error(error): break
            raise
        if len(raw)>2*1024*1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise CollectionError('website_invalid_sitemap')
        try:tree=ET.fromstring(raw)
        except ET.ParseError:raise CollectionError('website_invalid_sitemap') from None
        index=tree.tag.rsplit('}',1)[-1]=='sitemapindex'
        for node in tree:
            location=next((v.text for v in node if v.tag.rsplit('}',1)[-1]=='loc'),None)
            if not location:continue
            try:
                if not index and discover_attachment(normalize(location), url):
                    continue
                target = boundary(location, options, inventory=index)
            except (CollectionError, ValueError):
                continue
            if index:
                if target not in inventories and target not in inventories_seen:inventories.append(target)
            elif target not in pending and target not in seen:pending.append(target)
        inventories.pop(0);inventories_seen.append(url)
        if len(inventories)+len(inventories_seen)+len(pending)+len(attachment_pending)>10000:raise CollectionError('website_frontier_limit')
    while pending and len(items)<config['max_items'] and fetcher.requests<config['max_requests']-1:
        url=pending[0]
        if url in seen:
            pending.pop(0);continue
        boundary(url,options)
        if discover_attachment(url, None, required=True):
            pending.pop(0)
            seen.add(url)
            draw_attachments()
            continue
        parsed=urlsplit(url)
        try:
            rule=rules(url)
        except CollectionError as error:
            if not attachments:
                raise
            if budget_error(error):
                break
            record_html_failure(error)
            pending.pop(0)
            seen.add(url)
            depths.pop(url, None)
            continue
        if (not rule.can_fetch('c0-projects',url) or
                any(fnmatch.fnmatch(url,p) or fnmatch.fnmatch(parsed.path,p) for p in options['exclude'])):
            pending.pop(0);seen.add(url);continue
        def checked(target):
            if discover_attachment(normalize(target), url, required=True):
                raise CollectionError('website_attachment_redirect')
            boundary(target,options)
            if not rules(target).can_fetch('c0-projects',target):
                raise CollectionError('website_redirect_robots_denied')
        try:
            raw,final,media,_=response(url,validate_url=checked,interval=delay_for,
                                     **({'reject_media': ('application/pdf',)} if attachments else {}))
            if media not in ('text/html','application/xhtml+xml'):
                raise CollectionError('website_unsupported_media')
        except CollectionError as error:
            if not attachments:
                raise
            if budget_error(error):
                break
            pending.pop(0)
            seen.add(url)
            depths.pop(url, None)
            if str(error) == 'website_attachment_redirect':
                draw_attachments()
            else:
                record_html_failure(error)
            continue
        if preview:
            # HTTP previews never run article selectors; the worker owns conversion.
            class Title(HTMLParser):
                inside=False
                text=''
                def __init__(self):
                    super().__init__()
                    self.links = []
                def handle_starttag(self,tag,attrs):
                    if tag=='title':self.inside=True
                    if attachments and tag == 'a' and len(self.links) < 10001:
                        self.links.extend(value for key, value in attrs if key == 'href' and value)
                def handle_endtag(self,tag):
                    if tag=='title':self.inside=False
                def handle_data(self,data):
                    if self.inside:self.text=(self.text+data)[:256]
            title=Title();title.feed(raw.decode('utf-8-sig'))
            items.append({'title':title.text or final,'metadata':{'original_url':final},
                          **({'kind': 'html', 'selection': 'selected'} if attachments else {})})
            links=title.links
            canonical=final
        else:
            canonical, links = final, []
            selected = not config['include'] or matches(url, config['include'])
            try:
                page = parse_page(raw, final)
                links = page[1]
                if selected or not attachments:
                    title, body, canonical, links, metadata = extract(raw, final, options, page=page)
                    if selected:
                        items.append(item(canonical, title, body, canonical, **metadata))
            except CollectionError as error:
                if not attachments:
                    raise
                record_html_failure(error)
        pending.pop(0);seen.add(url)
        depth = depths.pop(url, 0)
        if attachments and len(links) >= 10000:
            depth_limited = True
        for link in links:
            try:
                target = normalize(link, final)
            except (CollectionError, ValueError):
                continue
            if discover_attachment(target, canonical):
                continue
            if preview:
                continue
            try:target=boundary(target,options)
            except CollectionError:continue
            if target not in seen and target not in pending:
                if attachments and depth >= attachments['max_depth']:
                    depth_limited = True
                    continue
                pending.append(target)
                if attachments:
                    depths[target] = depth + 1
        if len(pending)+len(seen)+len(attachment_pending)+len(attachment_seen)>10000:
            raise CollectionError('website_frontier_limit')
        if attachments:
            draw_attachments()
        if fetcher.requests>=config['max_requests']-1:break
    if attachments:
        draw_attachments()
    state = {'pending':pending,'seen':sorted(seen),'inventories':inventories,'inventories_seen':inventories_seen}
    if attachments:
        if not preview and not items and (pending or inventories or attachment_pending) and (
            pending == cursor.get('pending', options['seeds']) and
            inventories == cursor.get('inventories', options['sitemaps']) and
            attachment_pending == cursor.get('attachment_pending', {url: None for url in attachments['seeds']})
        ):
            raise CollectionError('website_collection_budget_stalled')
        state.update(attachment_pending=attachment_pending, attachment_seen=sorted(attachment_seen),
                     attachment_failures=attachment_failures, html_failures=html_failures,
                     attachment_retry_after=attachment_retry_after,
                     attachment_selected=attachment_selected,
                     depths=depths, depth_limited=depth_limited)
    return items, state, not pending and not inventories and not attachment_pending


def github(config,cursor,fetcher):
    state=dict(cursor);repo_index=state.get('repo',0)
    if repo_index>=len(config['repositories']):return [],{},True
    repo=config['repositories'][repo_index];base='https://api.github.com/repos/'+repo
    def get(path):
        raw,_,media=fetcher.get(base+path)
        if media not in ('application/json','text/json'):raise CollectionError('github_response_invalid')
        return json.loads(raw)
    try:metadata=get('')
    except CollectionError as error:
        if str(error)=='source_http_404':raise CollectionError('github_repository_unavailable') from None
        raise
    if metadata.get('private') is not False or type(metadata.get('id')) is not int or metadata['id']<=0:
        raise CollectionError('github_repository_unavailable')
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
