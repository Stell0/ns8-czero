# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Original fixtures exercise isolated parsers inside the assembled image."""
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from czero_core.extraction import extract_isolated


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
    print('Four isolated packaged parsers preserve expected text')


if __name__ == '__main__':
    probe()
