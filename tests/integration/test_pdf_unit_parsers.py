# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Real isolated PDF parsers; deliberately outside database-free fast feedback."""
import hashlib
import json
from pathlib import Path

import pytest

from czero_core.extraction import ExtractionError, extract_isolated
from czero_core.pdf_units import inventory_isolated, extract_page_isolated, assemble_pdf

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/evidence/pipeline'


def result(page, evidence):
    encoded = json.dumps({'text':evidence.text,'locations':evidence.locations},
        sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False)
    return {'ordinal':page,'state':'succeeded','locator':{'kind':'page','first':page,'last':page},
        'body':evidence.text,'locations':evidence.locations,
        'result_sha256':hashlib.sha256(encoded.encode()).hexdigest(),
        'text_sha256':evidence.text_hash}


@pytest.mark.parametrize('name,pages', [('readable-100.pdf',100),('blank-pages.pdf',5)])
def test_original_page_units_assemble_to_identical_body_locations_and_hash(name,pages):
    path = FIXTURES / name
    assert inventory_isolated(path) == pages
    values = [result(page,extract_page_isolated(path,page)) for page in range(1,pages+1)]
    combined = assemble_pdf(values,pages)
    baseline = extract_isolated(path,'application/pdf')
    assert combined == baseline and combined.text_hash == baseline.text_hash


def test_scan_is_an_explicit_page_failure_and_does_not_hide_readable_sibling():
    path = FIXTURES / 'mixed-scan.pdf'
    assert inventory_isolated(path) == 2
    assert extract_page_isolated(path,1).text.strip()
    with pytest.raises(ExtractionError,match='unsupported_scan'):
        extract_page_isolated(path,2)


def test_all_blank_is_not_a_published_document():
    path = FIXTURES / 'all-blank.pdf'
    values = [result(page,extract_page_isolated(path,page)) for page in (1,2)]
    assert all(row['body']=='' and row['locations']==[] for row in values)
    with pytest.raises(ExtractionError,match='no_text'): assemble_pdf(values,2)


@pytest.mark.parametrize('change', ['missing','duplicate','order','body','hash','location','locator','state'])
def test_assembly_fails_closed_on_missing_duplicate_or_corrupt_unit(change):
    path = FIXTURES / 'readable-100.pdf'
    rows = [result(page,extract_page_isolated(path,page)) for page in (1,2)]
    if change=='missing': rows.pop()
    elif change=='duplicate': rows[1]=rows[0]
    elif change=='order': rows.reverse()
    elif change=='body': rows[0]['body']+=' altered'
    elif change=='hash': rows[0]['text_sha256']='0'*64
    elif change=='location': rows[0]['locations'][0]['end']+=1
    elif change=='locator': rows[0]['locator']['first']=2
    else: rows[0]['state']='queued'
    with pytest.raises(ExtractionError): assemble_pdf(rows,2)


@pytest.mark.parametrize('page', [True,0,-1,201,'1'])
def test_page_selection_is_bounded_and_strict(page):
    with pytest.raises((ValueError,ExtractionError)):
        extract_page_isolated(FIXTURES/'readable-100.pdf',page)


def test_vector_only_and_inline_image_empty_pages_fail_closed(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    for content in (b'0 0 40 40 re f',b'BI /W 1 /H 1 /CS /RGB /BPC 8 ID \xff\x00\x00 EI'):
        writer=PdfWriter(); page=writer.add_blank_page(width=100,height=100)
        stream=DecodedStreamObject(); stream.set_data(content)
        page[NameObject('/Contents')]=writer._add_object(stream)
        path=tmp_path/'graphical.pdf'
        with path.open('wb') as target: writer.write(target)
        with pytest.raises(ExtractionError,match='unsupported_scan'):
            extract_page_isolated(path,1)
