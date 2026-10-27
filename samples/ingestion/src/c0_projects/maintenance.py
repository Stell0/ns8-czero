# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded public workflow metadata checks; never download/install executable code."""
from datetime import datetime,timezone,timedelta
import json,re
from urllib.parse import quote
from zoneinfo import ZoneInfo
from c0_ingest.errors import C0Error
from c0_ingest.sources import submit_text,verify_document
from .fetch import Fetcher,FetchError
from .model import sha,now
from .publish import listing

REPOSITORIES=('Stell0/ns8-czero','Kabutojira/WikiPlant')


def validate_release_plan(plan):
    if (type(plan) is not dict or set(plan)!={'lease','repository','installed_version'} or plan['repository'] not in REPOSITORIES
            or type(plan['lease']) is not dict or set(plan['lease'])!={'run_id','lease_owner','fencing_generation'}
            or type(plan['installed_version']) is not str or not re.fullmatch(r'(?:core-)?v?[0-9]+\.[0-9]+\.[0-9]+',plan['installed_version'])):
        raise C0Error('invalid_release_check_plan')
    lease=plan['lease']
    if (any(type(lease[key]) is not str or not 1<=len(lease[key])<=limit for key,limit in (('run_id',64),('lease_owner',128)))
            or type(lease['fencing_generation']) is not int or not 1<=lease['fencing_generation']<=2147483647):
        raise C0Error('invalid_release_check_lease')
    return plan


def collect_release(repository,fetcher=None):
    if repository not in REPOSITORIES:raise C0Error('untrusted_workflow_repository')
    fetcher=fetcher or Fetcher({'max_requests':5,'max_bytes':1024*1024,'timeout':15},accept_json=True)
    base='https://api.github.com/repos/'+repository
    def get(url):
        raw,_,media=fetcher.get(url)
        if media not in ('application/json','application/vnd.github+json'):raise C0Error('release_metadata_not_json')
        try:return json.loads(raw)
        except (ValueError,RecursionError):raise C0Error('release_metadata_invalid') from None
    repo=get(base)
    if type(repo) is not dict or type(repo.get('full_name')) is not str or repo['full_name'].lower()!=repository.lower() or repo.get('private') is not False:
        raise C0Error('release_repository_not_verified_public')
    result={'repository':repository,'complete':True,'fresh':True,'releases':[]}
    try:release=get(base+'/releases/latest')
    except FetchError as error:
        if str(error)=='source_http_404':return result
        raise
    if (type(release) is not dict or type(release.get('id')) is not int or release['id']<1
            or release.get('draft') is not False or release.get('prerelease') is not False
            or type(release.get('tag_name')) is not str
            or not re.fullmatch(r'(?:core-)?v?[0-9]+\.[0-9]+\.[0-9]+',release['tag_name'])):
        raise C0Error('release_identity_invalid')
    reference=get(base+'/git/ref/tags/'+quote(release['tag_name'],safe=''))
    target=reference.get('object',{}) if type(reference) is dict else {}
    for _ in range(3):
        if type(target) is not dict or type(target.get('sha')) is not str or not re.fullmatch('[0-9a-f]{40}',target['sha']):raise C0Error('release_commit_unresolved')
        if target.get('type')=='commit':break
        if target.get('type')!='tag':raise C0Error('release_commit_unresolved')
        tag=get(base+'/git/tags/'+target['sha'])
        target=tag.get('object',{}) if type(tag) is dict else {}
    else:raise C0Error('release_tag_depth_limit')
    result['releases']=[{'version':release['tag_name'],'release_id':str(release['id']),'source_commit':target['sha']}]
    return result


def check_release(client,plan,*,dry_run=False,collector=collect_release):
    validate_release_plan(plan);stored=client.call('project_get');config=stored['data']['manifest']
    run=client.call('project_record_get',kind='run_v1',identity=plan['lease']['run_id'])['data']
    if (any(run[key]!=value for key,value in plan['lease'].items()) or run['state']!='running'
            or run['workflow_type'] not in ('weekly','maintenance') or run['config_version']!=stored['data']['version']
            or not run['lease_expiry'] or datetime.fromisoformat(run['lease_expiry'])<=datetime.now(timezone.utc)):
        raise C0Error('release_check_lease_not_current')
    previous=next((row for row in listing(client,'project_records_list','objects',kind='release_check_v1')
        if row['data']['repository']==plan['repository']),None)
    today=datetime.now(timezone.utc).astimezone(ZoneInfo(config['timezone'])).date();week=(today-timedelta(days=today.weekday())).isoformat()
    if previous and previous['data']['week_start']==week and (previous['data']['attempts']>=3 or previous['data']['retry_after']
            and datetime.fromisoformat(previous['data']['retry_after'])>datetime.now(timezone.utc)):
        return {'status':'BLOCKED','outcome':'release_retry_not_due','records':[previous]}
    error='';metadata=None;version_id=''
    try:metadata=collector(plan['repository'])
    except (C0Error,OSError,ValueError,KeyError,RecursionError):error='metadata_fetch_failed'
    if dry_run:return {'status':'dry_run','metadata':metadata,'error_code':error,'writes_c0':0}
    if metadata is not None:
        body=json.dumps(metadata,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        external='project-workflow-release:'+plan['repository']
        matches=[row for row in listing(client,'sources_list','sources') if not row['deleted'] and row['metadata'].get('external_key')==external]
        if len(matches)>1:raise C0Error('ambiguous_release_source')
        source=matches[0] if matches else None
        versions=listing(client,'source_versions_list','versions',source_id=source['id']) if source else []
        version=next((row for row in versions if row['content_hash']==sha(body.encode())),None)
        if not version:version=submit_text(client,body=body,title='Workflow release metadata: '+plan['repository'],
            metadata={'external_key':external,'source_type':'workflow_release_metadata','repository':plan['repository'],
                'connector_id':'workflow-updates','original_url':'https://api.github.com/repos/'+plan['repository']+'/releases/latest',
                'canonical_url':'https://api.github.com/repos/'+plan['repository']+'/releases/latest',
                'retrieved_at':now(),'published_at':'','updated_at':''},
            external_key=external,source=source)
        verify_document(client,version,body,attempts=client.config['poll_attempts'],seconds=client.config['poll_seconds'])
        version_id=version['id']
    values={**plan,'metadata_version_id':version_id,'error_code':error}
    return client.call('project_release_observe',data={**values,'idempotency_key':sha(['release-observation',values,previous['revision'] if previous else 0])})
