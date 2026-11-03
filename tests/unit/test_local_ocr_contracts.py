# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
import pytest
from czero_core.extraction import ExtractionError
from czero_core.local_ocr import validate_profile,validate_provenance,preflight,_tsv


def profile():
    return {'adapter':'local-tesseract','revision':1,'engine_sha256':'a'*64,'renderer_sha256':'b'*64,
        'engine_build_sha256':'d'*64,'renderer_build_sha256':'e'*64,
        'models':{'eng':'c'*64},'language':'eng','dpi':150,'scale':2400}


@pytest.mark.parametrize('change',[{'adapter':'cloud'},{'language':'../../eng'},{'language':'eng; command'},
    {'dpi':True},{'dpi':300},{'scale':99999999},{'models':{'eng':'invalid'}},{'url':'https://example.org'}])
def test_ocr_registry_and_settings_are_closed(change):
    with pytest.raises(ValueError): validate_profile({**profile(),**change})


def test_missing_optional_backend_does_not_fall_back_to_another_engine(monkeypatch,tmp_path):
    import czero_core.local_ocr as module
    monkeypatch.setattr(module,'ENGINE',tmp_path/'absent')
    with pytest.raises(ExtractionError,match='ocr_unavailable'): preflight()


def test_tsv_confidence_is_observed_and_invalid_output_cannot_succeed():
    header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
    body,confidence,words=_tsv((header+'5\t1\t1\t1\t1\t1\t0\t0\t5\t5\t95.5\tcafé\n').encode())
    assert (body,confidence,words)==('café',95.5,1)
    with pytest.raises(ExtractionError): _tsv(header.encode())
    with pytest.raises(ExtractionError): _tsv((header+'5\t1\t1\t1\t1\t1\t0\t0\t5\t5\tnan\twrong\n').encode())
