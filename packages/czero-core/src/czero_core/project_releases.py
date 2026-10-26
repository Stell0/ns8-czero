# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Version observations from saved metadata, never runtime installation."""
from datetime import timedelta
import hashlib,json,re
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import text
from .project_workflows import data_of,receipt,digest

def release_version(value):
    if type(value) is not str:raise ValueError('invalid_release_version')
    match=re.fullmatch(r'(?:core-)?v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',value)
    if not match:raise ValueError('invalid_release_version')
    return tuple(int(part) for part in match.groups())


class ProjectReleases:
    def _release_metadata(self,connection,version_id,repository):
        row=connection.execute(text('''SELECT d.body,d.text_hash,v.state,s.metadata FROM c0_documents d
            JOIN c0_source_versions v ON v.id=d.version_id AND v.space_id=d.space_id
            JOIN c0_sources s ON s.id=v.source_id AND s.space_id=v.space_id
            WHERE v.space_id=:space AND v.id=CAST(:id AS uuid) AND NOT s.deleted'''),{'space':self._space_id,'id':version_id}).mappings().one_or_none()
        if (not row or row['state']!='ready' or row['metadata'].get('source_type')!='workflow_release_metadata'
                or row['metadata'].get('repository')!=repository):raise ValueError('release_metadata_not_ready_or_bound')
        if hashlib.sha256(row['body'].encode()).hexdigest()!=row['text_hash']:raise ValueError('release_metadata_hash_mismatch')
        try:metadata=json.loads(row['body'])
        except (ValueError,RecursionError):raise ValueError('invalid_release_metadata') from None
        if (type(metadata) is not dict or set(metadata)!={'repository','complete','fresh','releases'}
                or metadata['repository']!=repository or type(metadata['complete']) is not bool or type(metadata['fresh']) is not bool
                or type(metadata['releases']) is not list or len(metadata['releases'])>10):raise ValueError('invalid_release_metadata')
        known={}
        for release in metadata['releases']:
            if (type(release) is not dict or set(release)!={'version','release_id','source_commit'}
                    or type(release['release_id']) is not str or not 1<=len(release['release_id'])<=128
                    or type(release['source_commit']) is not str or not re.fullmatch('[0-9a-f]{40}',release['source_commit'])):
                raise ValueError('invalid_release_identity')
            release_version(release['version'])
            if release['version'] in known:raise ValueError('duplicate_release_version')
            known[release['version']]=digest(release)
        return metadata,known,row['text_hash']

    def observe_release(self,actor,lease,repository,installed_version,*,metadata_version_id='',error_code='',idempotency_key):
        if type(repository) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}',repository):
            raise ValueError('invalid_workflow_repository')
        installed=release_version(installed_version)
        if metadata_version_id:UUID(metadata_version_id)
        if type(error_code) is not str or len(error_code)>128 or bool(error_code)==bool(metadata_version_id):
            raise ValueError('release_observation_requires_metadata_or_error')
        def execute(connection,current,run_row):
            self._maintenance_run(run_row['data']);now=self.clock()
            day=now.astimezone(ZoneInfo(self._manifest(connection)['data']['manifest']['timezone'])).date()
            week=(day-timedelta(days=day.weekday())).isoformat();previous=self._find(connection,'release_check_v1',repository,required=False)
            same=previous and previous['data']['week_start']==week
            if same and (previous['data']['attempts']>=3 or previous['data']['retry_after'] and now<self._parse_release_retry(previous)):
                return receipt('BLOCKED','release_retry_not_due',previous)
            values={'repository':repository,'installed_version':installed_version,'latest_version':'',
                'metadata_version_id':previous['data']['metadata_version_id'] if previous else '',
                'metadata_hash':previous['data']['metadata_hash'] if previous else '',
                'status':'security_alert' if previous and previous['data']['status']=='security_alert' else 'failed',
                'summary':'Metadata retrieval failed; available version remains unknown.',
                'checked_at':now.isoformat(),'last_success_at':previous['data']['last_success_at'] if previous else '',
                'week_start':week,'retry_after':(now+timedelta(hours=1)).isoformat(),
                'attempts':previous['data']['attempts']+1 if same else 1}
            if metadata_version_id:
                metadata,known,content_hash=self._release_metadata(connection,metadata_version_id,repository)
                complete=metadata['complete'] and metadata['fresh']
                status='no_release' if not known else 'up_to_date'
                latest=max(known,key=release_version) if known else ''
                if latest and release_version(latest)>installed:status='available'
                for version,identity_hash in known.items():
                    identity=digest([repository,version]);baseline=self._find(connection,'release_identity_v1',identity,required=False)
                    if baseline and baseline['data']['identity_hash']!=identity_hash:status='security_alert'
                    elif not baseline and complete:
                        self._save(connection,current,'release_identity_v1',identity,{'repository':repository,'version':version,
                            'identity_hash':identity_hash,'metadata_version_id':metadata_version_id,'observed_at':now.isoformat()})
                if previous and previous['data']['status']=='security_alert':status='security_alert'
                if not complete and status!='security_alert':status='partial'
                values.update(metadata_version_id=metadata_version_id,metadata_hash=content_hash,status=status,latest_version=latest,
                    summary='Saved fresh bounded release metadata; compatibility and installation require the established reviewed update workflow.'
                        if complete else 'Incomplete/stale metadata cannot establish an up-to-date workflow.',
                    last_success_at=now.isoformat() if complete else values['last_success_at'],
                    retry_after='' if complete else values['retry_after'])
            saved=self._save(connection,current,'release_check_v1',repository,values,previous=previous)
            history=self._save(connection,current,'release_check_history_v1',digest(values),values)
            return receipt('SAVED' if values['status'] in ('available','up_to_date','no_release') else 'BLOCKED'
                if values['status'] in ('failed','security_alert') else 'PARTIAL','release_metadata_observed',saved,history)
        return self._workflow_mutate(actor,'release_observe',{'repository':repository,'installed_version':installed_version,
            'metadata_version_id':metadata_version_id,'error_code':error_code},idempotency_key,lease,execute)

    @staticmethod
    def _parse_release_retry(previous):
        from .project_schema import timestamp
        return timestamp(previous['data']['retry_after'])
