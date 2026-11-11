# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable, provider-free SQL/latency/allocation evidence; no live instance.

PYTHONPATH=tests python -m benchmarks.cross_space_references --output evidence.json
The default matrix is deliberately substantial. Explicit selectors can reproduce
one case; reduced sample counts are diagnostics, never full benchmark acceptance.
Use --baseline against original source with this same driver for matched controls.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import resource
import random
import secrets
import statistics
import subprocess
import threading
import time
import tracemalloc
from uuid import UUID, uuid4

from sqlalchemy import event, text

from czero_core.api_keys import ApiKeyService
from czero_core.identity import PermissionDenied, Role
from czero_core.knowledge import KnowledgeService
from czero_core.oauth_grants import pkce_challenge
from czero_core.objects import ObjectService
from czero_core.spaces import SpaceService
from czero_core.wiki import WikiService
from evaluation.fixture import Fixture, disposable_database, ORIGIN, CALLBACK

KINDS = ('object','page','source','entity','claim')
TABLES = dict(zip(KINDS, ('c0_objects','c0_wiki_pages','c0_sources','c0_entities','c0_claims')))


def percentile(values, p):
    return sorted(values)[min(len(values)-1, int((len(values)-1)*p))]


def rss():
    return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')


def measure(db, call, args, concurrency):
    local = threading.local()
    def track(*_):
        if hasattr(local, 'count'): local.count += 1
    def invoke(_):
        local.count = 0
        start = time.perf_counter()
        value = call()
        return ((time.perf_counter()-start)*1000, local.count, len(json.dumps(value,default=str).encode()),
                len(value['references']) if isinstance(value,dict) and 'references' in value else len(value))
    event.listen(db.engine, 'before_cursor_execute', track)
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            list(pool.map(invoke, range(args.warmups)))
            samples = list(pool.map(invoke, range(args.samples)))
        before = rss()
        tracemalloc.start()
        for _ in range(5): value = call()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {'p50_ms': statistics.median(s[0] for s in samples),
            'p95_ms': percentile([s[0] for s in samples], .95),
            'sql_min': min(s[1] for s in samples), 'sql_max': max(s[1] for s in samples),
            'bytes': max(s[2] for s in samples), 'visible_items': max(s[3] for s in samples), 'peak_allocated_bytes': peak,
            'rss_before_bytes': before, 'rss_after_bytes': rss(),
            'process_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    finally:
        event.remove(db.engine, 'before_cursor_execute', track)


def seed(f, args):
    db, owner, acl = f.db, f.owner, f.access
    spaces = SpaceService(db, acl)
    ids = [spaces.create(owner,'Benchmark '+str(i),idempotency_key='space-'+str(i))['id'] for i in range(11)]
    objects = ObjectService(db, acl)
    objects.register_type(owner, 'benchmark-reference', 'Synthetic record', {'type':'object'}, [])
    pools = {}
    # Real Wiki writes provide complete current generations for Option A's resolver.
    for space in ids:
        values=[]
        for n in range(100):
            kind = KINDS[n%5]
            identifier = uuid4()
            item={'kind':kind,'id':str(identifier),'space_id':space}
            if kind=='page':
                page=WikiService(db,acl).in_space(space).create_page(owner,'page-'+str(n),
                    'Synthetic guide','Synthetic body.',idempotency_key='page-'+str(n))
                item['id']=page['id']
            else:
                with db.engine.begin() as c:
                    params={'space':UUID(space),'id':identifier,'key':str(identifier)}
                    if kind=='object':
                        item['type_name']='benchmark-reference'
                        c.execute(text("INSERT INTO c0_objects(space_id,id,type_name,data,tags) VALUES (:space,:id,'benchmark-reference','{}','{}')"),params)
                    elif kind=='source':
                        c.execute(text("INSERT INTO c0_sources(space_id,id,ingest_key,title,metadata) VALUES (:space,:id,:key,'Synthetic source','{}')"),params)
                    elif kind=='entity':
                        c.execute(text("INSERT INTO c0_entities(space_id,id,kind,label,metadata) VALUES (:space,:id,'concept','Synthetic entity','{}')"),params)
                    else:
                        params['entity']=next(v['id'] for v in values if v['kind']=='entity')
                        c.execute(text("INSERT INTO c0_claims(space_id,id,entity_id,predicate,value,metadata,actor_id) VALUES (:space,:id,:entity,'supports','{}','{}',:id)"),params)
            values.append(item)
        pools[space]=values
    native=f.app.state.auth.oidc.verify_access_token(f.native['reader'])
    try: acl.resolve(native)
    except PermissionDenied: pass
    account=next(a for a in acl.list_accounts(owner) if a['username']=='reader')
    acl.set_role(owner,account['id'],Role.EDITOR)
    spaces.set_grant(owner,ids[0],account['id'],Role.EDITOR,expected_revision=0,idempotency_key='source-grant')
    for space in ids[1:]:
        spaces.set_grant(owner,space,account['id'],Role.READER,expected_revision=0,idempotency_key='grant-'+space)
    rng=random.Random(20261111)
    for pool in pools.values(): rng.shuffle(pool)
    cases=[]
    for count in args.references:
        for nspaces in args.spaces:
            for layout in args.layouts:
                source=objects.in_space(ids[0]).create(owner,'benchmark-reference',{})
                source={'kind':'object','id':str(source['id']),'type_name':'benchmark-reference'}
                targets=[]
                used={}
                for i in range(count):
                    space=ids[1+i%nspaces]
                    kind='object' if layout=='object' else KINDS[i%5]
                    pool=[item for item in pools[space] if item['kind']==kind]
                    index=used.get((space,kind),0)
                    targets.append(pool[index%len(pool)])
                    used[space,kind]=index+1
                # Uniqueness needs at least count distinct endpoints even at one space.
                # Generate additional object identities for the single-kind cases.
                if len({t['id'] for t in targets}) != count:
                    targets=[]
                    for i in range(count):
                        space=ids[1+i%nspaces]
                        row=objects.in_space(space).create(owner,'benchmark-reference',{})
                        targets.append({'space_id':space,'kind':'object','id':str(row['id']),'type_name':'benchmark-reference'})
                cases.append({'source':source,'targets':targets,'selected':ids[1:1+nspaces],
                              'count':count,'spaces':nspaces,'layout':layout})
    if not args.baseline:
        from czero_core.cross_space_references import CrossSpaceReferenceService
        refs=CrossSpaceReferenceService(db,acl)
        for case in cases:
            for target in case['targets']:
                refs.create(owner,space_id=ids[0],source=case['source'],target=target,idempotency_key=uuid4().hex)
    # One high-degree source, not merely many unrelated low-degree sources.
    # Both original and candidate receive the same 100000 synthetic target objects.
    dense=objects.in_space(ids[0]).create(owner,'benchmark-reference',{})
    dense={'kind':'object','id':str(dense['id']),'type_name':'benchmark-reference'}
    dense_targets=[]
    for start in range(0,100000,1000):
        rows=[]
        for n in range(start,start+1000):
            tid=UUID(hashlib.md5(('corpus-target-'+str(n)).encode()).hexdigest())
            target_space=UUID(ids[1+n%10])
            rows.append({'id':uuid4(),'space':UUID(ids[0]),'source':UUID(dense['id']),
                         'target_space':target_space,'target':tid,'actor':owner.user_id})
            if n<100:dense_targets.append({'space_id':str(target_space),'kind':'object',
                                           'id':str(tid),'type_name':'benchmark-reference'})
        with db.engine.begin() as c:
            c.execute(text("""INSERT INTO c0_objects(space_id,id,type_name,data,tags)
                VALUES (:target_space,:target,'benchmark-reference','{}','{}')"""),rows)
            if not args.baseline:
                c.execute(text("""INSERT INTO c0_cross_space_references(id,source_space_id,source_kind,source_id,
                    target_space_id,target_kind,target_id,relation_kind,created_by,source_object_id,target_object_id)
                    VALUES (:id,:space,'object',:source,:target_space,'object',:target,'references',:actor,:source,:target)"""),rows)
    cases.append({'source':dense,'targets':dense_targets,'selected':ids[1:],
                  'count':100,'spaces':10,'layout':'object','corpus_refs':100000})
    with db.engine.begin() as c:c.execute(text('ANALYZE'))
    # Same-space controls remain within the existing entity degree bound.
    source=next(v for v in pools[ids[0]] if v['kind']=='object')
    for target in pools[ids[0]][5:]:
        if target['kind']=='object' and target['id']!=source['id']: objects.in_space(ids[0]).add_relation(owner,source['id'],target['id'],'references',source_type='benchmark-reference',target_type='benchmark-reference')
    entity=next(v for v in pools[ids[0]] if v['kind']=='entity')
    knowledge=KnowledgeService(db,acl).in_space(ids[0])
    for target in pools[ids[0]][:25]:
        if target['kind'] in ('page','object','source'):
            knowledge.link_entity(owner,entity['id'],target['kind'],target['id'],idempotency_key=uuid4().hex)
    return spaces,ids,native,cases,source,entity


def principal(f, native, ids, auth, visible):
    native=replace(native,expires_at=time.time()+3600)
    owner=f.access.resolve(native)
    sessions=f.app.state.auth.sessions
    if auth=='key':
        keys=ApiKeyService(f.access,client_id='benchmark',client_secret='synthetic',resource=ORIGIN+'/mcp')
        value=keys.create(owner,name='Benchmark',scopes={'c0:read'},space_ids=[ids[0],*visible])
        return keys.verify(value['key'],resource=keys.resource).actor
    if getattr(f,'benchmark_cookie',None): sessions.logout(f.benchmark_cookie,f.benchmark_csrf)
    f.benchmark_cookie=sessions.create(native)
    session=sessions.get(f.benchmark_cookie)
    f.benchmark_csrf=session.csrf_token
    if auth=='session':return session.actor
    grants=f.app.state.delegated_grants
    if getattr(f,'benchmark_refresh',None):
        grants.revoke(f.benchmark_refresh,f.client['client_id'],resource=grants.resource)
    verifier=secrets.token_urlsafe(32)
    code=grants.issue_code(session,f.client['client_id'],callback=CALLBACK,scopes={'c0:read'},
                           challenge=pkce_challenge(verifier),resource=ORIGIN+'/mcp')
    pair=grants.exchange_code(code,f.client['client_id'],callback=CALLBACK,verifier=verifier,resource=ORIGIN+'/mcp')
    f.benchmark_refresh=pair.refresh_token
    return grants.verify(pair.access_token,resource=grants.resource).actor


def revocation_probe(f, ids, native, case):
    """Five admitted readers must finish before a waiting grant revocation."""
    from czero_core.cross_space_references import CrossSpaceReferenceService
    spaces=SpaceService(f.db,f.access)
    account=f.access.resolve(replace(native,expires_at=time.time()+300)).user_id
    target=case['selected'][0]
    revision=next(g['revision'] for g in spaces.list_grants(f.owner,target)['grants'] if g['account_id']==str(account))
    saved=spaces.set_grant(f.owner,target,account,Role.READER,expected_revision=revision,idempotency_key=uuid4().hex)
    actor=principal(f,native,ids,'session',[target])
    service=CrossSpaceReferenceService(f.db,f.access)
    admitted=threading.Barrier(6);release=threading.Event();revoking=threading.Event()
    original=service._available
    def pause(c,space,endpoint,**kwargs):
        admitted.wait(5)
        if not release.wait(5):raise RuntimeError('reader_barrier_timeout')
        return original(c,space,endpoint,**kwargs)
    service._available=pause
    arguments={'space_id':ids[0],'source':case['source'],'target_space_ids':case['selected'],'limit':100}
    def revoke():
        revoking.set()
        start=time.perf_counter()
        spaces.set_grant(f.owner,target,account,None,expected_revision=saved['revision'],idempotency_key=uuid4().hex)
        return (time.perf_counter()-start)*1000
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            readers=[pool.submit(service.list,actor,**arguments) for _ in range(5)]
            admitted.wait(5)
            revoked=pool.submit(revoke)
            if not revoking.wait(5):raise RuntimeError('revoker_barrier_timeout')
            with f.db.engine.connect() as c:
                for _ in range(100):
                    waiting=c.execute(text("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database())")).scalar_one()
                    if waiting:break
            assert waiting and not revoked.done(), 'revocation_did_not_wait_for_admitted_readers'
            release.set()
            completed=[r.result(5) for r in readers]
            elapsed=revoked.result(5)
    finally:
        release.set();service._available=original
    later=service.list(actor,**arguments)
    assert all(row['target']['space_id']!=target for row in later['references'])
    return {'concurrent_readers':len(completed),'revocation_wait_and_commit_ms':elapsed,
            'post_revocation_target_items':0,'deadlocks':0,'timeouts':0}


async def run(args):
    evidence={'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
              'parameters':vars(args),'seed':20261111,'measurements':[],
              'notes':['Server-side Core timings exclude HTTP/client serialization.',
                       'Half visibility grants alternate target spaces; one selected space cannot have partial per-resource permissions.',
                       'Missing targets are hard deleted and their references cascade; there are no dangling placeholders.']}
    output=Path(args.output)
    def save(): output.write_text(json.dumps(evidence,indent=2,default=str)+'\n')
    async with disposable_database(os.environ['CZERO_TEST_DATABASE_URL']) as url:
        f=Fixture(url,output.parent)
        try:
            spaces,ids,native,cases,control,entity=seed(f,args)
            resolver=ObjectService(f.db,f.access,reference_resolvers={**f.app.state.sources.reference_resolvers(),
                **KnowledgeService(f.db,f.access).reference_resolvers()})
            if args.availability != 'active':
                with f.db.engine.begin() as c:
                    if args.availability == 'archived':
                        for kind,table in TABLES.items():
                            if kind != 'object':
                                c.execute(text('UPDATE '+table+' SET deleted=true WHERE space_id=ANY(CAST(:spaces AS uuid[]))'),{'spaces':ids[1:]})
                    else:
                        for table in ('c0_claims','c0_entities','c0_wiki_revisions','c0_wiki_pages','c0_sources','c0_objects'):
                            c.execute(text('DELETE FROM '+table+' WHERE space_id=ANY(CAST(:spaces AS uuid[]))'),{'spaces':ids[1:]})
            grants={space:1 for space in ids[1:]}
            for visibility in args.visibility:
                allowed=ids[1:] if visibility in ('all','archived','missing') else [] if visibility=='none' else ids[1::2]
                for space in ids[1:]:
                    spaces.set_grant(f.owner,space,spaces.access.resolve(replace(native,expires_at=time.time()+300)).user_id,
                        Role.READER if space in allowed else None,expected_revision=grants[space],idempotency_key=uuid4().hex)
                    # Unchanged saves retain their revision; read it back exactly.
                    grants[space]=next(g['revision'] for g in spaces.list_grants(f.owner,space)['grants'])
                for auth in args.auth:
                    key_actor=principal(f,native,ids,auth,allowed) if auth=='key' else None
                    for case in cases:
                        for concurrency in args.concurrency:
                            for repetition in range(args.repetitions):
                                actor=key_actor or principal(f,native,ids,auth,allowed)
                                if args.baseline:
                                    calls={
                                        'object_relations':lambda:resolver.in_space(ids[0]).relations(actor,control['id']),
                                        'entity_links':lambda:KnowledgeService(f.db,f.access).in_space(ids[0]).entity_links(actor,entity['id']),
                                        'independent_resolution':lambda:[resolver.in_space(t['space_id']).resolve_reference(
                                            actor,t['kind'],t['id'],t.get('type_name',t['kind']))
                                            for t in case['targets'] if t['space_id'] in allowed]}
                                else:
                                    from czero_core.cross_space_references import CrossSpaceReferenceService
                                    service=CrossSpaceReferenceService(f.db,f.access)
                                    calls={'cross_space_list':lambda:service.list(actor,space_id=ids[0],source=case['source'],
                                        target_space_ids=case['selected'],limit=100)}
                                for operation,call in calls.items():
                                    if args.baseline and operation not in args.controls: continue
                                    result=measure(f.db,call,args,concurrency)
                                    evidence['measurements'].append({'count':case['count'],'spaces':case['spaces'],
                                        'layout':case['layout'],'corpus_refs':case.get('corpus_refs',case['count']),
                                        'availability':args.availability,'visibility':visibility,'auth':auth,
                                        'concurrency':concurrency,'repetition':repetition,'operation':operation,**result})
                                    save()
            if not args.baseline:
                from czero_core.cross_space_references import _LIST
                case=cases[-1]
                evidence['revocation']=revocation_probe(f,ids,native,case)
                with f.db.engine.begin() as c:
                    query='EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+str(_LIST)
                    evidence['query_plan']=c.execute(text(query),{'space':UUID(ids[0]),'kind':'object','source':case['source']['id'],
                        'targets':[UUID(s) for s in case['selected']],'after':None,'limit':101}).scalar_one()
            save()
        finally: await f.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--availability',choices=['active','archived','missing'],default='active')
    parser.add_argument('--controls',nargs='+',choices=['object_relations','entity_links','independent_resolution'],default=['object_relations','entity_links','independent_resolution'])
    parser.add_argument('--samples',type=int,default=200)
    parser.add_argument('--warmups',type=int,default=20)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--references',type=int,nargs='+',default=[1,10,50,100])
    parser.add_argument('--spaces',type=int,nargs='+',default=[1,2,5,10])
    parser.add_argument('--concurrency',type=int,nargs='+',default=[1,5])
    parser.add_argument('--layouts',nargs='+',choices=['object','mixed'],default=['object','mixed'])
    parser.add_argument('--visibility',nargs='+',choices=['all','half','none'],default=['all','half','none'])
    parser.add_argument('--auth',nargs='+',choices=['session','oauth','key'],default=['session','oauth','key'])
    args=parser.parse_args()
    if any(n not in (1,10,50,100) for n in args.references) or any(n not in (1,2,5,10) for n in args.spaces):parser.error('outside v1 matrix')
    if args.baseline and args.availability!='active':parser.error('baseline controls require active endpoints')
    if min(args.samples,args.warmups,args.repetitions)<1:parser.error('positive sample counts required')
    asyncio.run(run(args))


if __name__=='__main__': main()
