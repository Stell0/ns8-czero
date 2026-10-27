# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private, deterministic interchange artifacts; no C0 mutation or publication."""
import json,os,re
from pathlib import Path,PurePosixPath
from uuid import UUID
from c0_ingest.errors import C0Error
from .adapters import safe_read
from .formats import load_data
from .model import sha


def canonical(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def relative(value):
    if (type(value) is not str or len(value)>512 or '\\' in value or '\0' in value or value.startswith('/')
            or any(part in ('','.','..') for part in value.split('/'))):raise C0Error('unsafe_export_path')
    return PurePosixPath(value)


class Artifacts:
    def __init__(self,root,maximum):
        self.root=Path(root).absolute();self.maximum=maximum;self.size=0;self.files=[]
        if any(path.is_symlink() for path in (self.root,*self.root.parents)):raise C0Error('unsafe_export_destination')
        self.root=self.root.resolve()
        self.root.mkdir(mode=0o700,exist_ok=False)
    def add(self,path,body,**metadata):
        path=str(relative(path))
        if type(body) is not bytes or len(body)>16*1024*1024 or self.size+len(body)>self.maximum:raise C0Error('export_size_limit')
        target=self.root/path
        parent=self.root
        for part in relative(path).parts[:-1]:parent/=part;parent.mkdir(mode=0o700,exist_ok=True)
        with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as stream:
            stream.write(body);stream.flush();os.fsync(stream.fileno())
        entry={'path':path,'size':len(body),'sha256':sha(body),**metadata}
        self.files.append(entry);self.size+=len(body)
        return entry
    def readback(self):
        for entry in self.files:
            body=safe_read(self.root,entry['path'],4*1024*1024)
            if len(body)!=entry['size'] or sha(body)!=entry['sha256']:raise C0Error('export_readback_failed')


def validate_export_limits(max_records,max_bytes):
    if (type(max_records) is not int or not 1<=max_records<=100000 or type(max_bytes) is not int
            or not 1024<=max_bytes<=1024*1024*1024):raise C0Error('invalid_export_limits')


def export_project(client,output,*,max_records=10000,max_bytes=100*1024*1024):
    validate_export_limits(max_records,max_bytes)
    archive=Artifacts(output,max_bytes);baseline=None;count=0;observed={};counts={}
    try:
        stored=client.call('project_get');space=stored['data']['manifest']['space_id']
        if space!=client.space_id or stored['data']['manifest']['project_id']!=space:raise C0Error('export_project_binding_mismatch')
        archive.add('project.json',canonical(stored),kind='project',resource_id=space)
        def page(kind,**values):
            nonlocal baseline
            response=client.call('project_export_get',kind=kind,**values)
            if response['schema_version']!=1 or response['project_id']!=space or response['kind']!=kind:
                raise C0Error('export_response_binding_mismatch')
            if baseline is None:baseline=response['watermarks']
            if response['watermarks']!=baseline:raise C0Error('project_changed_during_export')
            return response
        catalog=page('catalog');definitions=catalog['rows']
        if (not 1<=len(definitions)<=64 or any(type(row.get('kind')) is not str
                or not re.fullmatch('[a-z_]{1,32}',row['kind']) or type(row.get('key_fields')) is not list
                or not 1<=len(row['key_fields'])<=2 or any(not re.fullmatch('[a-z_]{1,32}',key) for key in row['key_fields'])
                or row.get('text_kind') not in ('','document_text','wiki_text') for row in definitions)
                or len({row['kind'] for row in definitions})!=len(definitions)):raise C0Error('invalid_export_catalog')
        def rows(kind):
            cursor='';seen=set()
            while True:
                response=page(kind,after=cursor,limit=100)
                if type(response['rows']) is not list or len(response['rows'])>100:raise C0Error('invalid_export_page')
                yield from response['rows']
                cursor=response['next_cursor']
                if not cursor:break
                if cursor in seen or not response['rows']:raise C0Error('export_cursor_did_not_advance')
                seen.add(cursor)
                if len(seen)>max_records:raise C0Error('export_inventory_limit')
        for definition in definitions:
            kind=definition['kind'];counts[kind]=0
            for row in rows(kind):
                count+=1;counts[kind]+=1
                if count>max_records:raise C0Error('export_inventory_limit')
                identity=[row[key] for key in definition['key_fields']];key=sha(identity)
                path='records/'+kind+'/'+key+'.json';body=canonical(row)
                if path in observed:raise C0Error('duplicate_export_identity')
                observed[path]=sha(body)
                archive.add(path,body,kind=kind,resource_id=identity)
                if definition['text_kind']:
                    resource=str(UUID(row['id']));cursor='';content=''
                    while True:
                        fragment=page(definition['text_kind'],resource_id=resource,after=cursor)
                        part=fragment['rows'][0]
                        if (part['id']!=resource or part['start_char']!=len(content) or part['total_chars']!=row['body_chars']
                                or part['end_char']!=part['start_char']+len(part['body']) or len(part['body'])>32768):
                            raise C0Error('invalid_export_text_fragment')
                        content+=part['body']
                        if len(content.encode())>2*1024*1024:raise C0Error('export_text_limit')
                        cursor=fragment['next_cursor']
                        if not cursor:break
                        if cursor!=str(len(content)) or not part['body']:raise C0Error('export_text_cursor_did_not_advance')
                    body=content.encode()
                    if len(content)!=row['body_chars'] or sha(body)!=row[definition['hash_field']]:raise C0Error('export_text_hash_mismatch')
                    path=('documents/'+resource+'.txt' if kind=='documents' else 'wiki/'+str(UUID(row['page_id']))+'/revisions/'+str(row['number'])+'.md')
                    archive.add(path,body,kind=definition['text_kind'],resource_id=resource)
        verified=set()
        for definition in definitions:
            for row in rows(definition['kind']):
                path='records/'+definition['kind']+'/'+sha([row[key] for key in definition['key_fields']])+'.json'
                if path in verified or observed.get(path)!=sha(canonical(row)):raise C0Error('project_changed_during_export')
                verified.add(path)
                if len(verified)>max_records:raise C0Error('export_inventory_limit')
        if verified!=set(observed) or client.call('project_get')!=stored or page('catalog')!=catalog:
            raise C0Error('project_changed_during_export')
        archive.readback()
        manifest={'kind':'c0-project-export','schema_version':1,'status':'validated','instance_url':client.config['url'],
            'project_id':space,'manifest_version':stored['data']['version'],'watermarks':baseline,'record_counts':counts,
            'files':sorted(archive.files,key=lambda item:item['path']),'limitations':catalog['limitations']}
        entry=archive.add('manifest.json',canonical(manifest),kind='manifest',resource_id=space)
        archive.add('manifest.sha256',(entry['sha256']+'\n').encode(),kind='checksum',resource_id=space)
        verified=verify_export(archive.root)
        return {'status':'VALIDATED','project_id':space,'directory':str(archive.root),'manifest_hash':entry['sha256'],
            'files':verified['files'],'records':count,'writes_c0':0,'publication_performed':False}
    except (C0Error,OSError,ValueError,KeyError,TypeError,IndexError):
        try:archive.add('partial.json',canonical({'status':'PARTIAL','error':'export_incomplete_reconcile_authority_limits_and_source_state',
            'files':sorted(archive.files,key=lambda item:item['path']),'writes_c0':0}),kind='partial',resource_id=client.space_id or '')
        except (C0Error,OSError):pass
        return {'status':'PARTIAL','directory':str(archive.root),'error':'export_incomplete_reconcile_authority_limits_and_source_state','writes_c0':0}


def verify_export(root):
    root=Path(root).absolute()
    if any(path.is_symlink() for path in (root,*root.parents)):raise C0Error('unsafe_export_root')
    raw=safe_read(root,'manifest.json',16*1024*1024)
    expected=safe_read(root,'manifest.sha256',65).decode().strip()
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(raw)!=expected:raise C0Error('export_manifest_hash_mismatch')
    manifest=load_data(raw.decode(),'json',maximum=16*1024*1024,max_nodes=2000000)
    if (type(manifest) is not dict or manifest.get('kind')!='c0-project-export' or type(manifest.get('schema_version')) is not int or manifest.get('schema_version')!=1
            or manifest.get('status')!='validated' or type(manifest.get('files')) is not list
            or not 1<=len(manifest['files'])<=300000):raise C0Error('invalid_export_manifest')
    UUID(manifest['project_id']);seen={'manifest.json','manifest.sha256'};total=0
    for entry in manifest['files']:
        path=str(relative(entry['path']))
        if path in seen or not re.fullmatch('[0-9a-f]{64}',entry['sha256']) or type(entry['size']) is not int or not 0<=entry['size']<=4*1024*1024:
            raise C0Error('invalid_export_file_entry')
        body=safe_read(root,path,4*1024*1024);total+=len(body)
        if total>1024*1024*1024 or len(body)!=entry['size'] or sha(body)!=entry['sha256']:raise C0Error('export_file_integrity_failed')
        seen.add(path)
    actual=set()
    for directory,folders,files in os.walk(root,followlinks=False):
        if any((Path(directory)/name).is_symlink() for name in folders+files):raise C0Error('unsafe_export_symlink')
        actual.update((Path(directory)/name).relative_to(root).as_posix() for name in files)
    if actual!=seen:raise C0Error('export_extra_or_missing_files')
    return {'status':'VALIDATED','project_id':manifest['project_id'],'files':len(manifest['files']),
        'manifest_hash':expected,'writes_c0':0,'publication_performed':False}
