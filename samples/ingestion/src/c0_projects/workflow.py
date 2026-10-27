# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fenced publication coordination over the existing authenticated C0 client."""
import time
from uuid import uuid4
from c0_ingest.errors import C0Error
from .model import sha

COMMITS={'project_source_status_set','project_source_snapshot_set','project_connector_status_set'}


class SourceWorkflow:
    def __init__(self,client,connector_id,scan_hash):
        self.client=client;self.connector_id=connector_id;self.owner=uuid4().hex;self.version=client.call('project_get')['data']['version']
        self.cycle=sha(['source-sync',connector_id,scan_hash]);self.renewed=0
        result=self.renew()
        self.completed=result['outcome']=='workflow_already_complete'
        self.phase=self.run['current_phase']
        if not self.completed and self.phase=='collect':
            self.checkpoint('SAVED','Validated frozen local scan; external content is inert data.')

    def __getattr__(self,name):return getattr(self.client,name)

    def renew(self):
        result=self.client.call('project_run_claim',data={'workflow_type':'source_sync','lease_owner':self.owner,
            'config_version':self.version,'cycle_key':self.cycle,'connector_id':self.connector_id,'lease_seconds':900,'idempotency_key':uuid4().hex})
        if result['status']=='BLOCKED':raise C0Error('source_workflow_retry_exhausted')
        self.run=result['records'][0]['data']
        self.lease={key:self.run[key] for key in ('run_id','lease_owner','fencing_generation')}
        self.renewed=time.monotonic()
        return result

    def call(self,name,**arguments):
        if not self.completed and time.monotonic()-self.renewed>=60:self.renew()
        if name in COMMITS:
            if self.completed:raise C0Error('completed_source_cycle_is_read_only')
            arguments={**arguments,'data':{**arguments['data'],'lease':self.lease}}
        return self.client.call(name,**arguments)

    def checkpoint(self,status,summary,references=None):
        if time.monotonic()-self.renewed>=60:self.renew()
        result=self.client.call('project_run_checkpoint',data={'lease':self.lease,'phase':self.phase,'status':status,
            'summary':summary,'references':references or [],'idempotency_key':uuid4().hex})
        self.run=next(row['data'] for row in result['records'] if row['type_name']=='c0_project_run_v1')
        self.phase=self.run['current_phase'];self.completed=self.run['state']=='complete'
        return result

    def finish(self,coverage,complete):
        references=[coverage['id']] if coverage else []
        if self.phase=='publish':
            result=self.checkpoint('SAVED' if complete else 'PARTIAL',
                'Verified publication of the configured selection.' if complete else 'Collection or extraction is incomplete; resume the frozen scan.',references)
            if not complete:return result
        return self.checkpoint('SAVED' if complete else 'PARTIAL','Read back source snapshot and connector coverage receipts.',references)
