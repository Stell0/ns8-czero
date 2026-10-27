# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, read-only project interchange catalog; never export authority/secrets."""
import base64,json
from uuid import UUID
from sqlalchemy import text
from .receipts import snapshot

# Explicit columns exclude authentication, storage paths, search vectors and jobs.
CATALOG={
    'sources':('c0_sources','id,ingest_key,title,metadata,revision,deleted,created_at,updated_at',('id',)),
    'source_versions':('c0_source_versions','id,source_id,number,filename,media_type,content_hash,size_bytes,state,error_code,retain_original,original_present,generation,job_id,created_at',('id',)),
    'documents':('c0_documents','id,version_id,text_hash,locations,created_at,length(body) AS body_chars',('id',)),
    'chunks':('c0_chunks','id,document_id,ordinal,start_offset,end_offset,body,content_hash,locations',('id',)),
    'wiki_pages':('c0_wiki_pages','id,slug,title,revision,deleted,created_at,updated_at',('id',)),
    'wiki_revisions':('c0_wiki_revisions','id,page_id,number,title,content_hash,metadata,actor_id,created_at,length(body) AS body_chars',('id',)),
    'wiki_chunks':('c0_wiki_chunks','id,revision_id,ordinal,start_offset,end_offset,body,content_hash',('id',)),
    'entities':('c0_entities','id,kind,label,metadata,revision,deleted,created_at,updated_at',('id',)),
    'aliases':('c0_entity_aliases','normalized,entity_id,label,created_at',('normalized',)),
    'entity_links':('c0_entity_links','id,entity_id,target_kind,target_id,label_snapshot,object_id,page_id,source_id,document_id,chunk_id,actor_id,created_at',('id',)),
    'relations':('c0_relations','id,source_id,target_id,kind,metadata,revision,deleted,actor_id,created_at',('id',)),
    'claims':('c0_claims','id,entity_id,page_id,predicate,value,metadata,revision,deleted,actor_id,valid_from,valid_to,created_at',('id',)),
    'evidence_links':('c0_evidence_links','claim_id,chunk_id,created_at',('claim_id','chunk_id')),
    'annotation_targets':('c0_annotation_targets','id,kind,target_id,content_revision,resource_id,content_hash,created_by,created_at,source_version_id,wiki_revision_id,entity_id,object_id,claim_id',('id',)),
    'annotations':('c0_annotations','id,anchor_id,namespace,revision,created_at',('id',)),
    'annotation_revisions':('c0_annotation_revisions','id,annotation_id,number,value,actor_id,created_at',('id',)),
    'objects':('c0_objects','id,type_name,data,tags,revision,created_at,updated_at',('id',)),
    'object_relations':('c0_object_relations','id,source_id,target_id,kind,created_at',('id',)),
    'object_types':('c0_object_types','name,label,schema,unique_fields,created_at',('name',)),
    'knowledge_events':('c0_knowledge_events','id,kind,resource_id,operation,revision,actor_id,created_at,feed_cursor',('id',)),
    'object_events':('c0_object_events','id,object_id,type_name,revision,operation,actor_id,created_at,feed_cursor',('id',)),
}
KINDS=tuple(CATALOG)+('document_text','wiki_text','catalog')
LIMITATIONS=[
    'Two-read change detection is not a database transaction snapshot.',
    'Original binary bytes require the existing authorized original-file API or native backup; this contract exports metadata and extracted text.',
    'Generic object/claim events retain revision metadata, not unavailable historical payloads; explicit project histories and immutable Wiki/source versions are retained.',
    'Permissions, OAuth credentials, sessions, jobs, embeddings and server storage paths are excluded.',
]


def encode_cursor(space,kind,values):
    return base64.urlsafe_b64encode(json.dumps([str(space),kind,values],ensure_ascii=False,separators=(',',':')).encode()).decode().rstrip('=')


def decode_cursor(value,space,kind,keys):
    if type(value) is not str or len(value)>2048:raise ValueError('invalid_export_cursor')
    if not value:return None
    try:
        payload=json.loads(base64.b64decode(value+'='*((-len(value))%4),altchars=b'-_',validate=True))
        if type(payload) is not list or len(payload)!=3 or payload[:2]!=[str(space),kind]:raise ValueError()
        values=payload[2]
        if type(values) is not list or len(values)!=len(keys):raise ValueError()
        for key,item in zip(keys,values):
            if key in ('normalized','name'):
                if type(item) is not str or not 1<=len(item)<=512:raise ValueError()
            elif kind in ('knowledge_events','object_events'):
                if type(item) is not int or item<0:raise ValueError()
            elif type(item) is not str or str(UUID(item))!=item:raise ValueError()
        return values
    except (ValueError,TypeError,RecursionError):raise ValueError('invalid_export_cursor') from None


class ProjectExports:
    def export_page(self,actor,kind,*,after='',limit=50,resource_id=''):
        if kind not in KINDS or type(limit) is not int or not 1<=limit<=100:raise ValueError('invalid_export_selection')
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor);self._manifest(connection)
            params={'space':self._space_id,'limit':limit+1};rows=[];following=''
            if kind=='catalog':
                if after or resource_id:raise ValueError('invalid_export_catalog_selection')
                for name,(_,_,keys) in CATALOG.items():
                    body={'documents':('document_text','text_hash'),'wiki_revisions':('wiki_text','content_hash')}.get(name,('',''))
                    rows.append({'kind':name,'key_fields':list(keys),'text_kind':body[0],'hash_field':body[1]})
            elif kind in ('document_text','wiki_text'):
                try:
                    if type(resource_id) is not str:raise ValueError()
                    UUID(resource_id)
                    if type(after) is not str or not after.isascii() or (after and not after.isdecimal()) or len(after)>8:raise ValueError()
                    start=int(after or '0')
                except (ValueError,TypeError):raise ValueError('invalid_export_text_selection') from None
                table='c0_documents' if kind=='document_text' else 'c0_wiki_revisions'
                part=connection.execute(text('SELECT id,length(body) AS total_chars,substring(body FROM :start FOR 32768) AS body FROM '+table+
                    ' WHERE space_id=:space AND id=CAST(:id AS uuid)'),{**params,'id':resource_id,'start':start+1}).mappings().one_or_none()
                if part is None or start>part['total_chars']:raise ValueError('export_text_not_found')
                end=start+len(part['body']);rows=[{'id':str(part['id']),'start_char':start,'end_char':end,'total_chars':part['total_chars'],'body':part['body']}]
                following=str(end) if end<part['total_chars'] else ''
            else:
                if resource_id:raise ValueError('unexpected_export_resource')
                table,columns,keys=CATALOG[kind];values=decode_cursor(after,self._space_id,kind,keys)
                where='space_id=:space'
                if kind=='object_types':where='EXISTS(SELECT 1 FROM c0_objects o WHERE o.space_id=:space AND o.type_name=c0_object_types.name)'
                if values:
                    casts=[]
                    for number,(key,value) in enumerate(zip(keys,values)):
                        params['key'+str(number)]=value
                        casts.append(':key'+str(number) if key in ('name','normalized') or kind in ('knowledge_events','object_events') else 'CAST(:key'+str(number)+' AS uuid)')
                    where+=' AND ('+','.join(keys)+')>('+','.join(casts)+')'
                fetched=connection.execute(text('SELECT '+columns+' FROM '+table+' WHERE '+where+' ORDER BY '+','.join(keys)+' LIMIT :limit'),params).mappings()
                size=0;more=False
                for row in fetched:
                    item=snapshot(dict(row));amount=len(json.dumps(item,ensure_ascii=False,separators=(',',':')).encode())
                    if amount>262144:raise ValueError('export_row_too_large')
                    if len(rows)>=limit or size+amount>262144:more=True;break
                    rows.append(item);size+=amount
                if more:following=encode_cursor(self._space_id,kind,[rows[-1][key] for key in keys])
            cursors=dict(connection.execute(text('SELECT kind,value FROM c0_space_cursors WHERE space_id=:space'),params).all())
            return snapshot({'schema_version':1,'project_id':str(self._space_id),'kind':kind,'rows':rows,
                'next_cursor':following,'watermarks':cursors,'limitations':LIMITATIONS})
