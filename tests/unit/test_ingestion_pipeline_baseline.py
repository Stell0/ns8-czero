# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Freeze M0 extraction fidelity; these assert today's behavior, not a queue."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pypdf import PdfReader

from czero_core import extraction
from czero_core.jobs import Handler, MAX_JSON_BYTES

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/evidence/pipeline"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


@pytest.mark.parametrize("item", MANIFEST["files"], ids=lambda item: item["name"])
def test_frozen_originals_and_canonical_extraction(item):
    path = FIXTURES / item["name"]
    original = path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == item["original_sha256"]
    if "error" in item:
        with pytest.raises(extraction.ExtractionError, match="^" + item["error"] + "$"):
            extraction.extract_isolated(path, item["media_type"])
    else:
        result = extraction.extract_isolated(path, item["media_type"])
        assert result.text_hash == item["text_sha256"]
        assert len(result.text) == item["characters"]
        if "text" in item:
            assert result.text == item["text"]
        else:
            assert result.text == original.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        assert result.locations == item["locations"]
        segments = extraction.chunks(result)
        assert segments[0]["start"] == 0 and segments[-1]["end"] == len(result.text)
        for index, segment in enumerate(segments):
            assert segment["text"] == result.text[segment["start"]:segment["end"]]
            assert segment["text_hash"] == hashlib.sha256(segment["text"].encode()).hexdigest()
            if index:
                assert segment["start"] == segments[index - 1]["end"] - 150
    assert path.read_bytes() == original


def test_blank_pages_are_covered_by_original_inventory_not_text_locations():
    reader = PdfReader(FIXTURES / "blank-pages.pdf", strict=True)
    assert len(reader.pages) == 5
    assert [page.extract_text() for page in reader.pages] == [
        "", "Page 002: first evidence.", "", "Page 004: last evidence.", ""]
    scan = PdfReader(FIXTURES / "mixed-scan.pdf", strict=True)
    assert len(scan.pages) == 2 and scan.pages[0].extract_text()
    assert not scan.pages[1].extract_text()
    assert scan.pages[1]["/Resources"]["/XObject"]["/Im0"]["/Subtype"] == "/Image"


def test_original_generation_is_reproducible(tmp_path):
    subprocess.run([sys.executable, str(FIXTURES / "generate.py"), str(tmp_path)],
                   check=True, timeout=20)
    for item in MANIFEST["files"]:
        assert (tmp_path / item["name"]).read_bytes() == (FIXTURES / item["name"]).read_bytes()


def test_accepted_limits_and_generic_jobs_stay_bounded():
    assert (extraction.MAX_UPLOAD, extraction.MAX_TEXT_BYTES, extraction.MAX_CHARACTERS,
            extraction.MAX_LOCATIONS, extraction.MAX_CHUNKS) == (
                10 * 1024 * 1024, 2 * 1024 * 1024, 1_000_000, 4000, 4096)
    assert MAX_JSON_BYTES == 16384
    for options in ({"max_attempts": 6}, {"timeout_seconds": 31}):
        with pytest.raises(ValueError):
            Handler("bounded", lambda connection, payload: {}, **options)
