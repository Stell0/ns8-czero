# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit, parse_qsl
from uuid import UUID

from c0_ingest.errors import C0Error

ADAPTERS = {'local_files', 'http', 'rss_atom', 'sitemap', 'github', 'c0_space', 'wikiplant_export'}
DEFAULTS = {'enabled': True, 'include': [], 'max_items': 100, 'max_requests': 40,
    'max_bytes': 8 * 1024 * 1024, 'max_pages': 5, 'max_depth': 2, 'timeout': 15}
FIELDS = set(DEFAULTS) | {'id','adapter','url','repository','root','paths','source_space_id','authorization_ref'}


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def public_url(value):
    if type(value) is not str or len(value)>4096 or any(ord(c)<=32 or ord(c)==127 for c in value):
        raise C0Error('invalid_public_url')
    try:
        parsed=urlsplit(value)
        if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or parsed.port not in (None,443 if parsed.scheme=='https' else 80)):
            raise ValueError()
        if any(re.sub('[^a-z0-9]','',key.lower()).endswith(('token','key','secret','password','signature','credential','assertion','sessionid'))
               or key.lower() in {'auth','authorization','code','jwt','session','sig'} for key,_ in parse_qsl(parsed.query)):
            raise ValueError()
    except ValueError:
        raise C0Error('invalid_public_url') from None
    return value


def source_config(value):
    if type(value) is not dict or set(value)-FIELDS:
        raise C0Error('invalid_source_configuration')
    result={**DEFAULTS,**value}
    if (type(result.get('id')) is not str or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',result['id'])
            or type(result.get('adapter')) is not str or result['adapter'] not in ADAPTERS or type(result['enabled']) is not bool):
        raise C0Error('invalid_source_configuration')
    for field, maximum in [('max_items',1000),('max_requests',500),('max_bytes',16*1024*1024),('max_pages',20),('max_depth',4),('timeout',30)]:
        if type(result[field]) is not int or not 1<=result[field]<=maximum:
            raise C0Error('invalid_source_limit')
    for field in ('include','paths'):
        values=result.get(field,[])
        if type(values) is not list or len(values)>100 or any(type(v) is not str or not v or len(v)>512 or '\0' in v for v in values):
            raise C0Error('invalid_source_selection')
    adapter=result['adapter']
    if adapter in ('http','rss_atom','sitemap'):
        public_url(result.get('url'))
    if adapter=='github':
        if type(result.get('repository')) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}',result['repository']):
            raise C0Error('invalid_github_repository')
        if set(result['include'])-{'readme','docs','commits','releases','issues','pull_requests','comments'}:
            raise C0Error('invalid_github_selection')
    if adapter in ('local_files','wikiplant_export'):
        if type(result.get('root')) is not str or not result['root'] or '\0' in result['root']:
            raise C0Error('explicit_local_root_required')
        for path in result.get('paths',[]):
            if Path(path).is_absolute() or any(part in ('.','..') for part in Path(path).parts) or '\\' in path:
                raise C0Error('unsafe_local_selection')
    if adapter=='c0_space':
        if set(result['include'])-{'wiki','sources'}:raise C0Error('invalid_c0_source_selection')
        if type(result.get('source_space_id')) is not str:raise C0Error('explicit_source_space_required')
        try: UUID(result['source_space_id'])
        except (ValueError,KeyError,TypeError): raise C0Error('explicit_source_space_required') from None
        if type(result.get('authorization_ref')) is not str or not result['authorization_ref'].strip() or len(result['authorization_ref'])>512:
            raise C0Error('source_space_authorization_required')
    if len(json.dumps(result).encode())>16384:
        raise C0Error('source_configuration_too_large')
    return result


def load_config(path):
    path=Path(path)
    if path.stat().st_size>65536:
        raise C0Error('source_configuration_too_large')
    try:
        data=json.loads(path.read_text()) if path.suffix=='.json' else tomllib.loads(path.read_text())
        if set(data)-{'schema_version','server_url','project_space_id','sources'} or type(data.get('schema_version')) is not int or data['schema_version']!=1:
            raise ValueError()
        if type(data.get('project_space_id')) is not str or type(data.get('server_url')) is not str or any(ord(c)<=32 for c in data['server_url']):raise ValueError()
        UUID(data['project_space_id'])
        parsed=urlsplit(data['server_url'])
        if parsed.port is not None and not 1<=parsed.port<=65535:raise ValueError()
        if parsed.scheme!='https' or parsed.path!='/mcp' or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        if not parsed.hostname or type(data.get('sources')) is not list or not 1<=len(data['sources'])<=100:
            raise ValueError()
        data['sources']=[source_config(v) for v in data['sources']]
        if len({v['id'] for v in data['sources']})!=len(data['sources']):
            raise ValueError()
        return data
    except (KeyError,ValueError,TypeError):
        raise C0Error('invalid_project_source_configuration') from None


@dataclass(frozen=True)
class Item:
    connector_id: str
    external_id: str
    title: str
    content: bytes
    media_type: str='text/plain'
    original_url: str=''
    canonical_url: str=''
    published_at: str=''
    updated_at: str=''
    retrieved_at: str=field(default_factory=now)
    provenance: dict=field(default_factory=dict)

    def __post_init__(self):
        if (type(self.connector_id) is not str or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',self.connector_id)
                or type(self.external_id) is not str or not 1<=len(self.external_id)<=4096
                or type(self.title) is not str or not 1<=len(self.title)<=4096
                or type(self.content) is not bytes or not 1<=len(self.content)<=16*1024*1024
                or self.media_type not in ('text/plain','text/markdown','application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')):
            raise C0Error('invalid_normalized_source_item')
        for url in (self.original_url,self.canonical_url):
            if url:public_url(url)
        try:
            for value in (self.retrieved_at,self.published_at,self.updated_at):
                if value and datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is None:raise ValueError()
            if not self.retrieved_at or type(self.provenance) is not dict or len(json.dumps(self.provenance,allow_nan=False).encode())>8192:raise ValueError()
        except (TypeError,ValueError,AttributeError):raise C0Error('invalid_normalized_source_provenance') from None

    @property
    def content_hash(self):
        return sha(self.content)

    @property
    def key(self):
        return sha([self.connector_id,self.external_id])

    def metadata(self):
        return {'connector_id':self.connector_id,'external_id':self.external_id,
            'title':self.title,'media_type':self.media_type,'content_hash':self.content_hash,
            'original_url':self.original_url,'canonical_url':self.canonical_url,
            'published_at':self.published_at,'updated_at':self.updated_at,'retrieved_at':self.retrieved_at,
            'provenance':self.provenance}


class BatchLimit(C0Error):
    def __init__(self,batch):
        super().__init__('source_batch_limit')
        self.batch=batch


@dataclass
class Batch:
    items: list[Item]=field(default_factory=list)
    cursor: dict=field(default_factory=dict)
    status: str='complete'
    errors: list[str]=field(default_factory=list)
    retry_after: str=''
    attempted: bool=True

    def __post_init__(self):
        if len(self.items)>1000 or sum(len(item.content) for item in self.items)>32*1024*1024:
            raise C0Error('source_batch_limit')

    def add(self, item):
        if len(self.items)>=1000 or sum(len(value.content) for value in self.items)+len(item.content)>32*1024*1024:
            self.partial('source_batch_limit')
            raise BatchLimit(self)
        self.items.append(item)
        return True

    def partial(self, code):
        self.status='partial'
        if code not in self.errors: self.errors.append(code)
        return self
