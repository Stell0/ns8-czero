# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Closed metadata-only maintenance inputs, never prompts or source bodies."""
from .compilation_schema import HASH, UUID, LEASE, SOURCE, integer, record

FENCED = {'lease': LEASE, 'expected_revision': integer(1, 2147483646)}
DISCOVER = record({**FENCED, 'limit': integer(1, 20)})
ASSESS = record({'reviewed_ranges':{'type':'array','maxItems':32,'items':record({
        'start_offset':integer(0,16777216),'end_offset':integer(1,16777216)})},**FENCED, 'task_id': UUID, 'expected_task_revision': integer(1,2147483646),
    'reviewed_source_ids': {'type':'array','items':UUID,'minItems':0,'maxItems':3,'uniqueItems':True},
    'child_task_ids': {'type':'array','items':UUID,'maxItems':19,'uniqueItems':True},
    'status': {'enum':['reviewed','partial']},
    'findings': {'type':'array','maxItems':8,'uniqueItems':True,'items':{'enum':[
        'unread_context','contradiction','uncertain','unavailable_evidence','target_overflow','budget_exhausted']}}},
    [*FENCED,'task_id','expected_task_revision','reviewed_source_ids','child_task_ids','status','findings'])
SEMANTIC_SELECT = record({**FENCED,'refresh_changed':{'type':'boolean'}},list(FENCED))
SEMANTIC_REVIEW = record({**FENCED,'page_id':UUID,'revision':integer(1,2147483646),
    'content_id':UUID,'content_hash':HASH,
    'source_bindings':{'type':'array','items':SOURCE,'maxItems':3},
    'usage_reservation_id':{'anyOf':[UUID,{'type':'null'}]},'status':{'enum':['reviewed','partial','blocked']},
    'child_task_ids':{'type':'array','items':UUID,'maxItems':19,'uniqueItems':True}})
