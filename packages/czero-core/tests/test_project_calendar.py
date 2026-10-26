# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime,timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytest
from czero_core.project_schema import normalize_manifest,next_occurrence,occurrence_on_day
from czero_core.project_schedules import schedule_contract


def config(zone):
    identity=str(uuid4())
    return normalize_manifest({'project_id':identity,'space_id':identity,'name':'Synthetic calendar',
        'purpose':'Calendar policy','scope':'Synthetic only','timezone':zone,
        'schedule':{'daily_local_time':'02:30','weekly_local_time':'02:30'}})


def test_rome_gap_fold_and_single_daily_occurrence():
    manifest=config('Europe/Rome')
    assert occurrence_on_day(manifest,'daily','2026-03-29')==datetime(2026,3,29,1,30,tzinfo=timezone.utc)
    assert occurrence_on_day(manifest,'daily','2026-10-25')==datetime(2026,10,25,0,30,tzinfo=timezone.utc)
    after=datetime(2026,10,25,1,tzinfo=timezone.utc)
    assert next_occurrence(manifest,'daily',after).astimezone(ZoneInfo('Europe/Rome')).date().isoformat()=='2026-10-26'
    assert schedule_contract(manifest,after)['occurrences']['daily']['local_cycle_date']=='2026-10-25'


@pytest.mark.parametrize('zone',['Pacific/Auckland','America/New_York','Asia/Kolkata','Australia/Lord_Howe','Europe/Rome'])
def test_iana_calendar_occurrences_have_stable_local_cycle_identity(zone):
    manifest=config(zone);now=datetime(2026,10,26,9,tzinfo=timezone.utc)
    result=schedule_contract(manifest,now)
    for workflow in ('daily','weekly'):
        entry=result['occurrences'][workflow]
        due=datetime.fromisoformat(entry['latest_due']);future=datetime.fromisoformat(entry['next_occurrence'])
        assert due<=now<future
        assert due.astimezone(ZoneInfo(zone)).date().isoformat()==entry['local_cycle_date']
    assert result['installed_by_c0'] is False
