# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original fixtures exercise isolated parsers inside the assembled image."""
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from pypdf import PdfWriter
from pypdf.constants import UserAccessPermissions
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from czero_core.extraction import extract_isolated
from czero_core.protected_pdf import PDFProtection, inspect_pdf


def probe():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'text'
        source.write_text('Evidence café 東京', encoding='utf-8')
        for media in ('text/plain', 'text/markdown'):
            assert extract_isolated(source, media).text == 'Evidence café 東京'
        source = root / 'document.docx'
        document = Document()
        document.add_paragraph('Evidence café 東京')
        document.save(source)
        assert extract_isolated(source, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document').text == 'Evidence café 東京'
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 72 720 Td (PDF evidence) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        source = root / 'document.pdf'
        writer.write(source)
        assert extract_isolated(source, 'application/pdf').text == 'PDF evidence'
        password = 'synthetic-opening-password'
        permissions = UserAccessPermissions(-1) & ~UserAccessPermissions.EXTRACT
        writer.encrypt(password, algorithm='AES-256', permissions_flag=permissions)
        protected = root / 'protected.pdf'
        writer.write(protected)
        with protected.open('rb') as stream:
            assert inspect_pdf(stream, password) == PDFProtection(
                encrypted=True, restricted=True, password_required=True)
    for name in ('tesseract-ocr','tesseract-ocr-eng','tesseract-ocr-ita','poppler-utils'):
        assert (Path('/usr/share/doc')/name/'copyright').is_file()
    from czero_core.local_ocr import preflight,extract_unit
    with TemporaryDirectory() as directory:
        scanned=Path(directory)/'scan.pdf'; scanned.write_bytes(scanned_original())
        assert extract_unit(scanned,1,preflight()).evidence.text==PHRASE
    print('Packaged parsers, protected PDF inspection, and local OCR pass')


if __name__ == '__main__':
    probe()
