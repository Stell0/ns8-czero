# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Collectors return bounded evidence batches; they never publish C0 mutations."""
import base64
from contextlib import ExitStack
from email.utils import parsedate_to_datetime
import fnmatch
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import stat
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from c0_ingest.errors import C0Error
from github_vault.github_client import GitHubError
from .fetch import Fetcher, FetchError
from .model import Item, Batch, BatchLimit, now, public_url, sha

TEXT={'.md':'text/markdown','.markdown':'text/markdown','.txt':'text/plain','.rst':'text/plain',
    '.csv':'text/plain','.json':'text/plain','.yml':'text/plain','.yaml':'text/plain'}
BINARY={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
PRIVATE={'.env','oauth.json','auth.json','credentials.json','id_rsa','id_ed25519'}


def safe_read(root, relative, maximum):
    parts=Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('.','..') for p in parts):
        raise C0Error('unsafe_local_selection')
    with ExitStack() as stack:
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW); stack.callback(os.close,directory)
        for part in parts[:-1]:
            directory=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);stack.callback(os.close,directory)
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory); stack.callback(os.close,fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_size>maximum:
            raise C0Error('local_file_type_or_size_denied')
        content=bytearray()
        while len(content)<=maximum:
            part=os.read(fd,min(65536,maximum+1-len(content)))
            if not part: return bytes(content)
            content.extend(part)
        raise C0Error('local_file_too_large')


def local_files(config, *, root, cursor=None, **_):
    configured=Path(config['root']); base=(root/configured if not configured.is_absolute() else configured)
    if base.is_symlink() or not base.is_dir():
        raise C0Error('invalid_local_root')
    base=base.resolve(); batch=Batch(); visited=0
    selections=config.get('paths') or ['']
    candidates=set()
    for selected in selections:
        path=base/selected
        if not path.resolve().is_relative_to(base) or path.is_symlink():
            raise C0Error('unsafe_local_selection')
        if path.is_file(): candidates.add(path.relative_to(base).as_posix()); continue
        if not path.is_dir(): batch.partial('selected_path_missing'); continue
        for directory, dirs, files in os.walk(path,followlinks=False):
            visited+=1
            if visited>10000:
                return batch.partial('local_inventory_limit')
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not Path(directory,d).is_symlink())
            for name in files:
                visited+=1
                if visited>10000: return batch.partial('local_inventory_limit')
                relative=Path(directory,name).relative_to(base).as_posix()
                if name.startswith('.') or name in PRIVATE: continue
                if config['include'] and not any(fnmatch.fnmatch(relative,pattern) for pattern in config['include']): continue
                candidates.add(relative)
    inventory=sorted(candidates)
    from .model import sha
    identity=sha(inventory)
    position=cursor.get('offset',0) if cursor and cursor.get('inventory_hash')==identity and not cursor.get('complete') else 0
    if type(position) is not int or not 0<=position<=len(inventory):raise C0Error('invalid_local_cursor')
    batch.cursor={'inventory_hash':identity,'offset':position,'complete':False}
    for index,relative in enumerate(inventory):
        if index<position:continue
        batch.cursor['offset']=index
        if Path(relative).name in PRIVATE or Path(relative).name.startswith('.'):
            batch.partial('private_file_excluded');continue
        if len(batch.items)>=config['max_items']: return batch.partial('source_item_limit')
        suffix=Path(relative).suffix.lower(); media={**TEXT,**BINARY}.get(suffix)
        if not media: batch.partial('unsupported_local_media'); continue
        try:
            body=safe_read(base,relative,config['max_bytes'])
            if media in TEXT.values(): body.decode('utf-8')
            if not body: raise C0Error('empty_source')
        except (OSError,UnicodeError,C0Error):
            batch.partial('local_file_unavailable'); continue
        batch.add(Item(config['id'],relative,relative,body,media,
            provenance={'relative_path':relative,'source_type':'local_file'}))
        batch.cursor['offset']=index+1
    batch.cursor['complete']=batch.status=='complete'
    if batch.errors and batch.errors!=['source_item_limit']:batch.cursor['offset']=0
    return batch


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.ignored=0;self.in_title=False
        self.title=[];self.body=[];self.canonical=''
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'): self.ignored+=1
        if tag=='title': self.in_title=True
        if tag in ('p','div','section','article','h1','h2','h3','li','br'): self.body.append('\n')
        if tag=='link' and 'canonical' in attrs.get('rel','').lower().split(): self.canonical=attrs.get('href','')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'): self.ignored=max(0,self.ignored-1)
        if tag=='title': self.in_title=False
        if tag in ('p','div','section','article','li'): self.body.append('\n')
    def handle_data(self,value):
        if not self.ignored:
            if self.in_title: self.title.append(value)
            else: self.body.append(value)


def web_item(config, fetcher, url, *, external_id=None, published='', updated='', provenance=None):
    raw, canonical, media=fetcher.get(url)
    title=canonical
    if media in ('text/html','application/xhtml+xml'):
        parser=Page();parser.feed(raw.decode('utf-8'));text='\n'.join(line.strip() for line in ''.join(parser.body).splitlines() if line.strip())
        title=''.join(parser.title).strip() or title
        if parser.canonical:
            declared=public_url(urljoin(canonical,parser.canonical))
            if urlsplit(declared).hostname==urlsplit(canonical).hostname: canonical=declared
        raw=((title+'\n\n' if title else '')+text).encode();media='text/plain'
    elif media in ('text/plain','text/markdown','application/json','application/xml','text/xml'):
        raw.decode('utf-8')
        if media not in ('text/plain','text/markdown'):media='text/plain'
    elif media not in BINARY.values():
        raise C0Error('unsupported_remote_media')
    if not raw.strip(): raise C0Error('empty_source')
    return Item(config['id'],external_id or url,title,raw,media,url,canonical,published,updated,
        provenance=provenance or {'source_type':'http'})


def http(config, *, fetcher, **_):
    return Batch([web_item(config,fetcher,config['url'],external_id='page')])


def xml(content):
    text=content.decode('utf-8')
    if len(content)>2*1024*1024 or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise C0Error('unsafe_or_oversized_xml')
    return ET.fromstring(text)


def tag(element): return element.tag.rsplit('}',1)[-1]
def child(element,name): return next((v for v in element if tag(v)==name),None)
def value(element,name):
    item=child(element,name);return ''.join(item.itertext()).strip() if item is not None else ''


def source_date(text):
    if not text: return ''
    try:
        from datetime import datetime
        parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
    except ValueError:
        try: parsed=parsedate_to_datetime(text)
        except (ValueError,TypeError): return ''
    return parsed.isoformat() if parsed.tzinfo is not None else ''


def rss_atom(config, *, fetcher, cursor=None, **_):
    raw,feed_url,_=fetcher.get(config['url']); tree=xml(raw);batch=Batch();seen=set()
    entries=[v for v in tree.iter() if tag(v) in ('item','entry')]
    identity=sha(raw)
    position=cursor.get('offset',0) if cursor and cursor.get('feed_hash')==identity and not cursor.get('complete') else 0
    if type(position) is not int or not 0<=position<=len(entries):raise C0Error('invalid_feed_cursor')
    batch.cursor={'feed_hash':identity,'offset':position,'complete':False}
    for index,entry in enumerate(entries):
        if index<position:continue
        batch.cursor['offset']=index
        if len(batch.items)>=config['max_items']: return batch.partial('source_item_limit')
        links=[node for node in entry if tag(node)=='link' and node.attrib.get('rel','alternate')=='alternate']
        link=links[0] if links else None
        href=(link.attrib.get('href') or ''.join(link.itertext()).strip()) if link is not None else ''
        external=value(entry,'guid') or value(entry,'id') or href
        if not external or external in seen: continue
        seen.add(external)
        try:
            if not href:
                content=value(entry,'content') or value(entry,'description') or value(entry,'summary')
                if not content:raise C0Error('feed_entry_has_no_original')
                original=ET.tostring(entry,encoding='utf-8')
                if len(original)>config['max_bytes']:raise C0Error('source_content_too_large')
                batch.add(Item(config['id'],external,value(entry,'title') or external,original,
                    original_url=feed_url,canonical_url=feed_url,published_at=source_date(value(entry,'published') or value(entry,'pubDate')),
                    updated_at=source_date(value(entry,'updated')),provenance={'source_type':'rss_atom_inline','feed_url':feed_url}))
                batch.cursor['offset']=index+1
                continue
            url=public_url(urljoin(feed_url,href))
            if config['include'] and not any(urlsplit(url).path.startswith(prefix) for prefix in config['include']):continue
            if urlsplit(url).hostname!=urlsplit(feed_url).hostname:
                raise C0Error('feed_cross_host_destination_requires_separate_connector')
            batch.add(web_item(config,fetcher,url,external_id=external,
                published=source_date(value(entry,'published') or value(entry,'pubDate')),
                updated=source_date(value(entry,'updated')),provenance={'source_type':'rss_atom','feed_url':feed_url}))
        except (C0Error,UnicodeError) as error:
            if isinstance(error,FetchError):batch.retry_after=error.retry_after
            return batch.partial('feed_item_unavailable')
        batch.cursor['offset']=index+1
    batch.cursor['complete']=batch.status=='complete'
    return batch


def sitemap(config, *, fetcher, cursor=None, **_):
    batch=Batch();pending=[(config['url'],0)];seen=set();pages={};host=urlsplit(config['url']).hostname
    while pending:
        url,depth=pending.pop(0)
        if url in seen:continue
        seen.add(url)
        if len(seen)>config['max_pages']:return batch.partial('sitemap_inventory_limit')
        raw,canonical,_=fetcher.get(url);tree=xml(raw)
        index=tag(tree)=='sitemapindex'
        for item in tree:
            location=value(item,'loc')
            if not location:continue
            location=public_url(urljoin(canonical,location))
            if urlsplit(location).hostname!=host:
                batch.partial('sitemap_cross_host_destination_denied');continue
            if index:
                if depth>=config['max_depth']:batch.partial('sitemap_depth_limit')
                else:pending.append((location,depth+1))
                if len(pending)>10000:return batch.partial('sitemap_inventory_limit')
                continue
            if config['include'] and not any(urlsplit(location).path.startswith(prefix) for prefix in config['include']):continue
            pages[location]=source_date(value(item,'lastmod'))
            if len(pages)>10000:return batch.partial('sitemap_inventory_limit')
    inventory=sorted(pages.items());identity=sha(inventory)
    offset=cursor.get('offset',0) if cursor and cursor.get('inventory_hash')==identity and not cursor.get('complete') else 0
    if type(offset) is not int or not 0<=offset<=len(inventory):raise C0Error('invalid_sitemap_cursor')
    batch.cursor={'inventory_hash':identity,'offset':offset,'complete':False}
    for number,(location,updated) in enumerate(inventory):
        if number<offset:continue
        batch.cursor['offset']=number
        if len(batch.items)>=config['max_items']:return batch.partial('source_item_limit')
        try:batch.add(web_item(config,fetcher,location,updated=updated))
        except (C0Error,UnicodeError) as error:
            if isinstance(error,FetchError):batch.retry_after=error.retry_after
            return batch.partial('sitemap_page_unavailable')
        batch.cursor['offset']=number+1
    batch.cursor['complete']=batch.status=='complete'
    return batch


def github(config, *, github, cursor=None, private_authorization_ref='', **_):
    batch=Batch(); repo=config['repository'];base='/repos/'+repo
    try:metadata,_=github.get(base)
    except GitHubError as error:
        if error.retry_at:
            from datetime import datetime,timezone
            batch.retry_after=datetime.fromtimestamp(error.retry_at,timezone.utc).isoformat()
        return batch.partial('github_repository_unavailable')
    if type(metadata) is not dict or type(metadata.get('id')) is not int or metadata['id']<=0:
        return batch.partial('github_repository_metadata_invalid')
    private=metadata.get('private') is True
    if private:
        if (not private_authorization_ref or getattr(github,'authorized_private_repository','')!=repo
                or metadata.get('full_name','').casefold()!=repo.casefold()):raise C0Error('explicit_private_repository_authorization_required')
    elif metadata.get('private') is not False:raise C0Error('public_github_repository_required')
    visibility={'repository':repo,'source_visibility':'private' if private else 'public'}
    if private:visibility['private_authorization_ref']=private_authorization_ref
    repository_id=str(metadata['id']);
    resumed=cursor if cursor and cursor.get('complete') is False else {}
    if resumed and resumed.get('repository_id')!=repository_id:raise C0Error('github_cursor_repository_mismatch')
    progress=dict(resumed.get('streams',{}));batch.cursor={'repository_id':repository_id,'streams':progress,'complete':False}
    include=config['include'] or ['readme','commits','releases','issues','pull_requests','comments']
    if 'comments' in include:include=[*include,'review_comments']
    try:
        for kind in include:
            if kind in progress and progress[kind] is None:continue
            if kind in ('readme','docs'):
                if kind=='readme': paths=[base+'/readme']
                else:
                    paths=[];pending=[('docs',0)];directories=0
                    while pending:
                        directory,depth=pending.pop(0);directories+=1
                        if directories>config['max_pages']:return batch.partial('github_document_inventory_limit')
                        listing,_=github.get(base+'/contents/'+directory)
                        if type(listing) is not list:raise C0Error('invalid_github_document_inventory')
                        for row in sorted(listing,key=lambda r:r.get('path','')):
                            path=row.get('path','')
                            if not path.startswith('docs/') or any(v in ('.','..') for v in Path(path).parts):raise C0Error('invalid_github_document_path')
                            if row.get('type')=='dir':
                                if depth>=config['max_depth']:batch.partial('github_document_depth_limit')
                                else:pending.append((path,depth+1))
                            elif row.get('type')=='file' and Path(path).suffix.lower() in TEXT:paths.append(base+'/contents/'+path)
                position=progress.get(kind) or {'index':0}
                index=position.get('index',0)
                if type(index) is not int or not 0<=index<=10000:raise C0Error('invalid_github_document_cursor')
                for number,path in enumerate(paths):
                    if number<index:continue
                    progress[kind]={'index':number}
                    if len(batch.items)>=config['max_items']:return batch.partial('source_item_limit')
                    document,_=github.get(path)
                    try:content=base64.b64decode(document['content'].replace('\n',''),validate=True);content.decode('utf-8')
                    except (ValueError,KeyError,UnicodeError):return batch.partial('github_document_unavailable')
                    if len(content)>config['max_bytes']:return batch.partial('source_content_too_large')
                    batch.add(Item(config['id'],repository_id+':document:'+document['path'],document['path'],content,
                        'text/markdown',document.get('html_url',''),document.get('html_url',''),
                        provenance={'source_type':'github_document','repository_id':repository_id,'blob_sha':document['sha'],**visibility}))
                    progress[kind]={'index':number+1}
                progress[kind]=None
                continue
            endpoint={'commits':'commits','releases':'releases','issues':'issues','pull_requests':'pulls','comments':'issues/comments','review_comments':'pulls/comments'}[kind]
            position=progress.get(kind) or {'url':base+'/'+endpoint+'?per_page=100','index':0}
            path=position['url'];start=position['index'];pages=0
            if type(start) is not int or not 0<=start<=100:raise C0Error('invalid_github_cursor')
            parsed=urlsplit(path)
            if parsed.netloc and parsed.netloc!='api.github.com':raise C0Error('invalid_github_cursor')
            if parsed.path!=base+'/'+endpoint:raise C0Error('invalid_github_cursor')
            while path:
                pages+=1
                if pages>config['max_pages']: batch.partial('github_pagination_incomplete');break
                progress[kind]={'url':path,'index':start}
                try:rows,following=github.get(path)
                except Exception as error:
                    if not isinstance(error,GitHubError):raise
                    if error.retry_at:
                        from datetime import datetime,timezone
                        batch.retry_after=datetime.fromtimestamp(error.retry_at,timezone.utc).isoformat()
                    return batch.partial('github_page_unavailable')
                if type(rows) is not list: raise C0Error('invalid_github_page')
                for index,row in enumerate(rows):
                    if index<start:continue
                    progress[kind]={'url':path,'index':index}
                    if kind=='issues' and 'pull_request' in row: continue
                    if len(batch.items)>=config['max_items']: return batch.partial('source_item_limit')
                    external=repository_id+':'+kind+':'+str(row.get('id') or row.get('sha'))
                    body=json.dumps(row,ensure_ascii=False,sort_keys=True,indent=2).encode()
                    if len(body)>config['max_bytes']: batch.partial('source_content_too_large');continue
                    published=row.get('published_at') or row.get('created_at') or row.get('commit',{}).get('author',{}).get('date','')
                    batch.add(Item(config['id'],external,str(row.get('title') or row.get('name') or row.get('sha') or external),body,
                        'text/plain',row.get('html_url',''),row.get('html_url',''),source_date(published),source_date(row.get('updated_at','')),
                        provenance={'source_type':'github_'+kind,'repository_id':repository_id,**visibility}))
                    progress[kind]={'url':path,'index':index+1}
                path=following;start=0
                progress[kind]={'url':path,'index':0} if path else None
            if path is None:progress[kind]=None
    except GitHubError as error:
        if error.retry_at:
            from datetime import datetime,timezone
            batch.retry_after=datetime.fromtimestamp(error.retry_at,timezone.utc).isoformat()
        return batch.partial('github_request_or_rate_limit')
    batch.cursor['complete']=batch.status=='complete'
    return batch


def c0_space(config, *, source_client, cursor=None, **_):
    if source_client.space_id!=config['source_space_id']:raise C0Error('source_space_binding_mismatch')
    batch=Batch();calls=0
    def call(name,**arguments):
        nonlocal calls
        if calls>=config['max_requests']:raise C0Error('source_request_budget_exhausted')
        calls+=1
        return source_client.call(name,**arguments)
    # Capture a feed boundary before the snapshot. Later changes remain uncovered
    # until a future verified snapshot; reads never advance a target cursor.
    phases=config['include'] or ['wiki','sources'];typed=any(value.startswith('objects:') for value in phases)
    progress=dict(cursor) if cursor and cursor.get('complete') is False else {'phase':phases[0],'offset':0,'after':(cursor or {}).get('after',0),'complete':False}
    if typed:progress.setdefault('object_after',(cursor or {}).get('object_after',0))
    if (set(progress)-{'phase','offset','after','boundary','complete','feed_incomplete','object_after','object_boundary','object_feed_incomplete'} or progress.get('phase') not in phases
            or type(progress.get('offset')) is not int or not 0<=progress['offset']<=10000
            or type(progress.get('after')) is not int or progress['after']<0
            or typed and (type(progress['object_after']) is not int or progress['object_after']<0)):raise C0Error('invalid_c0_source_cursor')
    batch.cursor=progress
    try:
        if any(value in ('wiki','sources') for value in phases) and 'boundary' not in progress:
            changes=call('knowledge_changes',after=progress['after'],limit=100)['changes']
            progress['boundary']=max([row['id'] for row in changes]+[progress['after']])
            progress['feed_incomplete']=len(changes)==100
        if typed and 'object_boundary' not in progress:
            changes=call('objects_changes',after=progress['object_after'],limit=100)['events']
            progress['object_boundary']=max([row['id'] for row in changes]+[progress['object_after']])
            progress['object_feed_incomplete']=len(changes)==100
        for phase in phases[phases.index(progress['phase']):]:
            progress['phase']=phase
            spec=call('object_types_get',type_name=phase.split(':',1)[1]) if phase.startswith('objects:') else None
            if spec and spec['name']!=phase.split(':',1)[1]:raise C0Error('source_object_type_mismatch')
            while True:
                offset=progress['offset'];size=min(100,config['max_items'])
                response=(call('objects_list',type_name=spec['name'],limit=size,offset=offset)['objects'] if spec else
                    call('wiki_pages_list' if phase=='wiki' else 'sources_list',limit=size,offset=offset)['pages' if phase=='wiki' else 'sources'])
                for page in response:
                    if len(batch.items)>=config['max_items']:return batch.partial('source_item_limit')
                    if spec:
                        saved=call('objects_get',object_id=page['id'])
                        if saved['type_name']!=spec['name']:raise C0Error('source_object_type_mismatch')
                        content=json.dumps({'object':saved,'type':spec},sort_keys=True,ensure_ascii=False,indent=2).encode()
                        if len(content)>config['max_bytes']:return batch.partial('source_content_too_large')
                        batch.add(Item(config['id'],'object:'+saved['id'],spec['label']+' · '+saved['id'],content,
                            provenance={'source_type':'c0_typed_object','space_id':source_client.space_id,
                                'object_id':saved['id'],'type_name':spec['name'],'schema_hash':sha(spec['schema']),
                                'revision':saved['revision'],'c0_created_at':saved['created_at'],'c0_updated_at':saved['updated_at']}))
                    elif phase=='wiki':
                        saved=call('wiki_pages_get',page_id=page['id'],revision=page['revision'])['content']
                        batch.add(Item(config['id'],'wiki:'+page['id'],saved['title'],saved['body'].encode(),'text/markdown',
                            provenance={'source_type':'c0_space','space_id':source_client.space_id,'page_id':page['id'],
                                'revision':saved['number'],'content_hash':saved['content_hash']}))
                    elif not page['deleted']:
                        versions=call('source_versions_list',source_id=page['id'],limit=1,offset=0)['versions']
                        if versions:
                            version=versions[0]
                            if version['state']!='ready':return batch.partial('source_extraction_not_ready')
                            saved=call('documents_get',version_id=version['id'])
                            batch.add(Item(config['id'],'source:'+page['id'],page['title'],saved['body'].encode(),
                                provenance={'source_type':'c0_space','space_id':source_client.space_id,'source_id':page['id'],
                                    'version_id':version['id'],'source_hash':version['content_hash'],'document_id':saved['id']}))
                    progress['offset']+=1
                if len(response)<size:break
            progress['offset']=0
        progress.update(complete=batch.status=='complete',after=progress.get('boundary',progress['after']))
        progress.pop('boundary',None)
        if typed:progress['object_after']=progress.pop('object_boundary',progress['object_after'])
        incomplete=progress.pop('feed_incomplete',False)|progress.pop('object_feed_incomplete',False)
        if incomplete:
            batch.partial('source_change_feed_incomplete');progress.update(complete=False,phase=phases[0],offset=0)
    except C0Error:return batch.partial('source_read_or_authority_failed')
    return batch


def wikiplant_export(config, *, root, **kwargs):
    base=Path(config['root']);base=(root/base if not base.is_absolute() else base)
    identity=safe_read(base,'INSTANCE.json',65536)
    try:
        instance=json.loads(identity); legacy=str(instance.get('instance_id') or instance.get('id') or '')
        if not legacy: raise ValueError()
    except (ValueError,TypeError): raise C0Error('invalid_wikiplant_export_identity') from None
    selected={**config,'paths':config.get('paths') or ['data'],'include':config['include'] or ['*']}
    batch=local_files(selected,root=root)
    batch.items=[Item(item.connector_id,legacy+':'+item.external_id,item.title,item.content,item.media_type,
        provenance={**item.provenance,'source_type':'wikiplant_export','legacy_instance_id':legacy,'legacy_path':item.external_id}) for item in batch.items]
    return batch


ADAPTERS={'local_files':local_files,'http':http,'rss_atom':rss_atom,'sitemap':sitemap,
    'github':github,'c0_space':c0_space,'wikiplant_export':wikiplant_export}


def collect(config, *, root, fetcher=None, **kwargs):
    if config['adapter']=='website':
        from .website import website
        return website(config,root=Path(root),fetcher=fetcher,**kwargs)
    try:
        return ADAPTERS[config['adapter']](config,root=Path(root),fetcher=fetcher or Fetcher(config),**kwargs)
    except FetchError as error:
        return Batch(cursor=kwargs.get('cursor') or {},status='partial',errors=[str(error)],retry_after=error.retry_after)
    except BatchLimit as error:
        return error.batch
    except (OSError,ValueError,UnicodeError,ET.ParseError):
        raise C0Error('source_collection_failed') from None
