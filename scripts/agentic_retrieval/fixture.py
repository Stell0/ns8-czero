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

    async def seed_sources(self,sources):
        if not isinstance(sources,list) or not 1<=len(sources)<=100:raise ValueError('source_selection_budget')
        if any(not isinstance(s.get('body'),str) or not 1<=len(s['body'].encode())<=131072 for s in sources):raise ValueError('source_body_budget')
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
        for source in sources:
            version=await self.request('POST','/api/v1/sources/ingest-text',{'title':source['title'],
                'body':source['body'],'metadata':{'canonical_url':source['url'],
                    'provenance':{'product':source['product'],'product_version':source['version'],'language':source['language']}},
                'idempotency_key':source['key']},self.space)
            Worker(self.db,self.app.state.jobs.registry).tick()
        self.before=self.snapshot()

    async def corpus(self):
        docs=(await self.request('GET','/api/v1/source-documents',space=self.space))['documents']
        corpus=[]
        for entry in docs:
            doc=await self.request('GET','/api/v1/source-documents/'+entry['id'],space=self.space)
            if doc['state']!='ready' or doc['multipart']:raise RuntimeError('pilot_requires_ready_single_parts')
            version=doc['revision_id']
            physical=await self.request('GET','/api/v1/source-versions/'+version+'/document',space=self.space)
            chunks=(await self.request('GET','/api/v1/documents/'+physical['id']+'/chunks',space=self.space))['chunks']
            citations=[await self.request('GET','/api/v1/chunks/'+c['id']+'/citation',space=self.space) for c in chunks]
            meta=doc['metadata'];p=meta.get('provenance',{})
            corpus.append({'id':doc['id'],'url':meta['canonical_url'],'generation':version,
                'content_hash':body_hash(doc['body']),'body':doc['body'],'title':doc.get('title',''),
                'product':p.get('product',''),'version':p.get('product_version',''),'language':p.get('language',''),
                'chunks':citations})
        corpus.sort(key=lambda d:d['id']);validate_corpus(corpus);return corpus

    async def api_call(self,name,args):
        definition=self.app.state.operations.definition(name)
        if not definition:raise RuntimeError('operation_unavailable')
        # Use the existing authenticated MCP/SDK operation path for all writes.
        async with self.mcp('cited-research') as client:
            from c0_ingest.client import C0
            result=await client.call_tool(name,args)
            raw=result.model_dump(mode='json',by_alias=True,exclude_none=True)
        return C0.decode(name,raw)


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
async def paired_fixture(admin_url,directory,sources,*,checkpoint=None):
    """Clone only invocation-owned DBs; optional private checkpoint retains them."""
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
            a.space=saved['space'];a.reader_id=saved['reader_id']
        else:
            a_url=await databases.enter_async_context(disposable_database(admin_url,retain=bool(checkpoint)))
            b_url=await databases.enter_async_context(disposable_database(admin_url,retain=bool(checkpoint)))
            a=RetrievalFixture(a_url,directory/'raw')
            await a.seed_sources(sources)
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
            b.space=a.space;b.reader_id=a.reader_id
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
