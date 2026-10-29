# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic, bounded documentation collection; fetched instructions are data."""
import fnmatch
import json
from pathlib import Path
import re
import time
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone
from xml.etree.ElementTree import ParseError
from urllib.parse import parse_qsl,urlencode,urljoin,urlsplit,urlunsplit,unquote
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from c0_ingest.errors import C0Error
from c0_ingest.state import atomic,read,safe_path
from .fetch import Fetcher,FetchError
from .model import Item,Batch,now,public_url,sha

EXTRACTOR='markdownify-1.2.3/c0-website-1'
DEFAULTS={'seeds':[],'allowed_roots':[],'sitemaps':[],'exclude':[],
    'profile':'generic','selectors':[],'remove_selectors':[],
    'language':'','product':'','product_version':'','manual':'',
    'interval_ms':1000,'max_total_bytes':33554432,'max_cache_pages':1000,
    'configuration_version':'1'}
SELECTORS={'docusaurus':['article .theme-doc-markdown','.theme-doc-markdown','article'],
    'sphinx':['[role=main] .body','[role=main]','div.document div.body','article'],
    'generic':['article','main']}
NOISE='script,style,noscript,svg,nav,footer,header,form,button,.table-of-contents,.theme-doc-toc-mobile,.theme-doc-breadcrumbs,.theme-doc-footer,.headerlink,.copybutton,.copy-code-button,.toc-backref > span'
TRACKING={'fbclid','gclid','dclid','msclkid','mc_cid','mc_eid'}
MAX_FRONTIER=10000


def normalize(url,base=''):
    absolute=urljoin(base,url);parts=urlsplit(absolute)
    # No path case-folding, slash folding, locale/version stripping or query sort:
    # those operations can merge distinct resources on a documentation server.
    query=[(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
    result=urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path or '/',urlencode(query),''))
    return public_url(result)


def configuration(value):
    if type(value) is not dict or set(value)-DEFAULTS.keys():raise C0Error('invalid_website_configuration')
    result={**DEFAULTS,**value}
    for field in ('seeds','allowed_roots','sitemaps','exclude','selectors','remove_selectors'):
        values=result[field]
        if type(values) is not list or len(values)>100 or any(type(v) is not str or not v or len(v)>4096 for v in values):
            raise C0Error('invalid_website_selection')
    if not result['seeds'] or not result['allowed_roots'] or result['profile'] not in SELECTORS:
        raise C0Error('explicit_documentation_roots_required')
    for field in ('seeds','allowed_roots','sitemaps'):
        result[field]=[normalize(v) for v in result[field]]
    for field in ('language','product','product_version','manual','configuration_version'):
        if type(result[field]) is not str or len(result[field])>128 or '\0' in result[field]:raise C0Error('invalid_website_metadata')
    for field,low,high in (('interval_ms',100,60000),('max_total_bytes',65536,67108864),('max_cache_pages',1,1000)):
        if type(result[field]) is not int or not low<=result[field]<=high:raise C0Error('invalid_website_limit')
    for seed in result['seeds']:boundary(seed,result)
    for url in result['sitemaps']:boundary(url,result,inventory=True)
    return result


def boundary(url,config,*,inventory=False):
    url=normalize(url);parsed=urlsplit(url)
    decoded=unquote(parsed.path)
    if '\\' in decoded or any(part in ('.','..') for part in decoded.split('/')):raise C0Error('website_path_escape')
    for root in config['allowed_roots']:
        allowed=urlsplit(root)
        if (parsed.scheme,parsed.netloc)!=(allowed.scheme,allowed.netloc):continue
        prefix=allowed.path.rstrip('/')
        if inventory or parsed.path==prefix or parsed.path.startswith(prefix+'/'):return url
    raise C0Error('website_destination_not_approved')


def extract(raw,url,config):
    try:html=raw.decode('utf-8-sig')
    except UnicodeError:raise C0Error('website_invalid_utf8') from None
    soup=BeautifulSoup(html,'html.parser')
    if len(soup.find_all(True,limit=100001))>100000:raise C0Error('website_dom_limit')
    links=[]
    for anchor in soup.select('a[href]',limit=MAX_FRONTIER):
        try:links.append(normalize(anchor['href'],url))
        except (C0Error,ValueError):continue
    canonical=soup.select_one('link[rel~=canonical][href]')
    canonical=boundary(normalize(canonical['href'],url),config) if canonical else url
    def partition(value):
        parsed=urlsplit(value)
        roots=[root for root in config['allowed_roots'] if urlsplit(root).scheme==parsed.scheme and urlsplit(root).netloc==parsed.netloc and (parsed.path==urlsplit(root).path.rstrip('/') or parsed.path.startswith(urlsplit(root).path.rstrip('/')+'/'))]
        return max(roots,key=len) if roots else None
    if partition(canonical)!=partition(url):raise C0Error('website_canonical_crosses_document_partition')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    selectors=config['selectors'] or SELECTORS[config['profile']]
    article=None
    for selector in selectors:
        nodes=soup.select(selector,limit=2)
        if len(nodes)==1 and nodes[0].get_text(strip=True):article=nodes[0];break
    if article is None:raise C0Error('website_article_missing_or_javascript_only')
    heading=article.find('h1');title=heading.get_text(' ',strip=True) if heading else title
    if (re.fullmatch(r'\s*(?:404(?:\s*[-:|].*)?|page not found|not found|pagina non trovata|sign in|log in|login)\s*',title,re.I)
            or article.select_one('input[type=password]')):raise C0Error('website_error_or_login_page')
    # Docusaurus/Sphinx tabs often contain server-rendered hidden variants. Keep
    # all panels and add their labels before removing interactive controls.
    for panel in article.select('[role=tabpanel]'):
        label=soup.find(id=panel.get('aria-labelledby',''))
        if label:
            heading=soup.new_tag('h3');heading.string=label.get_text(' ',strip=True);panel.insert(0,heading)
    for selector in [NOISE,*config['remove_selectors']]:
        for node in article.select(selector):node.decompose()
    for node in article.select('[href],[src]'):
        for attribute in ('href','src'):
            if attribute not in node.attrs:continue
            value=node[attribute]
            if attribute=='href' and value.startswith('#'):continue
            try:
                resolved=normalize(value,canonical)
                fragment=urlsplit(value).fragment
                node[attribute]=resolved+('#'+fragment if fragment and attribute=='href' else '')
            except (C0Error,ValueError):node.attrs.pop(attribute,None)
    def language(pre):
        for node in (pre,pre.find('code')):
            if node:
                for cls in node.get('class',[]):
                    match=re.fullmatch(r'(?:language|lang)-([A-Za-z0-9_+.-]{1,40})',cls)
                    if match:return match[1]
        return ''
    body=MarkdownConverter(heading_style='ATX',bullets='-',code_language_callback=language,
        table_infer_header=True,wrap=False,strip_pre=None).convert_soup(article)
    body=body.replace('\r\n','\n').replace('\r','\n').lstrip('\ufeff').strip()+'\n'
    if not body.strip() or '\0' in body:raise C0Error('website_empty_article')
    metadata={'source_type':'website','extractor':EXTRACTOR,'configuration_version':config['configuration_version'],
        **{key:config[key] for key in ('product','product_version','language','manual')},
        'path':[value for value in (config['manual'],*urlsplit(canonical).path.strip('/').split('/')) if value]}
    return title or canonical,body.encode(),canonical,links,metadata


def website(definition,*,root,fetcher=None,cursor=None,**_):
    config=configuration(definition['website']);batch=Batch();started=time.monotonic()
    fetcher=fetcher or Fetcher(definition)
    cache=Path(root)/'data/c0-projects/website'/definition['id']
    if any(p.is_symlink() for p in (cache,*cache.absolute().parents)):raise C0Error('unsafe_website_cache')
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    fingerprint=sha([EXTRACTOR,config]);state_path=cache/'frontier.json'
    state=read(state_path,{})
    if state.get('configuration')!=fingerprint or state.get('complete'):
        state={'configuration':fingerprint,'pending':config['seeds'][:],'seen':[],'aliases':{},'complete':False,
            'retry_after':state.get('retry_after','')}
    identities=read(cache/'identities.json',{})
    if type(identities) is not dict or len(identities)>MAX_FRONTIER:raise C0Error('website_identity_limit')
    robots={};metrics={'crawl_seconds':0.,'conversion_seconds':0.,'requests':0,'downloaded_bytes':0,'excluded':0,'not_modified':0}
    initial_requests=fetcher.requests;initial_bytes=getattr(fetcher,'downloaded',0)
    def persist():
        atomic(state_path,state)
        batch.cursor={'frontier_hash':sha(state),'complete':state['complete'],'pending':len(state['pending']),
            'visited':len(state['seen']),'metrics':metrics}
    def delay_for_url(url):
        parsed=urlsplit(url);origin=urlunsplit((parsed.scheme,parsed.netloc,'','',''))
        rule=robots.get(origin)
        delay=config['interval_ms']/1000
        if rule:
            delay=max(delay,rule.crawl_delay('c0-projects') or rule.crawl_delay('*') or 0)
            rate=rule.request_rate('c0-projects') or rule.request_rate('*')
            if rate:
                if rate.requests<=0 or rate.seconds<0:raise C0Error('website_invalid_robots_rate')
                delay=max(delay,rate.seconds/rate.requests)
        if delay>60:raise C0Error('website_robots_delay_exceeds_run_budget')
        return delay
    def fetch(url,*,inventory=False,headers=None,allow_status=(200,)):
        boundary(url,config,inventory=inventory)
        if getattr(fetcher,'downloaded',0)-initial_bytes>=config['max_total_bytes']:raise C0Error('website_byte_budget')
        def validate(value):
            boundary(value,config,inventory=inventory)
            # Redirect destinations need their own robots permission, including
            # a separately approved origin. Robots discovery itself is exempt.
            if urlsplit(url).path!='/robots.txt' and not rules(value).can_fetch('c0-projects',value):
                raise C0Error('website_redirect_robots_denied')
        start=time.monotonic()
        try:
            return fetcher.response(url,headers=headers,allow_status=allow_status,
                validate_url=validate,interval=delay_for_url,
                remaining_bytes=lambda:config['max_total_bytes']-(getattr(fetcher,'downloaded',0)-initial_bytes))
        finally:metrics['crawl_seconds']+=time.monotonic()-start
    def rules(url):
        parsed=urlsplit(url);origin=urlunsplit((parsed.scheme,parsed.netloc,'','',''))
        if origin in robots:return robots[origin]
        raw,_,_,headers=fetch(origin+'/robots.txt',inventory=True,allow_status=(200,404,410,401,403))
        rule=RobotFileParser()
        if headers['status'] in (401,403):
            rule.disallow_all=True;batch.partial('website_robots_access_denied')
        elif headers['status'] in (404,410):rule.allow_all=True
        else:rule.parse(raw.decode('utf-8-sig').splitlines())
        robots[origin]=rule
        return rule
    try:
        if state.get('retry_after') and datetime.fromisoformat(state['retry_after'])>datetime.now(timezone.utc):
            batch.partial('website_retry_deferred');batch.retry_after=state['retry_after'];return batch
        state.pop('retry_after',None)
        # Sitemap discovery precedes article traversal. A missing sitemap falls
        # back to navigation links; denied/failed inventories remain partial.
        if not state.get('sitemaps_done'):
            if 'sitemap_pending' not in state:
                pending=[(url,0) for url in config['sitemaps']]
                for seed in config['seeds']:
                    rule=rules(seed)
                    pending.extend((url,0) for url in (rule.site_maps() or []))
                if not pending:
                    pending=list(dict.fromkeys((urlunsplit((*urlsplit(root)[:2],'/sitemap.xml','','')),0) for root in config['allowed_roots']))
                state.update(sitemap_pending=pending,sitemap_seen=[],lastmod={})
                persist()
            pending=state['sitemap_pending'];processed=0
            while pending:
                url,depth=pending[0]
                if url in state['sitemap_seen']:pending.pop(0);continue
                if processed>=definition['max_pages']:
                    batch.partial('website_sitemap_inventory_limit');break
                if depth>definition['max_depth']:
                    state['inventory_incomplete']=True;pending.pop(0);persist();continue
                boundary(url,config,inventory=True)
                if not rules(url).can_fetch('c0-projects',url):
                    metrics['excluded']+=1;pending.pop(0);state['sitemap_seen'].append(url);persist();continue
                raw,_,media,head=fetch(url,inventory=True,allow_status=(200,404,410))
                if head['status']==200:
                    from .adapters import xml,tag,value
                    tree=xml(raw);index=tag(tree)=='sitemapindex'
                    for node in tree:
                        location=value(node,'loc')
                        if not location:continue
                        if len(state['pending'])+len(pending)+len(state['sitemap_seen'])>=MAX_FRONTIER:raise C0Error('website_frontier_limit')
                        try:target=boundary(location,config,inventory=index)
                        except C0Error:metrics['excluded']+=1;continue
                        if index:
                            if target not in state['sitemap_seen'] and not any(entry[0]==target for entry in pending):pending.append((target,depth+1))
                        else:
                            if target not in state['pending'] and target not in state['seen']:state['pending'].append(target)
                            modified=value(node,'lastmod')
                            if modified and len(modified)<=64:state['lastmod'][target]=modified
                pending.pop(0);state['sitemap_seen'].append(url);processed+=1;persist()
            state['sitemaps_done']=not pending
        if state.get('inventory_incomplete'):batch.partial('website_sitemap_depth_limit')
        published=set()
        while state['pending']:
            if len(batch.items)>=min(definition['max_items'],definition['max_pages']):batch.partial('website_page_budget');break
            url=state['pending'][0]
            if url in state['seen']:state['pending'].pop(0);continue
            try:boundary(url,config)
            except C0Error:state['pending'].pop(0);metrics['excluded']+=1;continue
            if any(fnmatch.fnmatch(url,pattern) or fnmatch.fnmatch(urlsplit(url).path,pattern) for pattern in config['exclude']):
                state['pending'].pop(0);state['seen'].append(url);metrics['excluded']+=1;continue
            rule=rules(url)
            if definition['include'] and not any(fnmatch.fnmatch(url,pattern) or fnmatch.fnmatch(urlsplit(url).path,pattern) for pattern in definition['include']):
                state['pending'].pop(0);state['seen'].append(url);metrics['excluded']+=1;continue
            if not rule.can_fetch('c0-projects',url):
                state['pending'].pop(0);state['seen'].append(url);metrics['excluded']+=1;continue
            key=sha(url.encode());record=read(cache/(key+'.json'),{})
            headers={}
            if record.get('etag'):headers['If-None-Match']=record['etag']
            if record.get('last_modified'):headers['If-Modified-Since']=record['last_modified']
            raw,final,media,head=fetch(url,headers=headers,allow_status=(200,304))
            if head['status']==304:
                metrics['not_modified']+=1
                raw_path=cache/(key+'.html')
                if raw_path.is_file() and not raw_path.is_symlink() and raw_path.stat().st_size<=definition['max_bytes']:
                    raw=raw_path.read_bytes();media=record.get('media','text/html');final=boundary(record.get('final',final),config)
                    if sha(raw)!=record.get('hash'):raw,final,media,head=fetch(url)
                else:raw,final,media,head=fetch(url)
            if media not in ('text/html','application/xhtml+xml'):raise C0Error('website_unsupported_media')
            start=time.monotonic()
            try:title,body,canonical,links,provenance=extract(raw,final,config)
            finally:metrics['conversion_seconds']+=time.monotonic()-start
            if len(record)==0 and len(list(cache.glob('*.html')))>=config['max_cache_pages']:raise C0Error('website_cache_page_limit')
            identity=record.get('identity') or identities.get(url) or identities.get(final) or identities.get(canonical) or canonical
            if any(identities.get(alias,identity)!=identity for alias in (url,final,canonical)):raise C0Error('website_canonical_identity_conflict')
            for alias in (url,final,canonical):
                if alias not in identities and len(identities)>=MAX_FRONTIER:raise C0Error('website_identity_limit')
                identities[alias]=identity
            atomic(cache/'identities.json',identities)
            atomic(cache/(key+'.html'),raw)
            atomic(cache/(key+'.json'),{'url':url,'final':final,'canonical':canonical,'identity':identity,'etag':head.get('etag') or record.get('etag',''),
                'last_modified':head.get('last_modified') or record.get('last_modified',''),'media':media,'extractor':fingerprint,'hash':sha(raw)})
            state['aliases'][url]=canonical
            if url in state.get('lastmod',{}):provenance['source_lastmod']=state['lastmod'][url]
            updated_at=''
            if head.get('last_modified') or record.get('last_modified'):
                try:
                    updated=parsedate_to_datetime(head.get('last_modified') or record['last_modified'])
                    if updated.tzinfo is not None:updated_at=updated.isoformat()
                except (ValueError,TypeError,OverflowError):pass
            if identity not in published:
                batch.add(Item(definition['id'],identity,title,body,'text/markdown',url,canonical,retrieved_at=now(),updated_at=updated_at,provenance=provenance));published.add(identity)
            # Use navigation captured from the entire page, before article noise
            # is removed. Outbound references never become trusted crawl roots.
            for link in links:
                try:link=boundary(link,config)
                except C0Error:continue
                if link not in state['seen'] and link not in state['pending']:
                    if len(state['pending'])+len(state['seen'])>=MAX_FRONTIER:raise C0Error('website_frontier_limit')
                    state['pending'].append(link)
            state['pending'].pop(0);state['seen'].append(url);persist()
        state['complete']=not state['pending'] and state.get('sitemaps_done',False) and batch.status=='complete'
    except FetchError as error:
        batch.partial(str(error));batch.retry_after=error.retry_after;state['retry_after']=error.retry_after
    except (C0Error,ValueError,UnicodeError,OSError,ParseError,RecursionError) as error:
        batch.partial(str(error) if isinstance(error,C0Error) else 'website_collection_failed')
    finally:
        metrics['requests']=fetcher.requests-initial_requests
        metrics['downloaded_bytes']=getattr(fetcher,'downloaded',0)-initial_bytes
        metrics['elapsed_seconds']=time.monotonic()-started
        persist();fetcher.close()
    return batch
