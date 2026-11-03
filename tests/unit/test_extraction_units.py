# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from czero_core.extraction import Extracted, ExtractionError
from czero_core.extraction_queue import _result, ExtractionQueue, ExtractionWorker


@pytest.mark.parametrize('result', [None, Extracted('',[]), Extracted('x\r',[]),
    Extracted('text',[{'kind':'body','index':True,'start':0,'end':4}]),
    Extracted('text',[{'kind':'body','index':1,'start':0,'end':5}]),
    Extracted('text',[{'kind':'body','index':1,'start':0,'end':4,'path':'private'}]),
    Extracted('x'*1_000_001,[])])
def test_unit_outputs_are_bounded_typed_and_never_silently_truncated(result):
    with pytest.raises(ExtractionError): _result(result)


def test_normalized_unicode_offsets_and_fingerprint_are_exact():
    value = Extracted('café 東京',[{'kind':'body','index':1,'start':0,'end':7}])
    assert _result(value) == _result(value)
    assert _result(value) != _result(Extracted(value.text,[]))


def test_disabled_worker_opens_no_database_and_limits_stay_bounded():
    queue = ExtractionQueue(None,None,None)
    assert ExtractionWorker(queue).tick()==0
    for limit in (True,0,21):
        with pytest.raises(ValueError): ExtractionWorker(queue).tick(max_units=limit)
    with pytest.raises(ValueError): ExtractionQueue(None,None,None,enabled=1)


def test_app_worker_requires_explicit_opt_in_before_opening_database(monkeypatch,capsys):
    from czero_app.extraction_worker import main
    monkeypatch.delenv('CZERO_EXTRACTION_UNITS',raising=False)
    monkeypatch.setenv('CZERO_DATABASE_URL','invalid-private-value')
    assert main()==0 and '"processed": 0' in capsys.readouterr().out
    monkeypatch.setenv('CZERO_EXTRACTION_UNITS','yes')
    assert main()==1 and capsys.readouterr().err=='C0 extraction worker failed\n'
