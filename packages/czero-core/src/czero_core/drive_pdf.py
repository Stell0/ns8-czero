# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a complete Drive original with ordinary Core citation chunks."""
from pathlib import Path
from tempfile import TemporaryDirectory

from .extraction import ExtractionError, MAX_PDF_BYTES, chunks, extract_isolated


def prepare_pdf(body: bytes):
    """Produce ordinary citation chunks and keep mixed PDFs' textless pages explicit."""
    if not isinstance(body, bytes) or len(body) > MAX_PDF_BYTES:
        raise ExtractionError('too_large')
    if not body.startswith(b'%PDF-'):
        raise ExtractionError('invalid_pdf')
    with TemporaryDirectory(prefix='c0-drive-pdf-') as directory:
        path = Path(directory) / 'source.pdf'
        path.write_bytes(body)
        return prepare_pdf_file(path)


def prepare_pdf_file(path: Path):
    document = extract_isolated(path, 'application/pdf', allow_mixed_pdf=True)
    return document, chunks(document)
