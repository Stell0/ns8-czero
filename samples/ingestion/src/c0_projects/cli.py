# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit private-job CLI; no scheduler, migration or interactive auth fallback."""
import argparse
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys
from uuid import uuid4

from c0_ingest.auth import locked, login, disconnect
from c0_ingest.cli import bind_account
from c0_ingest.client import C0
from c0_ingest.config import connection_settings
from c0_ingest.errors import C0Error
from c0_ingest.jobs import check_job
from c0_ingest.state import atomic, read, safe_path
from github_vault.github_client import GitHub, GitHubError
from .adapters import collect, safe_read
from .model import load_config, Item, Batch, now, sha
from .workflow import SourceWorkflow
from .agent_packages import save_package
from .publish import approved, listing, parts, sync_part, verify, prior_receipt, locate, save_snapshot


def save_scan(directory,batches):
    if directory.exists():raise C0Error('scan_identity_already_exists')
    directory.mkdir(parents=True,mode=0o700)
    manifest={'schema_version':1,'created_at':now(),'sources':[]}
    for connector,batch in batches:
        entries=[]
        for index,item in enumerate(batch.items):
            name=connector['id']+'-'+str(index)+'.bin'
            atomic(directory/name,item.content)
            entries.append({**item.metadata(),'path':name})
        manifest['sources'].append({'connector_id':connector['id'],'definition_hash':sha(connector),
            'items':entries,'status':batch.status,'errors':batch.errors,'cursor':batch.cursor,'retry_after':batch.retry_after,'attempted':batch.attempted})
    atomic(directory/'manifest.json',manifest)
    return manifest


def load_scan(directory):
    path=directory/'manifest.json'
    if path.stat().st_size>4*1024*1024:raise C0Error('scan_manifest_too_large')
    manifest=json.loads(safe_read(directory,'manifest.json',4*1024*1024))
    if manifest.get('schema_version')!=1 or len(manifest['sources'])>100:
        raise C0Error('invalid_scan_manifest')
    total=0
    for source in manifest['sources']:
        for entry in source['items']:
            target=safe_path(directory,entry['path'])
            if target.is_symlink() or target.stat().st_size>16*1024*1024:
                raise C0Error('invalid_scan_content')
            content=safe_read(directory,entry['path'],16*1024*1024);total+=len(content)
            if total>64*1024*1024 or sha(content)!=entry['content_hash']:
                raise C0Error('scan_content_hash_or_limit_mismatch')
    return manifest


def item_from(directory,entry,connector):
    return Item(connector,entry['external_id'],entry['title'],safe_read(directory,entry['path'],16*1024*1024),
        entry['media_type'],entry['original_url'],entry['canonical_url'],entry['published_at'],entry['updated_at'],
        entry['retrieved_at'],entry['provenance'])


def connector_status(client,definition,batch,verified,discovered,verified_receipt_ids=None):
    existing=[r for r in listing(client,'project_records_list','objects',kind='connector_sync_v1') if r['data']['connector_id']==definition['id']]
    if len(existing)>1:raise C0Error('ambiguous_connector_state')
    status='complete' if batch.status=='complete' and verified==discovered else 'partial'
    data={'connector_id':definition['id'],'definition_hash':sha(definition),'last_attempt_at':now(),'last_success_at':'',
        'status':status,'last_error':batch.errors[0] if batch.errors else '', 'retry_after':batch.retry_after,'attempt_count':0,
        'remote_cursor':json.dumps(batch.cursor,sort_keys=True,separators=(',',':')),
        'progress_cursor':json.dumps(batch.cursor,sort_keys=True,separators=(',',':')),
        'verified_items':verified,'discovered_items':discovered}
    return client.call('project_connector_status_set',data={'data':data,'verified_receipt_ids':verified_receipt_ids or [],
        'expected_revision':existing[0]['revision'] if existing else 0,'idempotency_key':sha(['connector-status',data])})


def bootstrap(client,config,authorization_ref):
    current=client.call('project_get');manifest=current['data']['manifest'];writes=[]
    existing=listing(client,'project_records_list','objects',kind='connector_v1')
    for definition in config['sources']:
        previous=next((r for r in existing if r['data']['connector_id']==definition['id']),None)
        if previous and previous['data']['definition_hash']==sha(definition):continue
        result=client.call('project_connector_set',data={'definition':definition,'authorization_ref':authorization_ref,
            'expected_revision':previous['revision'] if previous else 0,
            'idempotency_key':sha(['source-approval',sha(definition),previous['revision'] if previous else 0])})
        writes.append(result['id'])
    identifiers=sorted(set(manifest['connector_ids'])|{d['id'] for d in config['sources']})
    if identifiers!=manifest['connector_ids']:
        result=client.call('project_configure',data={'manifest':{**manifest,'connector_ids':identifiers},
            'expected_revision':current['revision'],'authorization_ref':authorization_ref,
            'idempotency_key':sha(['source-configure',current['revision'],identifiers])})
        writes.append(result['id'])
    return {'status':'SAVED','resource_ids':writes,'connectors':len(config['sources'])}


def run(args, *, client_factory=C0):
    config=load_config(args.config,allow_empty_sources=args.group=='project') # Validate before network.
    job=(args.job or (args.config.parent.parent if args.config.parent.name=='config' else args.config.parent)).absolute()
    if args.operation=='validate':return {'status':'validated','connectors':len(config['sources']),'writes_c0':0},0
    check_job(job)
    connection=connection_settings(job)
    if connection['space_id']!=config['project_space_id'] or connection['url']!=config['server_url']:
        raise C0Error('configured_instance_or_space_binding_mismatch')
    state=job/'data/c0-projects'
    if (job/'data').is_symlink() or state.is_symlink():raise C0Error('unsafe_private_state_path')
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    with locked(job/'job.lock'):
        if args.group=='auth':
            if args.operation=='login':return login(connection),0
            if args.operation=='disconnect':return disconnect(connection),0
            return bind_account(connection,job),0
        if args.operation=='status':
            with ExitStack() as stack:
                client=client_factory(connection);stack.callback(client.close)
                selected=client.select_space(connection['space_id'],writable=False)
                if selected['name']!=connection['space_name']:raise C0Error('target_space_name_changed')
                return {'status':'observed','connectors':listing(client,'project_records_list','objects',kind='connector_sync_v1')},0
        with ExitStack() as stack:
            client=None
            if args.operation not in ('scan',):
                client=client_factory(connection,bootstrap=args.operation=='bootstrap');stack.callback(client.close)
                selected=client.select_space(connection['space_id'],writable=args.group!='project' and not args.dry_run and args.operation!='verify')
                if selected['name']!=connection['space_name']:raise C0Error('target_space_name_changed')
            if args.group=='project':
                if args.operation=='schedule':return client.call('project_schedule_get'),0
                if args.operation=='skill':
                    if not args.output:raise C0Error('explicit_package_output_required')
                    return save_package(client,args.output,format=args.format,connection=args.chatgpt_app_id),0
                raise C0Error('invalid_project_command')
            if args.operation=='bootstrap':
                if not args.apply or not args.authorization_ref:raise C0Error('explicit_admin_approval_required')
                return bootstrap(client,config,args.authorization_ref),0
            if (state/'latest.json').is_symlink() or (state/'publication.json').is_symlink() or (state/'scans').is_symlink():raise C0Error('unsafe_private_state_path')
            latest=read(state/'latest.json',{})
            if args.operation in ('scan','sync'):
                batches=[];total=0
                for definition in config['sources']:
                    if not definition['enabled']:continue
                    if client:approved(client,definition)
                    kwargs={};cursor={}
                    if client:
                        prior=[r for r in listing(client,'project_records_list','objects',kind='connector_sync_v1') if r['data']['connector_id']==definition['id'] and r['data']['definition_hash']==sha(definition)]
                        if prior and prior[0]['data']['progress_cursor']:cursor=json.loads(prior[0]['data']['progress_cursor'])
                        if prior and prior[0]['data']['retry_after']:
                            from datetime import datetime, timezone
                            if datetime.fromisoformat(prior[0]['data']['retry_after'])>datetime.now(timezone.utc):
                                batches.append((definition,Batch(cursor=cursor,status='partial',errors=['retry_deferred'],retry_after=prior[0]['data']['retry_after'],attempted=False)));continue
                    kwargs['cursor']=cursor
                    if definition['adapter']=='github':
                        cycle=cursor.get('cache_id') if cursor.get('complete') is False else uuid4().hex
                        import re
                        if not isinstance(cycle,str) or not re.fullmatch('[0-9a-f]{32}',cycle):raise C0Error('invalid_github_cache_binding')
                        cache=state/'github'/cycle
                        if cursor.get('complete') is False and not cache.exists():
                            # Lost frozen pages cannot justify resuming a mutable
                            # remote page offset. Re-enumerate and deduplicate.
                            cursor={};kwargs['cursor']=cursor;cycle=uuid4().hex;cache=state/'github'/cycle
                        cache.mkdir(parents=True,exist_ok=True,mode=0o700)
                        kwargs['github']=GitHub(cache,{'max_requests':definition['max_requests'],'max_retries':2,'max_wait_seconds':30},resume=True,anonymous=True,preserve_bodies=True,max_response_bytes=definition['max_bytes'],request_timeout=definition['timeout'])
                    try:
                        if definition['adapter']=='c0_space':
                            source=client_factory(connection);stack.callback(source.close)
                            source.select_space(definition['source_space_id'],writable=False);kwargs['source_client']=source
                        batch=collect(definition,root=job,**kwargs)
                        if definition['adapter']=='github':batch.cursor['cache_id']=cycle
                    except (C0Error,GitHubError):batch=Batch(cursor=cursor,status='partial',errors=['source_collection_failed'])
                    total+=sum(len(item.content) for item in batch.items)
                    if total>64*1024*1024:raise C0Error('scan_aggregate_limit')
                    batches.append((definition,batch))
                directory=state/'scans'/uuid4().hex;manifest=save_scan(directory,batches)
                atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest)})
                if args.operation=='scan':return {'status':'scanned','items':sum(len(b.items) for _,b in batches),'partial':any(b.status!='complete' for _,b in batches),'writes_c0':0},0 if all(b.status=='complete' for _,b in batches) else 2
            else:
                if not latest:raise C0Error('no_saved_scan_to_resume')
                directory=Path(latest['directory'])
                if not directory.resolve().is_relative_to(state.resolve()) or directory.is_symlink():raise C0Error('unsafe_scan_binding')
                manifest=load_scan(directory)
                if sha(manifest)!=latest['manifest_hash']:raise C0Error('scan_manifest_hash_mismatch')
            manifest=load_scan(directory);results=[];partial=False
            for source in manifest['sources']:
                definition=next((d for d in config['sources'] if d['id']==source['connector_id']),None)
                if not definition or sha(definition)!=source['definition_hash']:raise C0Error('scan_configuration_changed')
                approved(client,definition);verified=0;count=0;verified_refs=[]
                publisher=client
                if not args.dry_run and args.operation!='verify' and source.get('attempted',True):
                    publisher=SourceWorkflow(client,definition['id'],sha(manifest))
                verify_mode=args.operation=='verify' or (isinstance(publisher,SourceWorkflow) and publisher.completed)
                for entry in source['items']:
                    item=item_from(directory,entry,source['connector_id'])
                    item_results=[]
                    for part in parts(item):
                        count+=1
                        if count>1000:raise C0Error('publication_batch_limit')
                        if verify_mode:
                            previous=prior_receipt(client,part);stored,version=locate(client,part,previous)
                            if not previous or not version:raise C0Error('source_receipt_missing')
                            if previous['data']['sync_status']!='verified':raise C0Error('publication_pending_resume_required')
                            verify(client,part,version,attempts=connection['poll_attempts'],seconds=connection['poll_seconds']);verified+=1
                            results.append({'status':'verified','source_id':version['source_id'],'version_id':version['id'],'receipt_id':previous['id']})
                        else:
                            try:
                                result=sync_part(publisher,part,state/'publication.json',definition_hash=sha(definition),dry_run=args.dry_run,
                                    attempts=connection['poll_attempts'],seconds=connection['poll_seconds'])
                            except C0Error:
                                result={'status':'BLOCKED','external_id':part.external_id,'error':'publication_pending_resume'}
                            results.append(result);item_results.append(result)
                    if not args.dry_run and not verify_mode and item_results and all(r['status']=='verified' for r in item_results):
                        try:
                            save_snapshot(publisher,item,item_results)
                            verified+=len(item_results);verified_refs.extend(r['receipt_id'] for r in item_results)
                        except C0Error:
                            results.append({'status':'BLOCKED','external_id':item.external_id,'error':'source_snapshot_pending_resume'})
                batch=Batch(cursor=source['cursor'],status=source['status'],errors=source['errors'],retry_after=source['retry_after'])
                partial|=batch.status!='complete' or (not args.dry_run and verified!=count)
                if isinstance(publisher,SourceWorkflow) and not verify_mode:
                    coverage=connector_status(publisher,definition,batch,verified,count,verified_refs)
                    publisher.finish(coverage,batch.status=='complete' and verified==count)
            return {'status':'dry_run' if args.dry_run else 'PARTIAL' if partial else 'SAVED','items':len(results),'verified':sum(r['status']=='verified' for r in results),'resource_refs':results},2 if partial else 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('group',choices=['sources','auth','project'])
    parser.add_argument('operation',choices=['validate','scan','sync','status','verify','resume','bootstrap','login','bind-account','disconnect','skill','schedule'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--job',type=Path)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--authorization-ref')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--format',choices=['skill','plugin'],default='skill')
    parser.add_argument('--chatgpt-app-id',default='')
    args=parser.parse_args(argv)
    if args.group=='auth' and args.operation not in ('login','bind-account','disconnect'):parser.error('Choose an auth operation')
    if args.group=='sources' and args.operation in ('login','bind-account','disconnect'):parser.error('Choose a source operation')
    if args.group=='sources' and args.operation in ('skill','schedule'):parser.error('Choose a source operation')
    if args.group=='project' and args.operation not in ('validate','skill','schedule'):parser.error('Choose a project operation')
    if args.operation in ('sync','resume') and not args.dry_run and not args.apply:parser.error('Choose --dry-run or --apply explicitly')
    try:
        result,code=run(args);print(json.dumps(result,ensure_ascii=False,sort_keys=True));return code
    except (C0Error,OSError,ValueError,KeyError):
        print(json.dumps({'status':'BLOCKED','error':'operation_failed_inspect_private_state_and_authority'}));return 1


if __name__=='__main__':sys.exit(main())
