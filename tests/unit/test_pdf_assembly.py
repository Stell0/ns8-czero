# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Fast assembly guards use synthetic results, without workers or a database."""
import hashlib
import json

import pytest

from czero_core.extraction import ExtractionError
from czero_core.pdf_units import assemble_pdf


def unit(page,body):
    locations=[{'kind':'page','index':page,'start':0,'end':len(body)}] if body else []
    payload=json.dumps({'text':body,'locations':locations},sort_keys=True,
        separators=(',', ':'),ensure_ascii=False,allow_nan=False)
    return {'ordinal':page,'state':'succeeded','locator':{'kind':'page','first':page,'last':page},
        'body':body,'locations':locations,'result_sha256':hashlib.sha256(payload.encode()).hexdigest(),
        'text_sha256':hashlib.sha256(body.encode()).hexdigest()}


def test_unicode_offsets_and_blank_page_gaps_are_canonical():
    document=assemble_pdf([unit(1,'café 東京'),unit(2,''),unit(3,'Next\n')],3)
    assert document.text=='café 東京\n\nNext\n'
    assert document.locations==[{'kind':'page','index':1,'start':0,'end':7},
        {'kind':'page','index':3,'start':9,'end':14}]


@pytest.mark.parametrize('rows,count', [([],1),([unit(1,'text')],True),
    ([unit(1,'text')],201),([unit(2,'text')],1),([unit(1,'')],1),
    ([unit(1,'a'),unit(1,'b')],2),([unit(1,'a')],2)])
def test_incomplete_invalid_or_blank_assembly_is_never_evidence(rows,count):
    with pytest.raises((ExtractionError,ValueError)): assemble_pdf(rows,count)


def test_aggregate_limits_include_canonical_separators():
    rows=[unit(1,'x'*500000),unit(2,'y'*500000)]
    with pytest.raises(ExtractionError,match='too_large'): assemble_pdf(rows,2)


@pytest.mark.parametrize('field,value', [('body','changed'),('result_sha256','0'*64),
    ('text_sha256','0'*64),('locations',[]),('ordinal',True),
    ('locator',{'kind':'page','first':True,'last':1})])
def test_tampered_or_untyped_result_is_rejected(field,value):
    row=unit(1,'Original'); row[field]=value
    with pytest.raises(ExtractionError): assemble_pdf([row],1)
