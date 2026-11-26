# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import io
import os
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.constants import UserAccessPermissions
from pypdf.generic import DictionaryObject, DecodedStreamObject, NameObject

from czero_core.extraction import ExtractionError, extract_isolated
from czero_core.pdf_units import extract_page_isolated, inventory_isolated
from czero_core.protected_pdf import PDFProtection, inspect_pdf, working_pdf

PDF = 'application/pdf'


def protected_bytes(password, *, restricted=False, pages=1, algorithm='AES-256'):
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    fonts = DictionaryObject({NameObject('/F1'): writer._add_object(font)})
    resources = writer._add_object(DictionaryObject({NameObject('/Font'): fonts}))
    for number in range(1, pages + 1):
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject('/Resources')] = resources
        content = DecodedStreamObject()
        content.set_data(f'BT /F1 12 Tf 20 190 Td (Synthetic PDF page {number}.) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(content)
    if password is not None:
        permissions = UserAccessPermissions(-1)
        if restricted:
            permissions &= ~UserAccessPermissions.EXTRACT
        writer.encrypt(password, owner_password='synthetic-owner', algorithm=algorithm,
            permissions_flag=permissions)
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


@pytest.mark.parametrize('required,restricted,algorithm', [
    (False, False, None),
    (False, False, 'AES-256'),
    (False, True, 'RC4-128'),
    (True, False, 'AES-128'),
    (True, True, 'AES-256'),
])
def test_encryption_inspection_preserves_stream_position(required, restricted, algorithm):
    password = 'synthetic pässword' if required else ''
    original = io.BytesIO(protected_bytes(password if algorithm else None,
        restricted=restricted, algorithm=algorithm))
    original.seek(12)
    if required:
        with pytest.raises(ExtractionError, match='^pdf_password_required$'):
            inspect_pdf(original)
        with pytest.raises(ExtractionError, match='^pdf_password_incorrect$'):
            inspect_pdf(original, 'bad')
    assert inspect_pdf(original, password) == PDFProtection(
        encrypted=bool(algorithm), restricted=restricted, password_required=required)
    assert original.tell() == 12


def test_approval_exposes_only_anonymous_working_copy(tmp_path):
    path = tmp_path / 'original.pdf'
    password = 'synthetic-password'
    encrypted = protected_bytes(password, restricted=True)
    path.write_bytes(encrypted)
    with path.open('rb') as stream:
        stream.seek(3)
        assert inspect_pdf(stream, password).restricted
        assert stream.tell() == 3
    with pytest.raises(ExtractionError, match='^pdf_extraction_approval_required$'):
        with working_pdf(path, password, restricted_approved=False):
            pytest.fail('Restricted PDF was made readable without approval')
    with working_pdf(path, password, restricted_approved=True) as work:
        assert os.fstat(work.descriptor).st_nlink == 0
        assert inventory_isolated(work) == 1
        assert extract_page_isolated(work, 1).text == 'Synthetic PDF page 1.'
        assert extract_isolated(work, PDF).text == 'Synthetic PDF page 1.'
    with pytest.raises(OSError):
        os.fstat(work.descriptor)
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_bytes() == encrypted
    with pytest.raises(ExtractionError, match='^encrypted_pdf$'):
        extract_isolated(path, PDF)


def test_long_protected_pdf_preserves_page_order_through_poppler(tmp_path):
    assert Path('/usr/bin/pdftotext').is_file()
    path = tmp_path / 'original.pdf'
    path.write_bytes(protected_bytes('', restricted=True, pages=201))
    with working_pdf(path, None, restricted_approved=True) as work:
        document = extract_isolated(work, PDF)
        assert [entry['index'] for entry in document.locations] == list(range(1, 202))
        assert extract_page_isolated(work, 200).text.strip() == 'Synthetic PDF page 200.'
