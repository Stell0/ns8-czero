# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Shared PDF limits and Drive text-layer behavior with synthetic originals."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
import pytest

from czero_core.drive_pdf import prepare_pdf
from czero_core.extraction import (
    ExtractionError, MAX_PDF_BYTES, MAX_PDF_PAGES, MAX_UPLOAD, extract_isolated, upload_limit,
)
from czero_core.extraction_queue import _profile
from czero_core.pdf_units import extract_page_isolated, inventory_isolated


FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/evidence/pipeline'


def original(page_count, *, image_only=False, encrypted=False):
    template = PdfReader(FIXTURES / 'mixed-scan.pdf')
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_page(template.pages[1 if image_only else 0])
    if encrypted:
        writer.encrypt('fixture-password')
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


def test_mixed_pdf_retains_text_page_numbers_and_explains_textless_pages():
    raw = (FIXTURES / 'mixed-scan.pdf').read_bytes()
    document, segments = prepare_pdf(raw)
    assert document.text.strip()
    assert document.textless_pages == (2,)
    assert [location['index'] for location in document.locations] == [1]
    assert segments[0]['text'] == document.text
    assert segments[0]['locations'] == document.locations
    with pytest.raises(ExtractionError, match='unsupported_scan'):
        extract_isolated(FIXTURES / 'mixed-scan.pdf', 'application/pdf')


@pytest.mark.parametrize('make,error', [
    (lambda: b'%PDF-truncated', 'invalid_pdf'),
    (lambda: original(1, encrypted=True), 'encrypted_pdf'),
    (lambda: original(1, image_only=True), 'unsupported_scan'),
])
def test_unreadable_files_do_not_produce_partial_text(make, error):
    with pytest.raises(ExtractionError, match=error):
        prepare_pdf(make())


def test_2000_pages_are_citable_through_drive_direct_and_staged_parsers(tmp_path):
    raw = original(2000)
    path = tmp_path / 'large.pdf'
    path.write_bytes(raw)
    assert MAX_PDF_PAGES == inventory_isolated(path) == 2000
    assert _profile('pdf-page-v1', 2000)['pages'] == 2000
    document, segments = prepare_pdf(raw)
    assert not document.textless_pages
    assert [loc['index'] for loc in document.locations] == list(range(1, 2001))
    assert segments[-1]['locations'][-1]['index'] == 2000
    baseline = extract_isolated(path, 'application/pdf')
    assert baseline.text_hash == document.text_hash
    assert baseline.locations == document.locations
    last = document.locations[-1]
    assert extract_page_isolated(path, 2000).text == document.text[last['start']:last['end']]


def test_2001_pages_fail_before_extraction_in_all_paths(tmp_path):
    path = tmp_path / 'limit.pdf'
    path.write_bytes(original(2001))
    with pytest.raises(ExtractionError, match='pdf_too_many_pages'):
        prepare_pdf(path.read_bytes())
    for operation in (lambda: inventory_isolated(path), lambda: extract_isolated(path, 'application/pdf')):
        with pytest.raises(ExtractionError, match='too_large'):
            operation()
    with pytest.raises(ValueError, match='invalid_manifest'):
        _profile('pdf-page-v1', 2001)


def test_100_mib_pdf_byte_limit_is_inclusive_and_media_specific(tmp_path):
    assert upload_limit('application/pdf') == MAX_PDF_BYTES == 100 * 1024 * 1024
    assert upload_limit('text/plain') == MAX_UPLOAD == 10 * 1024 * 1024
    # Sparse unreferenced bytes between the last object and the cross-reference
    # table preserve a valid PDF and avoid building a 100 MiB Python buffer.
    raw = original(1)
    xref = raw.index(b'\nxref\n') + 1
    eof = raw.rindex(b'startxref\n') + len(b'startxref\n')
    tail = b'\n%%EOF\n'
    new_xref = MAX_PDF_BYTES - (eof - xref + len(tail) + len(str(MAX_PDF_BYTES)))
    path = tmp_path / 'size-boundary.pdf'
    with path.open('wb') as stream:
        stream.write(raw[:xref])
        stream.seek(new_xref - 1)
        stream.write(b'\n' + raw[xref:eof] + str(new_xref).encode() + tail)
    assert path.stat().st_size == MAX_PDF_BYTES
    assert inventory_isolated(path) == 1
    assert extract_isolated(path, 'application/pdf').text.strip()
    with path.open('ab') as stream:
        stream.write(b'\n')
    for operation in (lambda: inventory_isolated(path),
                      lambda: extract_isolated(path, 'application/pdf')):
        with pytest.raises(ExtractionError, match='too_large'):
            operation()
