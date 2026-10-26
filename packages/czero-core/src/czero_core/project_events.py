# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded local-calendar observations; admission still uses the common queue."""
from calendar import monthrange
from datetime import date,datetime,time,timedelta,timezone
from uuid import UUID
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from sqlalchemy import text
from .object_schema import bounded_json,validate_record
from .project_schema import EVENT_INPUT,PREFIX,identifier,timestamp
from .project_workflows import data_of,digest


def event_day(event):
    value=event['start_time'];precision=event['date_precision']
    if precision=='unknown':
        if value:raise ValueError('unknown_event_date_must_be_empty')
        return None
    if precision=='time':return timestamp(value).astimezone(ZoneInfo(event['timezone'])).date()
    if precision=='month':value+='-01'
    if precision=='year':value+='-01-01'
    result=date.fromisoformat(value)
    if result.isoformat()!=value:raise ValueError('invalid_event_date')
    return result


def latest_event_occurrence(event,today):
    """One latest missed equivalent refresh, without enumerating its whole past."""
    if event['date_precision'] not in ('date','time'):return None
    base=event_day(event);end=today+timedelta(days=event['lead_days']);recurrence=event['recurrence']
    if recurrence['until']:end=min(end,date.fromisoformat(recurrence['until']))
    if base>end:return None
    frequency=recurrence['frequency'];interval=recurrence['interval']
    if frequency=='none':return base
    if frequency in ('daily','weekly'):
        step=interval*(7 if frequency=='weekly' else 1)
        return base+timedelta(days=((end-base).days//step)*step)
    months=(end.year-base.year)*12+end.month-base.month;n=months//interval
    def month(index):
        year,zero=divmod(base.year*12+base.month-1+index*interval,12)
        return date(year,zero+1,min(base.day,monthrange(year,zero+1)[1]))
    result=month(n)
    return month(n-1) if result>end and n else result


def event_candidate_identity(event_id,day):return 'calendar-'+digest([event_id,day])


class ProjectEvents:
    def set_event(self,actor,data,*,expected_revision=0,idempotency_key):
        data=bounded_json(data)
        if type(data) is not dict:raise ValueError('invalid_event_definition')
        defaults={'kind':'event','description':'','end_time':'','date_precision':'date','status':'tentative',
            'refresh_question':'','priority':20,'expansion_priority':20,'parent_ids':[],'related_pages':[],
            'lead_days':0,'recurrence':{'frequency':'none','interval':1,'until':''}}
        defaults['expansion_priority']=data.get('priority',20)
        data=validate_record(EVENT_INPUT,{**defaults,**data})
        identifier(data['event_id']);identifier(data['topic_id'])
        try:ZoneInfo(data['timezone'])
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('invalid_event_timezone') from None
        start=event_day(data)
        if data['end_time']:
            ending={**data,'start_time':data['end_time']};end=event_day(ending)
            if start is None or end<start:raise ValueError('invalid_event_end')
            if data['date_precision']=='time' and timestamp(data['end_time'])<timestamp(data['start_time']):raise ValueError('invalid_event_end')
        if data['kind']=='research_refresh' and (data['date_precision'] not in ('date','time') or not data['refresh_question'].strip()):
            raise ValueError('refresh_requires_known_date_and_question')
        recurrence=data['recurrence']
        if recurrence['frequency']!='none' and data['date_precision'] not in ('date','time'):
            raise ValueError('partial_date_recurrence_unsupported')
        if recurrence['until'] and (start is None or date.fromisoformat(recurrence['until'])<start):raise ValueError('invalid_event_until')
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('invalid_revision')
        def execute(connection,current):
            self._find(connection,'topic_v1',data['topic_id']);self._references(connection,data['related_pages'])
            previous=self._find(connection,'event_v1',data['event_id'],required=False)
            if (previous['revision'] if previous else 0)!=expected_revision:raise self.conflict()
            if previous and (data['expansion_priority']!=previous['data']['expansion_priority'] or data['parent_ids']!=previous['data']['parent_ids']):
                raise ValueError('event_causal_depth_is_immutable')
            if data['parent_ids']:
                parents=[self._find(connection,'queue_v1',parent)['data'] for parent in data['parent_ids']]
                expansion=max(parent['expansion_priority'] for parent in parents)+self._manifest(connection)['data']['manifest']['research']['child_priority_increment']
                if data['expansion_priority']!=expansion or expansion>100:raise ValueError('invalid_event_causal_depth')
            values={**data,'project_id':str(self._space_id),'last_checked_at':self.clock().isoformat()}
            saved=self._save(connection,current,'event_v1',data['event_id'],values,previous=previous)
            self._save(connection,current,'event_history_v1',data['event_id']+':'+str(saved['revision']),{
                'event_id':data['event_id'],'version':saved['revision'],'definition':data,
                'actor_id':str(current.user_id),'recorded_at':self.clock().isoformat()})
            return saved
        return self._mutate(actor,'event',{'data':data,'expected_revision':expected_revision},idempotency_key,execute)

    def _calendar_context(self,connection,candidate):
        event=self._find(connection,'event_v1',candidate['origin_reference'])['data']
        if event['kind']!='research_refresh' or event['status'] not in ('scheduled','tentative'):raise ValueError('event_not_executable')
        today=self.clock().astimezone(ZoneInfo(event['timezone'])).date();day=latest_event_occurrence(event,today)
        if day is None:raise ValueError('event_not_due')
        local_date=day.isoformat();identity=event_candidate_identity(event['event_id'],local_date)
        if (candidate['stable_id'],candidate['topic_id'],candidate['question'],candidate['priority'],candidate['parent_ids'],
                candidate['novelty_key'],candidate['time_window'])!=(identity,event['topic_id'],event['refresh_question'],
                event['priority'],event['parent_ids'],identity,local_date):raise ValueError('calendar_candidate_binding_mismatch')
        if event['date_precision']=='time':
            original=timestamp(event['start_time']).astimezone(ZoneInfo(event['timezone']))
            due=datetime.combine(day,original.timetz().replace(tzinfo=None,fold=0),ZoneInfo(event['timezone'])).astimezone(timezone.utc)
        else:due=datetime.combine(day,time(23,59,59),ZoneInfo(event['timezone'])).astimezone(timezone.utc)
        if not candidate['due_at'] or timestamp(candidate['due_at'])!=due:raise ValueError('calendar_deadline_mismatch')
        earlier=connection.execute(text('''SELECT data FROM c0_objects WHERE space_id=:space AND type_name=:type
            AND data->>'event_id'=:event AND data->>'queue_id'<>'' ORDER BY data->>'local_date',id LIMIT 1'''),
            {'space':self._space_id,'type':PREFIX+'event_occurrence_v1','event':event['event_id']}).scalar_one_or_none()
        return {'event':event,'local_date':local_date,'lineage_root_id':earlier['lineage_root_id'] if earlier else identity}

    def _calendar_admitted(self,connection,current,candidate,result):
        admission=next(row for row in result['records'] if row['type_name']==PREFIX+'admission_v1')
        queued=next((row for row in result['records'] if row['type_name']==PREFIX+'queue_v1'),None)
        identity=candidate['novelty_key'];previous=self._find(connection,'event_occurrence_v1',identity,required=False)
        self._save(connection,current,'event_occurrence_v1',identity,{
            'event_id':candidate['origin_reference'],'local_date':candidate['time_window'],
            'queue_id':queued['data']['stable_id'] if queued else '',
            'lineage_root_id':queued['data']['lineage_root_id'] if queued else '',
            'admission_reference':admission['id'],'disposition':admission['data']['disposition'],
            'recorded_at':self.clock().isoformat()},previous=previous)
