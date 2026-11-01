# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Export selected published Freshdesk FAQs into the existing C0 source workflow.

Category/folder traversal, blacklist selection and title/body mapping adapted
from NethServer/Freshdesk2S3 (GPLv3). No S3, tickets or Freshdesk writes.
"""
import argparse
import base64
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin,urlsplit
from uuid import uuid4

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from c0_ingest.auth import locked
from c0_ingest.config import connection_settings
from c0_ingest.errors import C0Error
from c0_ingest.jobs import check_job
from c0_ingest.state import atomic,read
from c0_projects.cli import save_scan,state_directory
from c0_projects.fetch import Fetcher,FetchError
from c0_projects.model import Batch,Item,load_config,now,public_url,sha

ENV_KEYS={'FRESHDESK_DOMAIN','FRESHDESK_SOLUTIONS_DOMAIN','FRESHDESK_API_KEY',
          'CATEGORY_BLACKLIST','ARTICLE_ID_BLACKLIST'}
EXTRACTOR='freshdesk-markdown-1'


def settings(path):
    """Read only this adapter's literal values; never execute/source .env."""
    values={}
    for line in Path(path).read_text().splitlines():
        key,sep,value=line.partition('=')
        if not sep or key not in ENV_KEYS:continue
        if key in values:raise C0Error('duplicate_freshdesk_environment_key')
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:raise C0Error('invalid_freshdesk_environment_value')
            value=value[1:-1]
        if '\0' in value:raise C0Error('invalid_freshdesk_environment_value')
        values[key]=value
    host=values.get('FRESHDESK_DOMAIN','').removeprefix('https://').rstrip('/').lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.freshdesk\.com',host):raise C0Error('explicit_freshdesk_api_host_required')
    key=values.get('FRESHDESK_API_KEY','')
    if not key or any(ord(c)<33 or ord(c)>126 for c in key):raise C0Error('freshdesk_api_key_required')
    portal=values.get('FRESHDESK_SOLUTIONS_DOMAIN') or host
    portal=public_url(portal if portal.startswith('https://') else 'https://'+portal).rstrip('/')
    if urlsplit(portal).scheme!='https' or urlsplit(portal).path or urlsplit(portal).query:
        raise C0Error('explicit_https_portal_origin_required')
    blocked=[v.strip() for v in values.get('ARTICLE_ID_BLACKLIST','').split(',') if v.strip()]
    if any(not v.isdecimal() or int(v)<1 for v in blocked):raise C0Error('invalid_article_blacklist')
    return {'api_origin':'https://'+host,'portal_origin':portal,'api_key':key,
            'excluded_categories':[v.strip() for v in values.get('CATEGORY_BLACKLIST','').split(',') if v.strip()],
            'excluded_articles':sorted({int(v) for v in blocked})}


class API:
    def __init__(self,config,cache,*,maximum=500,seconds=1800,fetcher=None):
        if type(maximum) is not int or not 1<=maximum<=500 or not 1<=seconds<=3600:raise C0Error('invalid_freshdesk_budget')
        self.config=config;self.cache=Path(cache);self.cache.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.fetcher=fetcher or Fetcher({'max_requests':maximum,'max_bytes':2*1024*1024,'timeout':20},accept_json=True)
        self.deadline=time.monotonic()+seconds
    def get(self,path,page=None):
        if not re.fullmatch(r'/api/v2/solutions/(?:categories(?:/\d+/folders)?|folders/\d+(?:/subfolders|/articles)?|articles/\d+)',path):
            raise C0Error('freshdesk_endpoint_denied')
        if page is not None and (type(page) is not int or not 1<=page<=20):raise C0Error('freshdesk_page_limit')
        query=path+(f'?per_page=100&page={page}' if page is not None else '')
        saved=self.cache/(sha(query)+'.json')
        if saved.exists():
            row=read(saved)
            if row['query']!=query or row['hash']!=sha(row['data']):raise C0Error('freshdesk_cache_changed')
            return row['data']
        if time.monotonic()>=self.deadline:raise C0Error('freshdesk_execution_budget_exhausted')
        url=self.config['api_origin']+query
        def validate(value):
            if value!=url:raise C0Error('freshdesk_authenticated_redirect_denied')
        raw,_,media,_=self.fetcher.response(url,headers={'Authorization':'Basic '+base64.b64encode((self.config['api_key']+':X').encode()).decode()},validate_url=validate,interval=.25)
        if media!='application/json':raise C0Error('freshdesk_non_json_response')
        try:data=json.loads(raw)
        except ValueError:raise C0Error('freshdesk_invalid_json') from None
        atomic(saved,{'query':query,'data':data,'hash':sha(data),'fetched_at':now()})
        return data
    def pages(self,path):
        seen=set()
        for page in range(1,21):
            rows=self.get(path,page)
            if not isinstance(rows,list) or len(rows)>100:raise C0Error('freshdesk_invalid_inventory')
            for row in rows:
                if not isinstance(row,dict) or type(row.get('id')) is not int:raise C0Error('freshdesk_invalid_identity')
                if row['id'] in seen:raise C0Error('freshdesk_repeated_inventory_page')
                seen.add(row['id']);yield row
            if len(rows)<100:return
        raise C0Error('freshdesk_page_limit')
    def close(self):self.fetcher.close()


def markdown(article,url):
    title=article.get('title');html=article.get('description')
    if not isinstance(title,str) or not title.strip() or not isinstance(html,str):raise C0Error('freshdesk_empty_article')
    soup=BeautifulSoup(html,'html.parser')
    if len(soup.find_all(True,limit=100001))>100000 or soup.select_one('input[type=password]'):
        raise C0Error('freshdesk_defective_article')
    for node in soup.select('script,style,iframe,form,object,embed'):node.decompose()
    if not soup.get_text(strip=True):raise C0Error('freshdesk_empty_article')
    for node in soup.select('[href],[src]'):
        for attr in ('href','src'):
            if attr not in node.attrs:continue
            value=urljoin(url,node[attr])
            if urlsplit(value).scheme not in ('https','http','mailto'):
                del node[attr]
            else:node[attr]=value
    def language(pre):
        for node in (pre,pre.find('code')):
            for cls in node.get('class',[]) if node else []:
                match=re.fullmatch(r'(?:language|lang)-([A-Za-z0-9_+.-]{1,40})',cls)
                if match:return match[1]
        return ''
    body=MarkdownConverter(heading_style='ATX',bullets='-',wrap=False,strip_pre=None,
        table_infer_header=True,code_language_callback=language).convert_soup(soup)
    return ('# '+title.strip()+'\n\n'+body.replace('\r\n','\n').replace('\r','\n').strip()+'\n').encode()


def collect(api,connector,config):
    """Default-language Solutions; match the reference category/article selection."""
    items=[];inventory=[];seen=set();folders_seen=set();total=0
    def excluded(kind,row,reason):inventory.append({'kind':kind,'id':row['id'],'status':'excluded','reason':reason})
    def folder(row,category,depth=0):
        nonlocal total
        fid=row['id']
        if fid in folders_seen:return
        folders_seen.add(fid)
        if depth>4:raise C0Error('freshdesk_folder_depth_limit')
        for article in api.pages(f'/api/v2/solutions/folders/{fid}/articles'):
            aid=article['id']
            if aid in seen:continue
            seen.add(aid)
            if aid in config['excluded_articles']:excluded('article',article,'article_blacklist');continue
            if article.get('status')!=2:excluded('article',article,'draft_or_unknown_status');continue
            full=api.get(f'/api/v2/solutions/articles/{aid}')
            if not isinstance(full,dict) or type(full.get('id')) is not int or full['id']!=aid:raise C0Error('freshdesk_article_identity_changed')
            if full.get('status')!=2:excluded('article',article,'no_longer_published');continue
            if full.get('folder_id')!=fid:raise C0Error('freshdesk_article_moved_during_scan')
            url=config['portal_origin']+f'/support/solutions/articles/{aid}'
            content=markdown(full,url);total+=len(content)
            if len(items)>=connector['max_items'] or total>32*1024*1024:raise C0Error('freshdesk_item_or_byte_budget_exhausted')
            language=full.get('language') or ''
            item=Item(connector['id'],str(aid)+'.md',full['title'],content,'text/markdown',url,url,
                full.get('created_at') or '',full.get('updated_at') or '',
                provenance={'source_type':'freshdesk_faq','article_id':aid,'category_id':category['id'],
                    'category':category['name'],'folder_id':fid,'folder':row['name'],'language':language,
                    'extractor':EXTRACTOR,'source_hash':sha(full['description'].encode()),'tags':full.get('tags',[])})
            items.append(item);inventory.append({'kind':'article','id':aid,'status':'selected','canonical_url':url,'content_hash':item.content_hash})
        if row.get('sub_folders_count',0):
            for child in api.pages(f'/api/v2/solutions/folders/{fid}/subfolders'):folder(child,category,depth+1)
    for category in api.pages('/api/v2/solutions/categories'):
        if category['name'] in config['excluded_categories']:excluded('category',category,'category_blacklist');continue
        for row in api.pages(f"/api/v2/solutions/categories/{category['id']}/folders"):folder(row,category)
    return Batch(items=items,cursor={'complete':True,'selected':len(items),'inventory_hash':sha(inventory)}),inventory


def scan(job,config_path,env_path,relative,*,resume=False,maximum=500,seconds=1800):
    check_job(job);config=load_config(config_path);connection=connection_settings(job)
    if (config['server_url'],config['project_space_id'])!=(connection['url'],connection['space_id']):raise C0Error('configured_instance_or_space_binding_mismatch')
    if len(config['sources'])!=1 or config['sources'][0]['adapter']!='local_files':raise C0Error('faq_requires_one_local_export_connector')
    definition=config['sources'][0];state=state_directory(job,relative)
    if state==state_directory(job):raise C0Error('faq_requires_separate_source_state')
    if definition['root']!=relative+'/export':raise C0Error('faq_export_requires_its_private_state_directory')
    state.mkdir(parents=True,mode=0o700,exist_ok=True)
    source=settings(env_path);identity=sha({k:v for k,v in source.items() if k!='api_key'}|{'definition':definition,'extractor':EXTRACTOR})
    with locked(state/'scan.lock'):
        previous=read(state/'crawl.json',{})
        if previous and not previous['complete'] and not resume:raise C0Error('saved_freshdesk_scan_requires_resume')
        if resume and (not previous or previous['selection_hash']!=identity):raise C0Error('freshdesk_resume_selection_changed')
        failure=read(state/'scan-failure.json',{})
        if resume and failure.get('retry_after') and datetime.fromisoformat(failure['retry_after'])>datetime.now(timezone.utc):
            raise C0Error('freshdesk_retry_deferred')
        cycle=previous['cycle'] if resume else uuid4().hex
        atomic(state/'crawl.json',{'cycle':cycle,'complete':False,'selection_hash':identity})
        api=API(source,state/'cache'/cycle,maximum=maximum,seconds=seconds)
        try:
            batch,inventory=collect(api,definition,source)
            if not batch.items:raise C0Error('freshdesk_empty_selection_requires_review')
            directory=state/'scans'/cycle
            if directory.exists():raise C0Error('saved_faq_scan_already_exists')
            manifest=save_scan(directory,[(definition,batch)])
            export=job/definition['root'];export.mkdir(parents=True,mode=0o700,exist_ok=True)
            for item in batch.items:atomic(export/item.external_id,item.content)
            atomic(state/'inventory.json',inventory)
            atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest)})
            atomic(state/'crawl.json',{'cycle':cycle,'complete':True,'selection_hash':identity,'items':len(batch.items)})
            return {'status':'scanned','items':len(batch.items),'excluded':len(inventory)-len(batch.items),'requests':api.fetcher.requests,'writes_c0':0}
        except (C0Error,KeyError,TypeError,UnicodeError) as error:
            code=str(error) if isinstance(error,C0Error) else 'freshdesk_invalid_response'
            atomic(state/'scan-failure.json',{'status':'partial','error':code,'retry_after':getattr(error,'retry_after',''),'cycle':cycle})
            raise C0Error(code) from None
        finally:api.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['scan','sync','resume','status','verify'])
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--env',type=Path);parser.add_argument('--state-directory',default='data/freshdesk-faq')
    parser.add_argument('--continue-scan',action='store_true');parser.add_argument('--max-requests',type=int,default=500)
    parser.add_argument('--seconds',type=int,default=1800);mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true');mode.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv);os.umask(0o077)
    if args.command=='scan':
        if not args.env or args.apply or args.dry_run:parser.error('scan requires --env and never writes C0')
        try:print(json.dumps(scan(args.job,args.config,args.env,args.state_directory,resume=args.continue_scan,maximum=args.max_requests,seconds=args.seconds)));return 0
        except (C0Error,OSError,ValueError) as error:
            print(json.dumps({'status':'blocked','error':str(error) if isinstance(error,C0Error) else 'private_faq_configuration_unavailable'}));return 1
    if args.env:parser.error('--env is used only by scan; publication reuses the saved snapshot')
    from c0_projects.cli import main as project_main
    operation='resume' if args.command in ('sync','resume') else args.command
    if operation=='resume' and not (args.apply or args.dry_run):parser.error('choose --apply or --dry-run')
    arguments=['sources',operation,'--job',str(args.job),'--config',str(args.config),
               '--state-directory',args.state_directory,'--batch-extraction']
    if args.apply:arguments.append('--apply')
    if args.dry_run:arguments.append('--dry-run')
    return project_main(arguments)


if __name__=='__main__':raise SystemExit(main())
