# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Closed, bounded coordination data. No model, prompt or content mutation schema."""
from copy import deepcopy
import hashlib
import json
import re
from uuid import UUID as UUIDValue
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema import Draft202012Validator, FormatChecker

from .object_schema import bounded_json

PROFILE = 'sourced-navigation-v1'
HASH = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
UUID = {'type': 'string', 'format': 'uuid', 'minLength': 36, 'maxLength': 36}
KEY = {'type': 'string', 'pattern': '^[A-Za-z0-9_.:-]{1,128}$'}
REASONS = ['missing_concept', 'incomplete_page', 'stale_support', 'distributed_evidence',
    'missing_relationship', 'terminology_gap', 'contradiction', 'applicability_gap',
    'missing_link', 'source_changed', 'initial_compilation']
ORIGINS = ['manual', 'bootstrap', 'retrieval', 'daily', 'weekly']
STATES = ['queued', 'leased', 'planned', 'needs_review', 'deferred', 'conflict', 'failed',
    'uncertain', 'superseded', 'no_change', 'applied_pending_verify', 'succeeded']
ACTIVE = ('queued', 'leased', 'planned', 'needs_review', 'deferred', 'uncertain')
ERRORS = ['external_failed', 'unsupported_evidence', 'source_unavailable', 'source_incomplete',
    'concurrent_edit', 'retry_exhausted', 'budget_exhausted', 'model_usage_unknown']


def record(properties, required=None):
    return {'type': 'object', 'properties': properties,
        'required': list(properties) if required is None else required, 'additionalProperties': False}


def integer(low, high):
    return {'type': 'integer', 'minimum': low, 'maximum': high}


DEFAULTS = {'enabled': False, 'retrieval_feedback': False, 'publication_mode': 'queue_only',
    'timezone': 'UTC', 'profile_id': PROFILE, 'profile_version': 1,
    'allowed_target_kinds': ['page', 'annotation'], 'contradiction_handling': 'review',
    'uncertainty_handling': 'review', 'daily_documents': 10, 'daily_pages': 10,
    'weekly_documents': 20, 'weekly_pages': 10, 'max_tasks_per_run': 20,
    'max_outstanding_tasks': 100, 'max_attempts': 3, 'concurrency': 1,
    'lease_seconds': 300, 'run_seconds': 900, 'request_seconds': 60,
    'daily_model_requests': 20, 'daily_model_tokens': 100000,
    'weekly_model_requests': 100, 'weekly_model_tokens': 500000,
    'retrieval_model_requests': 1, 'retrieval_model_tokens': 4000}
POLICY = record({
    **{key: {'type': 'boolean'} for key in ('enabled', 'retrieval_feedback')},
    'publication_mode': {'enum': ['queue_only', 'automatic_supported']},
    'timezone': {'type': 'string', 'minLength': 1, 'maxLength': 100},
    'profile_id': {'const': PROFILE}, 'profile_version': {'type': 'integer', 'const': 1},
    'allowed_target_kinds': {'type': 'array', 'minItems': 1, 'maxItems': 2,
        'items': {'enum': ['page', 'annotation']}, 'uniqueItems': True},
    'contradiction_handling': {'const': 'review'}, 'uncertainty_handling': {'const': 'review'},
    **{key: integer(1, 1000) for key in ('daily_documents', 'daily_pages', 'weekly_documents',
        'weekly_pages', 'max_outstanding_tasks', 'daily_model_requests', 'weekly_model_requests')},
    'max_tasks_per_run': integer(1, 20), 'max_attempts': integer(1, 5), 'concurrency': integer(1, 4),
    'lease_seconds': integer(60, 900), 'run_seconds': integer(60, 900), 'request_seconds': integer(1, 60),
    'daily_model_tokens': integer(1, 10000000), 'weekly_model_tokens': integer(1, 100000000),
    'retrieval_model_requests': integer(0, 1), 'retrieval_model_tokens': integer(1, 4000)})
CHUNK = record({'chunk_id': UUID, 'source_id': UUID, 'version_id': UUID, 'document_id': UUID,
    'content_hash': HASH, 'source_hash': HASH, 'start_offset': integer(0, 1000000),
    'end_offset': integer(1, 1000000)})
SOURCE = record({'logical_document_id': UUID, 'revision_id': UUID, 'content_hash': HASH,
    'text_hash': HASH, 'metadata_hash': HASH, 'parts_hash': HASH,
    'chunks': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': CHUNK}})
SOURCE_SELECTION = record({'logical_document_id': UUID, 'revision_id': UUID,
    'chunk_ids': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': UUID, 'uniqueItems': True}})
TARGET = record({'kind': {'const': 'page'}, 'id': UUID, 'revision': integer(1, 2147483646),
    'content_id': UUID, 'content_hash': HASH})
LEASE = record({'run_id': UUID, 'lease_owner': KEY, 'fencing_generation': integer(1, 9223372036854775806)})
PROPOSAL = record({'policy_revision': integer(0, 2147483646), 'origin': {'enum': ORIGINS},
    'reason': {'enum': REASONS}, 'topic_key': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9_.:/-]{0,95}$'},
    'source_bindings': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': SOURCE},
    'target': {'anyOf': [TARGET, {'type': 'null'}]},
    'source_label': {'type': 'string', 'maxLength': 160}},
    ['policy_revision', 'origin', 'reason', 'topic_key', 'source_bindings'])
CLAIM = record({'kind': {'enum': ORIGINS}, 'cycle_key': KEY, 'lease_owner': KEY,
    'policy_revision': integer(0, 2147483646), 'task_limit': integer(1, 20)},
    ['kind', 'cycle_key', 'lease_owner', 'policy_revision'])
CHECKPOINT = record({'lease': LEASE, 'expected_revision': integer(1, 2147483646),
    'action': {'enum': ['planned', 'no_change', 'defer', 'fail', 'reserve_model', 'start_model',
        'return_model', 'fail_model', 'uncertain_model', 'reconcile_returned', 'reconcile_failed', 'finish', 'partial']},
    'task_id': UUID, 'expected_task_revision': integer(1, 2147483646), 'plan_hash': HASH,
    'error_code': {'enum': ERRORS}, 'request_id': UUID, 'reserved_tokens': integer(1, 10000000),
    'observed_tokens': {'anyOf': [integer(0, 100000000), {'type': 'null'}]},
    'external_reference_hash': HASH}, ['lease', 'expected_revision', 'action'])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _canonical(schema, value):
    if value is None:
        return None
    if 'anyOf' in schema:
        schema = next((s for s in schema['anyOf'] if s.get('type') != 'null'), schema)
    if schema.get('type') == 'integer':
        return int(value)  # JSON Schema also accepts integral JSON numbers such as 1.0.
    if schema.get('format') == 'uuid':
        return str(UUIDValue(value))
    if isinstance(value, dict):
        return {k: _canonical(schema.get('properties', {}).get(k, {}), v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonical(schema.get('items', {}), v) for v in value]
    return value


def checked(schema, value, *, maximum=16384):
    value = bounded_json(value, maximum=maximum)
    # These schemas are trusted constants, never supplied by an API caller.
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value):
        raise ValueError('invalid_compilation_request')
    return _canonical(schema, value)


def policy(value):
    result = checked(POLICY, value)
    try:
        ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('invalid_compilation_policy') from None
    if result['retrieval_feedback'] and not result['enabled']:
        raise ValueError('invalid_compilation_policy')
    return result


def defaults():
    return deepcopy(DEFAULTS)


def key(value):
    if not isinstance(value, str) or re.fullmatch(KEY['pattern'], value) is None:
        raise ValueError('invalid_compilation_identity')
    return value
