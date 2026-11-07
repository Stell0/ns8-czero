# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from copy import deepcopy
import pytest
from czero_core.compilation_content import passage, record_binding


def test_exact_passage_offsets_and_unicode_hash_are_original_bound():
    body = 'Café\n東京 procedure.'
    citation = {'chunk_id':'00000000-0000-0000-0000-000000000001','body':body,
        'content_hash':hashlib.sha256(body.encode()).hexdigest(),'start_offset':100,'end_offset':100+len(body)}
    observed = passage(citation,'東京')
    assert observed['start_offset'] == 105 and observed['end_offset'] == 107
    with pytest.raises(ValueError): passage(citation,'invented')
    with pytest.raises(ValueError): passage(citation,'東京',start_offset=104,end_offset=106)
    with pytest.raises(ValueError): passage({**citation,'content_hash':'0'*64},'東京')


def test_claim_readback_normalizes_equivalent_api_datetime_rendering():
    value = {'id':'c','entity_id':'e','page_id':None,'predicate':'port','value':{'port':7443},
        'metadata':{},'revision':1,'deleted':False,'valid_from':'2026-01-01T00:00:00+00:00',
        'valid_to':None,'evidence_stale':False,'evidence':[{'chunk_id':'a'}]}
    equivalent = {**value,'valid_from':'2026-01-01T00:00:00Z'}
    assert record_binding('claim',equivalent) == record_binding('claim',value)
