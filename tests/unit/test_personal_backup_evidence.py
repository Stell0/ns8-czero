# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
import pytest
from robot.libraries.BuiltIn import BuiltIn

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=runpy.run_path(str(ROOT/'tests/personal_backup_evidence.py'))
VALID={name:True for name in EVIDENCE['FIELDS']}


@pytest.mark.parametrize('value',[{},None,{**VALID,'private':'synthetic-private-value'},
    {**VALID,'personal_import_cleanup':1},{**VALID,'personal_restore_fenced':False}])
def test_incomplete_or_private_backup_evidence_is_rejected_without_logging(monkeypatch,value):
    monkeypatch.syspath_prepend(str(ROOT/'tests'))
    library=runpy.run_path(str(ROOT/'tests/CzeroBackup.py'))['CzeroBackup']()
    logged=[]
    monkeypatch.setattr(BuiltIn,'log',lambda _,value:logged.append(value))
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda _,value:logged.append(value))
    with pytest.raises(AssertionError,match='Personal backup acceptance measurement invalid'):
        library.verify_disposable_personal_state(json.dumps(value))
    assert logged==[]


def test_only_one_complete_native_proof_is_accepted(monkeypatch):
    assert EVIDENCE['require_proof']([VALID])==VALID
    for values in ([],[VALID,VALID]):
        with pytest.raises(AssertionError,match='One measured personal backup proof'):
            EVIDENCE['require_proof'](values)
    monkeypatch.syspath_prepend(str(ROOT/'tests'))
    library=runpy.run_path(str(ROOT/'tests/CzeroBackup.py'))['CzeroBackup']()
    logged=[]
    monkeypatch.setattr(BuiltIn,'log',lambda _,value:logged.append(value))
    monkeypatch.setattr(BuiltIn,'log_to_console',lambda _,value:None)
    library.verify_disposable_personal_state(json.dumps(VALID))
    assert len(logged)==1 and json.loads(logged[0].split(': ',1)[1])==VALID
