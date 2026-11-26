# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from io import BytesIO
from uuid import uuid4

import pytest
from czero_core.extraction import ExtractionError, MAX_PDF_BYTES, MAX_UPLOAD
from czero_core.sources import OriginalStore, _metadata, _payload


def test_oversized_empty_and_invalid_uploads_leave_no_partial_files(tmp_path):
    store = OriginalStore(tmp_path / 'originals')
    for content, code in [(b'', 'empty_upload'), (b'x' * (MAX_UPLOAD + 1), 'too_large')]:
        with pytest.raises(ValueError, match=code): store.write(uuid4(), BytesIO(content))
        assert list(store.root.iterdir()) == []


def test_pdf_original_stream_accepts_100_mib_and_rejects_the_next_byte(tmp_path):
    class SizedStream:
        def __init__(self, size):
            self.remaining = size

        def read(self, limit):
            count = min(self.remaining,limit)
            self.remaining -= count
            return b'x' * count

    store = OriginalStore(tmp_path / 'originals')
    identifier = uuid4()
    assert MAX_PDF_BYTES == 100 * 1024 * 1024
    _, size = store.write(identifier, SizedStream(MAX_PDF_BYTES), media_type='application/pdf')
    assert store.path(identifier).stat().st_size == size == MAX_PDF_BYTES
    with pytest.raises(ExtractionError,match='too_large'):
        store.write(uuid4(), SizedStream(MAX_PDF_BYTES+1), media_type='application/pdf')
    assert list(store.root.iterdir()) == [store.path(identifier)]


def test_source_root_symlink_and_request_path_are_rejected(tmp_path):
    target = tmp_path / 'target'; target.mkdir()
    link = tmp_path / 'link'; link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='invalid_source_directory'):
        OriginalStore(link).path(uuid4())
    store = OriginalStore(target)
    with pytest.raises(ValueError, match='invalid_reference'): store.path('../../escape')
    with pytest.raises(ValueError, match='invalid_payload'): _payload({'version_id': str(uuid4()), 'path': '/etc/passwd'})


@pytest.mark.parametrize('metadata', [{'field': '\0'}, {'nested': ['\0']}, {'\0': True}, {1: 'non-string key'}])
def test_metadata_rejects_postgresql_unsupported_strings_and_keys(metadata):
    with pytest.raises(ValueError): _metadata(metadata)
