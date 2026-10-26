# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Small versioned research-project contracts over C0's existing typed records."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .object_schema import bounded_json, schema_validator, validate_record

PREFIX = 'c0_project_'
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def string(maximum=128, *, minimum=1, values=None):
    result = {'type': 'string', 'minLength': minimum, 'maxLength': maximum}
    if values is not None:
        result['enum'] = values
    return result


def integer(minimum, maximum):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}


def array(item=None, maximum=100):
    return {'type': 'array', 'items': item or string(), 'maxItems': maximum}


def record(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


RESEARCH = record(normal_daily_attempts=integer(1, 50), urgent_total_daily_attempts=integer(1, 100),
    urgent_priority={'type': 'integer', 'const': 0}, child_priority_increment=integer(1, 100),
    max_children_per_investigation=integer(1, 3), max_attempts=integer(1, 10),
    max_active_items=integer(1, 1000), max_new_roots_per_day=integer(1, 50))
MONITORING = record(enabled={'type': 'boolean'}, mandatory_primary_topic_refresh={'type': 'boolean', 'const': True},
    max_queries_per_topic=integer(1, 50), max_sources_per_topic=integer(1, 100), overlap_hours=integer(0, 168))
SCHEDULE = record(daily_local_time=string(5), weekly_day=string(values=DAYS), weekly_local_time=string(5),
    execution_provider=string(values=['external_agent']), enabled={'type': 'boolean'})
MANIFEST = record(schema_version={'type': 'integer', 'const': 1}, project_id=string(36), space_id=string(36),
    name=string(128), description=string(2048, minimum=0), language=string(35), timezone=string(100),
    purpose=string(4096), scope=string(4096), exclusions=array(string(512)), primary_topic_ids=array(),
    research=RESEARCH, monitoring=MONITORING, schedule=SCHEDULE,
    reporting=record(upcoming_days=integer(1, 90), quiet_day_report={'type': 'boolean'}),
    maintenance=record(semantic_pages_per_week=integer(1, 100), max_inventory=integer(1, 10000)),
    connector_ids=array(), state=record(initialized={'type': 'boolean'},
        migration_status=string(values=['not_started', 'prepared', 'imported'])))
TOPIC = record(key=string(128), schema_version={'type': 'integer', 'const': 1}, topic_id=string(), label=string(256),
    classification=string(values=['user', 'adjacent', 'peripheral']),
    lifecycle=string(values=['active', 'provisional', 'archived', 'retired']), aliases=array(string(256)),
    parent_ids=array(maximum=8), anchor_ids=array(maximum=8), originating_question=string(2048, minimum=0),
    direct_contribution=string(2048, minimum=0), assessment_ref=string(512, minimum=0),
    authorization_ref=string(512, minimum=0), authorized_by=string(36, minimum=0),
    created_at=string(40), expires_at=string(40, minimum=0))
SCHEMAS = {
    'manifest_v1': record(key=string(128), version=integer(1, 2147483647), manifest=MANIFEST),
    'config_v1': record(key=string(128), version=integer(1, 2147483647), manifest=MANIFEST,
        actor_id=string(36), authorization_ref=string(512), recorded_at=string(40)),
    'topic_v1': TOPIC,
}
SCHEMAS = {key: schema_validator(value).schema for key, value in SCHEMAS.items()}
DEFAULTS = {
    'schema_version': 1, 'description': '', 'language': 'en', 'timezone': 'UTC', 'exclusions': [],
    'primary_topic_ids': [], 'connector_ids': [],
    'research': {'normal_daily_attempts': 5, 'urgent_total_daily_attempts': 10, 'urgent_priority': 0,
        'child_priority_increment': 20, 'max_children_per_investigation': 3, 'max_attempts': 3,
        'max_active_items': 50, 'max_new_roots_per_day': 5},
    'monitoring': {'enabled': True, 'mandatory_primary_topic_refresh': True,
        'max_queries_per_topic': 5, 'max_sources_per_topic': 10, 'overlap_hours': 12},
    'schedule': {'daily_local_time': '06:00', 'weekly_day': 'sunday', 'weekly_local_time': '08:00',
        'execution_provider': 'external_agent', 'enabled': False},
    'reporting': {'upcoming_days': 7, 'quiet_day_report': True},
    'maintenance': {'semantic_pages_per_week': 30, 'max_inventory': 1000},
    'state': {'initialized': False, 'migration_status': 'not_started'},
}


def identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('invalid_project_identifier')
    return value


def timestamp(value):
    if type(value) is not str:
        raise ValueError('invalid_project_time')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise ValueError('invalid_project_time') from None


def normalize_manifest(value):
    """Compatible v1 additions only; unknown/future versions fail closed."""
    value = bounded_json(value)
    result = deepcopy(DEFAULTS)
    for key, item in value.items():
        if key in result and type(result[key]) is dict and type(item) is dict:
            result[key].update(item)
        else:
            result[key] = item
    result = validate_record(MANIFEST, result)
    if str(UUID(result['space_id'])) != result['space_id'] or str(UUID(result['project_id'])) != result['project_id']:
        raise ValueError('invalid_project_identity')
    if result['project_id'] != result['space_id']:
        raise ValueError('project_identity_must_match_space')
    try:
        ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('invalid_project_timezone') from None
    if not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*', result['language']):
        raise ValueError('invalid_project_language')
    for field in ('daily_local_time', 'weekly_local_time'):
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', result['schedule'][field]):
            raise ValueError('invalid_project_schedule')
    if result['research']['urgent_total_daily_attempts'] < result['research']['normal_daily_attempts']:
        raise ValueError('invalid_project_budgets')
    for field in ('primary_topic_ids', 'connector_ids'):
        values = result[field]
        if len(values) != len(set(values)):
            raise ValueError('duplicate_project_identifier')
        for item in values:
            identifier(item)
    if result['state']['initialized'] and (not result['primary_topic_ids'] or not result['monitoring']['enabled']):
        raise ValueError('active_project_requires_monitoring')
    return result


def next_occurrence(manifest, workflow, after):
    """Strictly future; gaps move forward by the gap, folds choose first occurrence."""
    if workflow not in ('daily', 'weekly') or after.tzinfo is None:
        raise ValueError('invalid_project_schedule')
    zone = ZoneInfo(manifest['timezone'])
    local = after.astimezone(zone)
    hour, minute = map(int, manifest['schedule'][workflow + '_local_time'].split(':'))
    for offset in range(9):
        day = local.date() + timedelta(days=offset)
        if workflow == 'weekly' and day.weekday() != DAYS.index(manifest['schedule']['weekly_day']):
            continue
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone, fold=0).astimezone(timezone.utc)
        if candidate > after.astimezone(timezone.utc):
            return candidate
    raise ValueError('invalid_project_schedule')
