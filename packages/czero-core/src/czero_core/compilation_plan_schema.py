# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Closed publication envelopes. Proposed bodies are transient, never coordinator data."""
from .compilation_schema import record, integer, UUID, HASH, KEY, SOURCE, LEASE

KINDS = ['page','entity','claim','relation']
NULL_UUID = {'anyOf': [UUID, {'type': 'null'}]}
NULL_HASH = {'anyOf': [HASH, {'type': 'null'}]}
PASSAGE = record({'chunk_id': UUID, 'start_offset': integer(0, 1000000),
    'end_offset': integer(1, 1000000), 'quote': {'type': 'string', 'minLength': 1, 'maxLength': 8192}})
BINDING = record({'kind': {'enum': KINDS + ['annotation','link']}, 'id': UUID,
    'revision': integer(1, 2147483646), 'content_id': NULL_UUID,
    'content_hash': NULL_HASH, 'record_hash': HASH})
TARGET_BINDING = record({'operation_index': integer(0, 24), 'kind': {'enum': KINDS},
    'canonical_key': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9_.:/-]{0,127}$'},
    'id': NULL_UUID, 'revision': integer(0, 2147483646), 'content_id': NULL_UUID,
    'content_hash': NULL_HASH, 'record_hash': NULL_HASH, 'managed': {'type': 'boolean'},
    'evidence': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': PASSAGE}})
DEDUP = record({'operation_index': integer(0, 24), 'candidate': BINDING,
    'comparison': {'enum': ['equivalent','distinct','ambiguous']},
    'rationale': {'enum': ['same_concept','different_concept','different_product','different_version','uncertain']}})
PLAN = record({'schema_version': {'type': 'integer', 'const': 1}, 'space_id': UUID,
    'task_id': UUID, 'expected_task_revision': integer(1, 2147483646),
    'policy_revision': integer(1, 2147483646),
    'profile_id': {'enum': ['sourced-navigation-v1','sourced-knowledge-v1']},
    'profile_version': {'type': 'integer', 'const': 1},
    'source_bindings': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': SOURCE},
    'target_bindings': {'type': 'array', 'maxItems': 25, 'items': TARGET_BINDING},
    'dedup_decisions': {'type': 'array', 'maxItems': 64, 'items': DEDUP},
    'classification': {'enum': ['extracted','supported_synthesis','uncertain','contradictory','unsupported']},
    'operations': {'type': 'array', 'maxItems': 25, 'items': record({'operation': {'type': 'string'}, 'arguments': {'type': 'object'}})},
    'deferred': {'type': 'array', 'maxItems': 32, 'items': record({
        'reason': {'enum': ['unsupported_evidence','contradiction','unknown_applicability','duplicate_candidate','unread_source_context']},
        'source_ids': {'type': 'array', 'maxItems': 3, 'uniqueItems': True, 'items': UUID}})},
    'usage_reservation_id': NULL_UUID})
VALIDATE = record({'lease': LEASE, 'expected_revision': integer(1, 2147483646), 'plan': PLAN})
APPROVAL = record({'plan_hash': HASH, 'reference': KEY})
APPLY = record({**VALIDATE['properties'], 'plan_hash': HASH,
    'approval': {'anyOf': [APPROVAL, {'type': 'null'}]}}, ['lease','expected_revision','plan','plan_hash'])
VERIFY = record({'lease': LEASE, 'expected_revision': integer(1, 2147483646),
    'task_id': UUID, 'expected_task_revision': integer(1, 2147483646),
    'policy_revision': integer(1, 2147483646), 'plan_hash': HASH,
    'observations': {'type': 'array', 'minItems': 1, 'maxItems': 25, 'items': BINDING},
    'source_bindings': PLAN['properties']['source_bindings']})
