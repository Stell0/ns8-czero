# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json

import pytest

from czero_core.document_units import validate_spec,text_blocks,assemble
from czero_core.extraction import ExtractionError


def row(body,start,end,ordinal):
    locations=[{'kind':'body','index':1,'start':0,'end':len(body)}]
    encoded=json.dumps({'text':body,'locations':locations},sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False)
    return {'ordinal':ordinal,'state':'succeeded','locator':{'kind':'characters','start':start,'end':end},
        'body':body,'locations':locations,'text_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'result_sha256':hashlib.sha256(encoded.encode()).hexdigest()}


def test_character_units_preserve_unicode_whitespace_and_exact_complete_hash():
    body='  café\n\n東京\t\n'
    spec={'characters':len(body),'ranges':[[0,8],[8,len(body)]],'text_sha256':hashlib.sha256(body.encode()).hexdigest()}
    result=assemble([row(body[:8],0,8,1),row(body[8:],8,len(body),2)],'text/plain',spec)
    assert result.text==body and result.locations==[{'kind':'body','index':1,'start':0,'end':len(body)}]


@pytest.mark.parametrize('ranges',[[[True,4]],[[1,4]],[[0,2],[3,4]],[[0,3],[2,4]],[[0,5]],[]])
def test_manifest_coordinates_reject_boolean_gapped_overlapping_or_missing_ranges(ranges):
    with pytest.raises(ValueError): validate_spec('text/plain',{'characters':4,'ranges':ranges,'text_sha256':'a'*64})


def test_fence_width_and_unicode_line_separators_do_not_invent_headings():
    body='# Real\n\n````text\n# Hidden\n```\n## Also hidden\n````\n\n## Last\ntext\u2028# Literal\n'
    _,headings=text_blocks(body,True)
    assert headings==[(0,1),(body.index('## Last'),2)]


def test_corrupt_or_incomplete_results_never_assemble():
    body='abcdef'; spec={'characters':6,'ranges':[[0,3],[3,6]],'text_sha256':hashlib.sha256(body.encode()).hexdigest()}
    rows=[row('abc',0,3,1),row('def',3,6,2)]
    with pytest.raises(ExtractionError): assemble(rows[:1],'text/plain',spec)
    rows[1]['body']='xyz'
    with pytest.raises(ExtractionError): assemble(rows,'text/plain',spec)
