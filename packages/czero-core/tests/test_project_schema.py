# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from czero_core.project_schema import normalize_manifest, next_occurrence


def manifest(**changes):
    key = str(uuid4())
    return normalize_manifest({'space_id': key, 'project_id': key, 'name': 'Synthetic research',
        'purpose': 'Test reusable projects', 'scope': 'Fabricated records only', **changes})


def test_defaults_are_bounded_inert_and_compatible():
    first = manifest()
    assert normalize_manifest(deepcopy(first)) == first
    assert first['research']['normal_daily_attempts'] == 5
    assert first['research']['urgent_total_daily_attempts'] == 10
    assert first['monitoring']['max_queries_per_topic'] == 5
    assert first['monitoring']['max_sources_per_topic'] == 10
    assert not first['schedule']['enabled']


@pytest.mark.parametrize('changes', [
    {'schema_version': 2}, {'timezone': 'unknown/nowhere'}, {'language': 'English text!'},
    {'monitoring': {'max_queries_per_topic': 0}}, {'schedule': {'daily_local_time': '25:00'}},
    {'research': {'normal_daily_attempts': 11}}, {'research': {'max_children_per_investigation': 4}},
    {'primary_topic_ids': ['same', 'same']}, {'state': {'initialized': True}}, {'unknown': 'field'},
])
def test_invalid_configuration_never_means_unlimited(changes):
    with pytest.raises(ValueError):
        manifest(**changes)


@pytest.mark.parametrize('after, expected', [
    ('2026-03-28T23:00:00+00:00', '2026-03-29T01:30:00+00:00'),
    ('2026-10-24T23:00:00+00:00', '2026-10-25T00:30:00+00:00'),
    ('2026-10-25T00:45:00+00:00', '2026-10-26T01:30:00+00:00'),
])
def test_rome_gap_and_fold_have_one_daily_occurrence(after, expected):
    config = manifest(timezone='Europe/Rome', schedule={'daily_local_time': '02:30'})
    assert next_occurrence(config, 'daily', datetime.fromisoformat(after)).isoformat() == expected


def test_weekly_expiry_is_strictly_future():
    config = manifest(timezone='Europe/Rome')
    now = datetime(2026, 10, 25, 7, tzinfo=timezone.utc) # Sunday 08:00 after fold
    assert next_occurrence(config, 'weekly', now).isoformat() == '2026-11-01T07:00:00+00:00'


def test_unrelated_predecessor_type_collision_is_not_managed():
    from czero_core.objects import _project_type
    from czero_core.project_schema import PREFIX, SCHEMAS
    assert _project_type(PREFIX+'manifest_v1')
    assert not _project_type(PREFIX+'manifest_v1', {'schema':{'type':'object'},'unique_fields':[]})
    assert _project_type(PREFIX+'manifest_v1', {'schema':SCHEMAS['manifest_v1'],'unique_fields':['key']})
    assert not _project_type('c0_project_custom')
