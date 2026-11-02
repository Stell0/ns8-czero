# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable real C0 sources and paired identity-preserving database snapshots."""
from contextlib import asynccontextmanager,AsyncExitStack
import json
import time
import re
import secrets
from uuid import UUID
from joserfc.jwk import RSAKey
from c0_ingest.state import atomic
import httpx2
from joserfc import jwt
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from evaluation.fixture import ORIGIN
from pathlib import Path

from sqlalchemy import create_engine,text
from czero_core.worker import Worker
from evaluation.fixture import Fixture, disposable_database, database_parameters
from .protocol import body_hash, digest, validate_corpus
from .job import read_corpus


class RetrievalFixture(Fixture):
    def refresh_native(self):
        for name,key in self.keys.items():
            self.native[name]=jwt.encode({'alg':'RS256','kid':'evaluation'},
                {'iss':self.identity['issuer'],'aud':'czero900','ldap_uuid':str(key),'sub':str(key),
                 'preferred_username':name,'iat':int(time.time())-1,'exp':int(time.time())+300,'typ':'Bearer'},self.signer)
        self.http.headers['Authorization']='Bearer '+self.native['owner']

    async def request(self,*args,**kwargs):
        self.refresh_native()
        return await super().request(*args,**kwargs)

    @asynccontextmanager
    async def mcp(self,case):
        self.refresh_native();pair=self.token(case)
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=self.app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+pair.access_token}) as http:
            async with Client(streamable_http_client(ORIGIN+'/mcp',http_client=http)) as client:
                yield client

    async def seed_sources(self,sources, *, max_sources=1000, max_source_bytes=134217728):
        validate_sources(sources,max_sources,max_source_bytes)
        self.max_sources=max_sources;self.max_source_bytes=max_source_bytes
        self.ground['Operations']=await self.request('POST','/api/v1/spaces',{'name':'Retrieval laboratory','idempotency_key':'lab'})
        self.space=self.ground['Operations']['id']
        # Create the Reader through normal verified native access, then grant only
        # this protected space. The evaluated OAuth grant has c0:read alone.
        import httpx
        from evaluation.fixture import ORIGIN
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url=ORIGIN,
                headers={'Authorization':'Bearer '+self.native['reader']}) as client:
            await client.get('/api/v1/me')
        accounts=(await self.request('GET','/api/v1/access/accounts'))['accounts']
        self.reader_id=next(a['id'] for a in accounts if a['username']=='reader')
        await self.request('PUT','/api/v1/access/accounts/'+self.reader_id,{'role':'reader'})
        await self.request('PUT','/api/v1/spaces/'+self.space+'/grants/'+self.reader_id,
                           {'role':'reader','expected_revision':0,'idempotency_key':'lab-reader'})
        if any(source.get('parts') for source in sources):
            from c0_projects.model import source_config,now
            definition=source_config({'id':'evaluation','adapter':'local_files','root':'inputs'})
            await self.request('POST','/api/v1/project/initialize',{'manifest':{'project_id':self.space,'space_id':self.space,
                'name':'Retrieval laboratory','purpose':'Selected evidence comparison','scope':'Disposable fixture only',
                'connector_ids':['evaluation']},'authorization_ref':'evaluation fixture','idempotency_key':'project'},self.space)
            await self.request('PUT','/api/v1/project/connectors',{'definition':definition,
                'authorization_ref':'evaluation fixture','expected_revision':0,'idempotency_key':'connector'},self.space)
        for source in sources:
            key=source.get('key',source.get('id'))
            metadata={'canonical_url':source['url'],'provenance':{'product':source['product'],
                'product_version':source['version'],'language':source['language']}}
            parts=source.get('parts') or [None]
            receipts=[]
            for number,part in enumerate(parts,1):
                body=(source['body'].encode()[part['start_byte']:part['end_byte']].decode() if part else source['body'])
                external=digest([key,number])
                part_metadata=metadata if part is None else {**metadata,'connector_id':'evaluation',
                    'external_id':external,'parent_external_id':key}
                if len(body.encode())<=131072:
                    version=await self.request('POST','/api/v1/sources/ingest-text',{'title':source['title'],
                        'body':body,'metadata':part_metadata,'idempotency_key':external},self.space)
                else:
                    self.refresh_native()
                    response=await self.http.post('/api/v1/sources/upload',params={'space_id':self.space},
                        data={'title':source['title'],'media_type':'text/plain','retain_original':'false',
                              'metadata':json.dumps(part_metadata)},files={'file':('original.txt',body.encode(),'text/plain')})
                    response.raise_for_status();version=response.json()
                Worker(self.db,self.app.state.jobs.registry).tick()
                if part is not None:
                    data={'connector_id':'evaluation','definition_hash':digest(definition),'external_id':external,
                        'parent_external_id':key,'parent_content_hash':body_hash(source['body']),
                        'part_number':number,'start_byte':part['start_byte'],'end_byte':part['end_byte'],
                        'last_attempt_at':now(),'last_success_at':'','last_content_hash':body_hash(body),
                        'source_id':version['source_id'],'version_id':version['id'],'extraction_status':'ready',
                        'sync_status':'verified','last_error':'','retry_after':'','remote_cursor':'',
                        'provenance':{'original_url':source['url'],'canonical_url':source['url'],
                            'retrieved_at':now(),'published_at':'','updated_at':'','details':'{}'}}
                    receipt=await self.request('PUT','/api/v1/project/source-status',{'data':data,
                        'expected_revision':0,'idempotency_key':'receipt-'+external},self.space)
                    receipts.append(receipt['id'])
            if source.get('parts'):
                await self.request('PUT','/api/v1/project/source-snapshot',{'connector_id':'evaluation',
                    'external_id':key,'content_hash':body_hash(source['body']),'part_receipt_ids':receipts,
                    'expected_revision':0,'idempotency_key':'snapshot-'+key},self.space)
        self.before=self.snapshot()

    async def corpus(self):
        async def call(name, **arguments):
            routes={
                'source_documents_list':('/api/v1/source-documents',()),
                'source_documents_get':('/api/v1/source-documents/{logical_document_id}',('logical_document_id',)),
                'documents_get':('/api/v1/source-versions/{version_id}/document',('version_id',)),
                'document_chunks_list':('/api/v1/documents/{document_id}/chunks',('document_id',)),
                'citations_get':('/api/v1/chunks/{chunk_id}/citation',('chunk_id',))}
            path,fields=routes[name];path=path.format(**arguments)
            self.refresh_native()
            response=await self.http.get(path,params={'space_id':self.space,
                **{k:v for k,v in arguments.items() if k not in fields}})
            response.raise_for_status();return response.json()
        return await read_corpus(call,max_sources=self.max_sources,max_source_bytes=self.max_source_bytes)

    async def api_call(self,name,args):
        definition=self.app.state.operations.definition(name)
        if not definition:raise RuntimeError('operation_unavailable')
        # Use the existing authenticated MCP/SDK operation path for all writes.
        async with self.mcp('cited-research') as client:
            from c0_ingest.client import C0
            result=await client.call_tool(name,args)
            raw=result.model_dump(mode='json',by_alias=True,exclude_none=True)
        return C0.decode(name,raw)


def validate_sources(sources,max_sources,max_source_bytes):
    if not isinstance(sources,list) or not 1<=len(sources)<=max_sources:raise ValueError('source_selection_budget')
    if any(not isinstance(s.get('body'),str) or not s['body'] for s in sources):raise ValueError('source_body_budget')
    if sum(len(s['body'].encode()) for s in sources)>max_source_bytes:raise ValueError('source_total_bytes_budget')
    keys=[s.get('key',s.get('id')) for s in sources]
    if any(not isinstance(k,str) or not k for k in keys) or len(set(keys))!=len(keys):raise ValueError('source_identity')
    for source in sources:
        body=source['body'].encode();offset=0
        parts=source.get('parts') or [{'start_byte':0,'end_byte':len(body)}]
        if len(parts)>100:raise ValueError('source_part_count_budget')
        for part in parts:
            if part['start_byte']!=offset or not offset<part['end_byte']<=len(body):raise ValueError('source_part_layout')
            segment=body[offset:part['end_byte']].decode()
            if len(segment.encode())>2097152 or len(segment)>1000000:raise ValueError('source_part_body_budget')
            offset=part['end_byte']
        if offset!=len(body):raise ValueError('source_part_layout')


def owned_binding(admin_url,binding):
    """Verify retained DB ownership before reconnecting or cleanup."""
    admin=create_engine(admin_url)
    try:
        with admin.connect() as c:
            for url in (binding['a_url'],binding['b_url']):
                parsed=database_parameters(url);expected=database_parameters(admin_url)
                if parsed.set(database=expected.database)!=expected or not re.fullmatch(r'czero_eval_[0-9a-f]{32}',parsed.database):
                    raise ValueError('retained_database_target_changed')
                comment=c.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=:name"),{'name':parsed.database}).scalar_one()
                if comment!='c0-agentic:'+binding['nonce']:raise ValueError('retained_database_ownership_unproven')
    finally:admin.dispose()


@asynccontextmanager
async def paired_fixture(admin_url,directory,sources,*,checkpoint=None,max_sources=1000,max_source_bytes=134217728):
    """Clone only invocation-owned DBs; optional private checkpoint retains them."""
    validate_sources(sources,max_sources,max_source_bytes)
    directory=Path(directory);checkpoint=Path(checkpoint) if checkpoint else None
    saved=json.loads(checkpoint.read_text()) if checkpoint and checkpoint.exists() else None
    a=b=None
    async with AsyncExitStack() as databases:
        if saved:
            owned_binding(admin_url,saved)
            identity={'issuer':saved['issuer'],'signer':RSAKey.import_key(saved['signer']),
                      'keys':{k:UUID(v) for k,v in saved['keys'].items()}}
            a_url,b_url=saved['a_url'],saved['b_url']
            a=RetrievalFixture(a_url,directory/'raw',identity=identity)
            a.space=saved['space'];a.reader_id=saved['reader_id'];a.max_sources=max_sources;a.max_source_bytes=max_source_bytes
        else:
            a_url=await databases.enter_async_context(disposable_database(admin_url,retain=bool(checkpoint)))
            b_url=await databases.enter_async_context(disposable_database(admin_url,retain=bool(checkpoint)))
            a=RetrievalFixture(a_url,directory/'raw')
            await a.seed_sources(sources,max_sources=max_sources,max_source_bytes=max_source_bytes)
            a.db.engine.dispose()
            original=database_parameters(a_url).database;clone=database_parameters(b_url).database
            admin=create_engine(admin_url)
            try:
                with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
                    c.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()'),{'name':original})
                    c.exec_driver_sql('DROP DATABASE '+clone)
                    c.exec_driver_sql('CREATE DATABASE '+clone+' TEMPLATE '+original)
                    if checkpoint:
                        nonce=secrets.token_hex(24)
                        for name in (original,clone):c.exec_driver_sql("COMMENT ON DATABASE "+name+" IS 'c0-agentic:"+nonce+"'")
            finally:admin.dispose()
            if checkpoint:
                saved={'a_url':a_url,'b_url':b_url,'nonce':nonce,'issuer':a.identity['issuer'],
                    'signer':a.signer.as_dict(private=True),'keys':{k:str(v) for k,v in a.keys.items()},
                    'space':a.space,'reader_id':a.reader_id}
                atomic(checkpoint,saved)
        try:
            b=RetrievalFixture(b_url,directory/'enriched',identity=a.identity)
            b.space=a.space;b.reader_id=a.reader_id;b.max_sources=max_sources;b.max_source_bytes=max_source_bytes
            a_corpus=await a.corpus();b_corpus=await b.corpus()
            if a_corpus!=b_corpus:raise RuntimeError('paired_snapshot_mismatch')
            import shutil
            if a.app.state.sources.originals.root.exists():
                shutil.copytree(a.app.state.sources.originals.root,b.app.state.sources.originals.root,dirs_exist_ok=True)
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(a.app.state.mcp_app.router.lifespan_context(a.app.state.mcp_app))
                await stack.enter_async_context(b.app.state.mcp_app.router.lifespan_context(b.app.state.mcp_app))
                yield a,b,a_corpus
        finally:
            if b:await b.close()
            if a:await a.close()


def cleanup_pair(admin_url,checkpoint):
    binding=json.loads(Path(checkpoint).read_text());owned_binding(admin_url,binding)
    admin=create_engine(admin_url)
    try:
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            for url in (binding['a_url'],binding['b_url']):
                c.exec_driver_sql('DROP DATABASE '+database_parameters(url).database+' WITH (FORCE)')
    finally:admin.dispose()
    Path(checkpoint).unlink()
