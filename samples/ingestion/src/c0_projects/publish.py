# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""C0 publication/readback is separate from source collection and reasoning."""
from dataclasses import dataclass
import json
from pathlib import Path
from time import sleep,perf_counter

import httpx2
from c0_ingest.auth import credentials
from c0_ingest.errors import C0Error
from c0_ingest.sources import submit_text, verify_document
from c0_ingest.state import atomic, read
from .model import Item, now, sha


@dataclass(frozen=True)
class Part:
    item: Item
    external_id: str
    number: int
    content: bytes
    start_byte: int
    end_byte: int


def parts(item, limit=None):
    if item.media_type not in ('text/plain','text/markdown'):
        yield Part(item,sha([item.external_id,1]),1,item.content,0,len(item.content));return
    text=item.content.decode('utf-8')
    if limit is None:
        if len(item.content)<=2*1024*1024 and len(text)<=1_000_000:
            yield Part(item,sha([item.external_id,1]),1,item.content,0,len(item.content));return
        limit=131072
    if type(limit) is not int or not 1<=limit<=131072:raise C0Error('invalid_source_part_limit')
    start=0;offset=0;number=0
    while start<len(text):
        low=start+1;high=min(len(text),start+limit)
        while low<=high:
            middle=(low+high)//2
            if len(text[start:middle].encode())<=limit: low=middle+1
            else: high=middle-1
        end=high
        if end<len(text):
            boundary=text.rfind('\n\n',start,end)
            if boundary>start+(end-start)//2: end=boundary+2
        content=text[start:end].encode();number+=1
        if number>100: raise C0Error('source_part_limit')
        yield Part(item,sha([item.external_id,number]),number,content,offset,offset+len(content))
        offset+=len(content);start=end


def publication_parts(client,item):
    # Preserve existing multipart layouts on unchanged retries. New documents
    # that fit extraction limits can use one REST upload instead of text MCP.
    previous=client.call('objects_list',type_name='c0_project_source_snapshot_v1',
        where=json.dumps({'connector_id':item.connector_id,'external_id':item.external_id}),limit=2,offset=0)['objects']
    if len(previous)>1:raise C0Error('ambiguous_source_snapshot')
    return parts(item,limit=131072 if previous and len(previous[0]['data']['part_receipt_ids'])>1 else None)


def listing(client,name,field,**arguments):
    rows=[]
    for offset in range(0,10000,100):
        page=client.call(name,limit=100,offset=offset,**arguments)[field]
        rows.extend(page)
        if len(page)<100:return rows
    raise C0Error('source_inventory_incomplete')


def approved(client, config):
    manifest=client.call('project_get')['data']['manifest']
    connectors=listing(client,'project_records_list','objects',kind='connector_v1')
    match=next((r for r in connectors if r['data']['connector_id']==config['id']),None)
    if not match or match['data']['definition_hash']!=sha(config) or config['id'] not in manifest['connector_ids'] or not config['enabled']:
        raise C0Error('source_definition_requires_project_approval')
    return match


def prior_receipt(client,part):
    rows=client.call('objects_list',type_name='c0_project_source_sync_v1',
        where=json.dumps({'connector_id':part.item.connector_id,'external_id':part.external_id}),limit=2,offset=0)['objects']
    if len(rows)>1:raise C0Error('ambiguous_source_receipt')
    return rows[0] if rows else None


def locate(client,part,prior):
    external_key=sha([part.item.connector_id,part.external_id])
    source_id=prior['data']['source_id'] if prior else None
    if source_id is None:
        matches=client.call('sources_list',external_key=external_key,limit=2,offset=0)['sources']
        if len(matches)>1: raise C0Error('ambiguous_external_source_identity')
        if matches:source_id=matches[0]['id']
    if source_id:
        source=client.call('sources_get',source_id=source_id)
        if source['deleted'] or source['metadata'].get('external_key')!=external_key:
            raise C0Error('source_identity_changed')
        versions=listing(client,'source_versions_list','versions',source_id=source_id)
        version=next((v for v in versions if v['content_hash']==sha(part.content)),None)
        return source,version
    return None,None


def upload_binary(client,part,source):
    if len(part.content)>10*1024*1024:raise C0Error('binary_upload_limit_exceeded')
    suffix={'text/markdown':'.md','text/plain':'.txt','application/pdf':'.pdf'}.get(part.item.media_type,'.docx')
    metadata={'external_key':sha([part.item.connector_id,part.external_id]),'connector_id':part.item.connector_id,
        'external_id':part.external_id,'parent_external_id':part.item.external_id,
        'original_url':part.item.original_url,'canonical_url':part.item.canonical_url,'provenance':part.item.provenance}
    form={'title':part.item.title[:240],'media_type':part.item.media_type,'retain_original':'false' if part.item.media_type in ('text/plain','text/markdown') else 'true',
          'metadata':json.dumps(metadata)}
    if source:form.update(source_id=source['id'],expected_revision=str(source['revision']))
    try:
        with httpx2.Client(follow_redirects=False,timeout=45) as http:
            response=http.post(client.config['url'].removesuffix('/mcp')+'/api/v1/sources/upload',
                params={'space_id':client.space_id},headers={'Authorization':'Bearer '+credentials(client.config)},
                data=form,files={'file':('evidence'+suffix,part.content,part.item.media_type)})
        if response.status_code!=202:raise C0Error('binary_publication_rejected')
        return response.json()
    except (httpx2.HTTPError,ValueError):
        raise C0Error('binary_publication_uncertain_reconcile_before_retry') from None


def verify(client,part,version,*,attempts=20,seconds=3,timings=None):
    if part.item.media_type in ('text/plain','text/markdown'):
        document=verify_document(client,version,part.content.decode(),attempts=attempts,seconds=seconds,timings=timings)
    else:
        for attempt in range(attempts):
            versions=listing(client,'source_versions_list','versions',source_id=version['source_id'])
            current=next((v for v in versions if v['id']==version['id']),None)
            if not current or current['content_hash']!=sha(part.content):raise C0Error('binary_version_readback_mismatch')
            if current['state']=='failed':raise C0Error('binary_extraction_failed')
            if current['state']=='ready':break
            if attempt+1<attempts:sleep(seconds)
        else:raise C0Error('binary_extraction_pending_resume')
        document=client.call('documents_get',version_id=version['id'])
    if document['version_id']!=version['id'] or sha(document['body'].encode())!=document['text_hash']:
        raise C0Error('document_readback_mismatch')
    # Staged part bytes are Editor-only. Exact citations become available after
    # the complete parent is atomically published, never during verification.
    return document


def sync_part(client,part,journal,*,definition_hash,dry_run=False,binary_publisher=upload_binary,attempts=20,seconds=3,timings=None):
    started=perf_counter();observed={}
    previous=prior_receipt(client,part)
    source,version=locate(client,part,previous)
    if dry_run:return {'status':'unchanged' if version else 'would_update' if source else 'would_create','external_id':part.external_id}
    intent={'connector_id':part.item.connector_id,'external_id':part.external_id,'content_hash':sha(part.content),
            'source_id':source['id'] if source else None,'source_revision':source['revision'] if source else 0}
    pending=read(journal,{})
    key=sha([client.space_id,part.item.connector_id,part.external_id,sha(part.content)])
    prior=pending.get(key,{})
    observations=prior.get('observations',{})
    observation=sha(part.item.metadata())
    applied=observations.get(observation)
    if applied and (not source or not version or applied['version_id']!=version['id'] or applied['source_revision']!=source['revision']):
        raise C0Error('source_observation_superseded_scan_and_reconcile_current')
    desired={'external_key':sha([part.item.connector_id,part.external_id]),'connector_id':part.item.connector_id,
        'external_id':part.external_id,'parent_external_id':part.item.external_id,
        'original_url':part.item.original_url,'canonical_url':part.item.canonical_url,'provenance':part.item.provenance}
    metadata_changed=source is not None and (source['title']!=part.item.title[:240] or source['metadata']!=desired)
    completed=prior.get('state')=='verified'
    if completed and not observations and (not version or metadata_changed):
        raise C0Error('legacy_source_journal_requires_current_reconciliation')
    if key in pending and prior['intent']!=intent and not completed:
        original_revision=prior['intent'].get('source_revision')
        known=version and prior.get('version',{}).get('id')==version['id']
        # One own submission may advance CAS before its reply is saved. Later
        # writes never authorize rebasing the old frozen intent onto new state.
        reconciled=(source and version and type(original_revision) is int and source['revision']==original_revision+1
            and (prior['intent']['source_id']==source['id'] or (prior['intent']['source_id'] is None and version['number']==1))
            and (known or not metadata_changed))
        if not reconciled:raise C0Error('uncertain_source_intent_requires_reconciliation')
    original_intent=intent if completed else prior.get('intent',intent)
    pending[key]={'intent':original_intent,'state':'prepared','observations':observations};atomic(journal,pending)
    if version is None or metadata_changed:
        if part.item.media_type in ('text/plain','text/markdown') and len(part.content)<=131072:
            metadata={'external_key':sha([part.item.connector_id,part.external_id]),'connector_id':part.item.connector_id,
                'external_id':part.external_id,'parent_external_id':part.item.external_id,
                'original_url':part.item.original_url,'canonical_url':part.item.canonical_url,'provenance':part.item.provenance}
            version=submit_text(client,body=part.content.decode(),title=part.item.title[:240],metadata=metadata,
                external_key=sha([part.item.connector_id,part.external_id]),media_type=part.item.media_type,source=source)
        else:version=binary_publisher(client,part,source)
    pending[key]={'intent':original_intent,'state':'submitted','version':version,'observations':observations};atomic(journal,pending)
    data={'connector_id':part.item.connector_id,'definition_hash':definition_hash,'external_id':part.external_id,'parent_external_id':part.item.external_id,
        'parent_content_hash':part.item.content_hash,'part_number':part.number,'start_byte':part.start_byte,'end_byte':part.end_byte,
        'last_attempt_at':now(),'last_success_at':'','last_content_hash':sha(part.content),
        'source_id':version['source_id'],'version_id':version['id'],'extraction_status':version['state'],
        'sync_status':'queued','last_error':'','retry_after':'','remote_cursor':'',
        'provenance':{**{k:part.item.metadata()[k] for k in ('original_url','canonical_url','retrieved_at','published_at','updated_at')},
            'details':json.dumps(part.item.provenance,sort_keys=True,separators=(',',':'))}}
    # Receipt keys include the full frozen payload. A lost receipt reply is
    # reconciled by its exact unique identity/current revision on the next run.
    if previous is None or previous['data']['version_id']!=version['id']:
        previous=client.call('project_source_status_set',data={'data':data,'expected_revision':previous['revision'] if previous else 0,
            'idempotency_key':sha(['source-submitted',key,sha(data)])})
    try:
        verify(client,part,version,attempts=attempts,seconds=seconds,timings=observed)
    except C0Error:
        failed={**data,'sync_status':'partial','last_error':'extraction_or_readback_pending_resume'}
        client.call('project_source_status_set',data={'data':failed,'expected_revision':previous['revision'],
            'idempotency_key':sha(['source-pending',key,sha(failed)])})
        raise
    versions=listing(client,'source_versions_list','versions',source_id=version['source_id'])
    current=next(v for v in versions if v['id']==version['id'])
    if (previous['data']['sync_status']=='verified' and previous['data']['last_content_hash']==sha(part.content)
            and previous['data']['provenance']['retrieved_at']==part.item.retrieved_at
            and previous['data']['parent_content_hash']==part.item.content_hash
            and previous['data']['start_byte']==part.start_byte and previous['data']['end_byte']==part.end_byte):
        result=previous
    else:
        data.update(extraction_status=current['state'],sync_status='verified')
        result=client.call('project_source_status_set',data={'data':data,'expected_revision':previous['revision'],
            'idempotency_key':sha(['source-verified',key,sha(data)])})
    readback=client.call('project_source_status_get',connector_id=part.item.connector_id,external_id=part.external_id)
    if readback['id']!=result['id'] or readback['data']['version_id']!=version['id'] or readback['data']['sync_status']!='verified':
        raise C0Error('source_receipt_readback_mismatch')
    observed_source=client.call('sources_get',source_id=version['source_id'])
    observations[observation]={'version_id':version['id'],'source_revision':observed_source['revision']}
    pending[key]={'intent':original_intent,'state':'verified','receipt':{'id':result['id'],'revision':result['revision']},'observations':observations};atomic(journal,pending)
    if timings is not None:
        observed['publication_seconds']=max(0.,perf_counter()-started-sum(observed.values()))
        for key,value in observed.items():timings[key]=timings.get(key,0.)+value
    return {'status':'verified','source_id':version['source_id'],'version_id':version['id'],'receipt_id':result['id']}


def save_snapshot(client,item,results,*,timings=None):
    started=perf_counter()
    if not results or any(row['status']!='verified' for row in results):raise C0Error('source_snapshot_not_verified')
    previous=client.call('objects_list',type_name='c0_project_source_snapshot_v1',
        where=json.dumps({'connector_id':item.connector_id,'external_id':item.external_id}),limit=2,offset=0)['objects']
    if len(previous)>1:raise C0Error('ambiguous_source_snapshot')
    if previous and previous[0]['data']['content_hash']==item.content_hash:
        verify_snapshot(client,item,previous[0],timings=timings)
        return previous[0]
    saved=client.call('project_source_snapshot_set',data={'connector_id':item.connector_id,'external_id':item.external_id,
        'content_hash':item.content_hash,'part_receipt_ids':[row['receipt_id'] for row in results],
        'expected_revision':previous[0]['revision'] if previous else 0,
        'idempotency_key':sha(['source-snapshot',item.key,item.content_hash,previous[0]['revision'] if previous else 0])})
    current=client.call('objects_get',object_id=saved['id'])
    if current!=saved:raise C0Error('source_snapshot_readback_mismatch')
    if timings is not None:timings['publication_seconds']=timings.get('publication_seconds',0.)+perf_counter()-started
    verify_snapshot(client,item,saved,timings=timings)
    return saved


def verify_snapshot(client,item,saved=None,*,timings=None):
    started=perf_counter()
    if saved is None:
        rows=client.call('objects_list',type_name='c0_project_source_snapshot_v1',
            where=json.dumps({'connector_id':item.connector_id,'external_id':item.external_id}),limit=2,offset=0)['objects']
        if len(rows)!=1:raise C0Error('current_snapshot_missing_or_ambiguous')
        saved=rows[0]
    full=client.call('source_documents_get',logical_document_id=saved['id'])
    if full['state']!='ready' or (item.media_type in ('text/plain','text/markdown') and (full['body'].encode()!=item.content or full['text_hash']!=item.content_hash)):
        raise C0Error('current_document_readback_mismatch')
    if timings is not None:timings['readback_seconds']=timings.get('readback_seconds',0.)+perf_counter()-started
    return full
