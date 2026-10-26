# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""External-runner calendar contracts and explicitly attributed observations."""
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from .object_schema import validate_record
from .project_schema import SCHEMAS, next_occurrence, occurrence_on_day
from .project_workflows import receipt


def schedule_contract(manifest,now):
    local=now.astimezone(ZoneInfo(manifest['timezone']))
    values={}
    for workflow in ('daily','weekly'):
        due=[]
        for offset in range(9):
            day=(local.date()-timedelta(days=offset)).isoformat()
            try:candidate=occurrence_on_day(manifest,workflow,day)
            except ValueError:continue
            if candidate<=now:due.append(candidate)
        latest=max(due)
        future=next_occurrence(manifest,workflow,now)
        values[workflow]={'latest_due':latest.isoformat(),
            'local_cycle_date':latest.astimezone(ZoneInfo(manifest['timezone'])).date().isoformat(),
            'next_occurrence':future.isoformat()}
    return {'timezone':manifest['timezone'],'server_now':now.isoformat(),'local_date':local.date().isoformat(),
        'desired':manifest['schedule'],'occurrences':values,'execution_provider':'external_agent',
        'installed_by_c0':False,'verification':'External installation, authentication and scheduled execution require observed host evidence.'}


class ProjectSchedules:
    def schedule(self,actor):
        with self.database.engine.connect() as connection:
            self._authorize(connection,actor)
            manifest=self._manifest(connection)['data']
            return {'project_id':str(self._space_id),'space_id':str(self._space_id),'manifest_version':manifest['version'],
                **schedule_contract(manifest['manifest'],self.clock())}

    def observe_runner(self,actor,data,*,idempotency_key):
        if type(data) is not dict:raise ValueError('invalid_runner_observation')
        allowed=set(SCHEMAS['runner_observation_v1']['properties'])-{'key','project_id','config_version','actor_id','recorded_at'}
        if set(data)!=allowed:raise ValueError('invalid_runner_observation')
        def execute(connection,current):
            if data['status'] in ('reported_installed','reported_execution') and (not data['task_reference'] or not data['evidence_reference']):
                raise ValueError('runner_report_requires_observed_reference')
            if data['run_id']:
                run=self._find(connection,'run_v1',data['run_id'])['data']
                if run['workflow_type']!=data['workflow_type']:raise ValueError('runner_workflow_mismatch')
                if data['status']=='reported_execution' and run['state']!='complete':
                    raise ValueError('runner_report_is_not_completed_c0_work')
            elif data['status']=='reported_execution':raise ValueError('runner_execution_requires_stored_run')
            values={'key':'validated','project_id':str(self._space_id),'config_version':self._manifest(connection)['data']['version'],
                'actor_id':str(current.user_id),'recorded_at':self.clock().isoformat(),**data}
            validate_record(SCHEMAS['runner_observation_v1'],values)
            saved=self._save(connection,current,'runner_observation_v1',uuid4().hex,{k:v for k,v in values.items() if k!='key'})
            # This is a recorded report, never a permission grant or proof that
            # the host installed/authenticated/executed a real scheduled task.
            return receipt('SAVED','runner_observation_recorded',saved)
        return self._mutate(actor,'runner_observation',data,idempotency_key,execute)
