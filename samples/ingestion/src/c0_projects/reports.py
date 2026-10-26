# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic rendering/publication of externally authored report entries.

No research, semantic evaluation, external delivery or notification occurs here.
"""
from datetime import date
from uuid import UUID
from c0_ingest.errors import C0Error
from .model import sha
from .publish import listing

SECTIONS={
    'en':('New learnings','Changes affecting project goals','Connections with existing research',
        'Events and upcoming developments','Uncertainties and contradictions','Research completed',
        'Queued and deferred investigations','Monitoring coverage and failures','Operational details'),
    'it':('Nuove conoscenze','Cambiamenti per gli obiettivi del progetto','Collegamenti con la ricerca esistente',
        'Eventi e prossimi sviluppi','Incertezze e contraddizioni','Ricerche completate',
        'Indagini in coda e rinviate','Copertura e problemi del monitoraggio','Dettagli operativi'),
}


def validate_plan(plan):
    required={'lease','report_type','local_date','sections','entries'}
    if type(plan) is not dict or not required<=set(plan) or set(plan)-required-{'headings'}:
        raise C0Error('invalid_report_plan')
    if plan['report_type'] not in ('daily','weekly') or date.fromisoformat(plan['local_date']).isoformat()!=plan['local_date']:
        raise C0Error('invalid_report_cycle')
    if type(plan['lease']) is not dict or set(plan['lease'])!={'run_id','lease_owner','fencing_generation'}:
        raise C0Error('invalid_report_lease')
    sections=plan['sections'];entries=plan['entries']
    if 'headings' in plan and (type(plan['headings']) is not list or len(plan['headings'])!=9
            or any(type(value) is not str or not value.strip() or len(value)>256 or '\n' in value for value in plan['headings'])):
        raise C0Error('invalid_localized_report_headings')
    if (type(sections) is not list or len(sections)!=9 or any(type(value) is not str or len(value.encode())>8192 for value in sections)
            or type(entries) is not list or len(entries)>1000):raise C0Error('invalid_report_sections')
    seen=set()
    for entry in entries:
        if type(entry) is not dict or set(entry)!={'result_reference','disposition','text','reason','assessment_ref'}:
            raise C0Error('invalid_report_entry')
        UUID(entry['result_reference'])
        if entry['result_reference'] in seen:raise C0Error('duplicate_report_result')
        seen.add(entry['result_reference'])
        if entry['disposition'] not in ('included','deferred'):raise C0Error('invalid_report_disposition')
        if any(type(entry[key]) is not str or len(entry[key].encode())>8192 for key in ('text','reason','assessment_ref')):
            raise C0Error('invalid_report_entry_text')
        if len(entry['text'].strip())<8 or not entry['assessment_ref'].strip() or len(entry['assessment_ref'])>512:
            raise C0Error('substantive_report_entry_required')
        if len(entry['reason'])>1024 or (entry['disposition']=='deferred' and not entry['reason'].strip()):
            raise C0Error('explicit_report_deferral_reason_required')
    return plan


def render(plan,language):
    """Other languages require nine explicit localized headings from the agent."""
    validate_plan(plan)
    headings=plan.get('headings',SECTIONS.get(language))
    if headings is None:raise C0Error('localized_report_headings_required')
    title=(headings[0] if language not in SECTIONS else 'Rapporto di ricerca' if language=='it' else 'Research report')+' · '+plan['local_date']
    body='# '+title+'\n';ranges=[]
    for index,(heading,prose) in enumerate(zip(headings,plan['sections'])):
        body+='\n## '+heading+'\n\n'+prose.strip()+'\n'
        if index==5:
            for entry in plan['entries']:
                text=entry['text'].strip();body+='\n';start=len(body.encode());body+=text
                ranges.append((entry,start,len(body.encode())));body+='\n'
    if len(body.encode())>131072:raise C0Error('report_body_requires_saved_appendices')
    return title,body,ranges


def save_report(client,plan):
    """Resume identical lost responses using stored draft/member revisions."""
    validate_plan(plan);stored=client.call('project_get');manifest=stored['data']['manifest']
    if manifest['project_id']!=client.space_id or manifest['space_id']!=client.space_id:
        raise C0Error('project_report_binding_mismatch')
    title,body,ranges=render(plan,manifest['language']);lease=plan['lease']
    def mutation(name,values):
        return client.call(name,data={**values,'lease':lease,'idempotency_key':sha([name,lease,values])})
    prepared=mutation('project_report_prepare',{'report_type':plan['report_type'],'local_date':plan['local_date']})
    header=next(row for row in prepared['records'] if row['type_name'].endswith('report_v1'))
    if header['data']['saved_status']=='saved' and not header['data']['draft_open']:
        return client.call('project_report_get',report_type=plan['report_type'],local_date=plan['local_date'])
    wiki=client.call('wiki_pages_upsert',data={'slug':'project-reports/'+plan['report_type']+'/'+plan['local_date'],
        'title':title,'body':body,'metadata':{'c0_project':{'project_id':client.space_id,'report_reference':header['id'],
            'language':manifest['language']}},'idempotency_key':sha(['project-report-wiki',header['id'],body])})
    members=listing(client,'project_records_list','objects',kind='report_member_v1')
    for entry,start,end in ranges:
        previous=next((row for row in members if row['data']['report_reference']==header['id']
            and row['data']['draft_generation']==header['data']['draft_generation']
            and row['data']['result_reference']==entry['result_reference']),None)
        values={'result_reference':entry['result_reference'],'disposition':entry['disposition'],'location':'main',
            'wiki_revision_id':wiki['content']['id'],'start_byte':start,'end_byte':end,
            'reason':entry['reason'],'assessment_ref':entry['assessment_ref']}
        if previous and all(previous['data'].get(key)==value for key,value in values.items()):continue
        mutation('project_report_member_set',{'report_reference':header['id'],'data':values,
            'expected_revision':previous['revision'] if previous else 0})
    mutation('project_report_finalize',{'report_reference':header['id'],'wiki_revision_id':wiki['content']['id']})
    verified=client.call('project_report_get',report_type=plan['report_type'],local_date=plan['local_date'])
    if verified['report']['data']['wiki_revision_id']!=wiki['content']['id']:
        raise C0Error('project_report_readback_mismatch')
    return verified
