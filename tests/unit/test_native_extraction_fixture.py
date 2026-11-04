# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import re
import runpy
import sys
from types import ModuleType,SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('fail',[False,True])
def test_manual_reindex_restores_native_timer_even_on_private_failure(monkeypatch,fail):
    state={'active':True};commands=[];logs=[]
    def execute(command,**kwargs):
        commands.append(command)
        if command.endswith('/get-configuration'):
            return json.dumps({'host':'fixture.example.test','extraction':{'enabled':True}}),'',0
        if command.endswith('is-active czero-extraction.timer'):return 'active\n','',0
        if command.endswith('stop czero-extraction.timer czero-extraction.service'):
            state['active']=False;return '','',0
        if command.endswith('start czero-extraction.timer'):
            state['active']=True;return '','',0
        match=re.search(r' reindex ([24]) ',command)
        assert match and state['active'] is False
        if fail:return '','private-test-secret\nDisposable extraction pool proof failed (SourceConflict)',1
        return json.dumps({'stage':'reindex','workers':int(match[1]),'units':9,'verified':True}),'',0
    builtin=SimpleNamespace(set_log_level=lambda _: 'INFO',get_library_instance=lambda _:SimpleNamespace(execute_command=execute),
        log=logs.append,log_to_console=logs.append)
    for name in ('robot','robot.api','robot.api.deco','robot.libraries','robot.libraries.BuiltIn'):
        monkeypatch.setitem(sys.modules,name,ModuleType(name))
    sys.modules['robot.api.deco'].keyword=lambda function:function
    sys.modules['robot.libraries.BuiltIn'].BuiltIn=lambda:builtin
    monkeypatch.syspath_prepend(str(ROOT/'tests'))
    fixture=runpy.run_path(str(ROOT/'tests/CzeroExtraction.py'))['CzeroExtraction']()
    if fail:
        with pytest.raises(AssertionError,match='phase=reindex, workers=2, type=SourceConflict') as error:
            fixture.verify_disposable_explicit_reindex('czero901')
        assert 'private-test-secret' not in str(error.value)
    else:
        fixture.verify_disposable_explicit_reindex('czero901')
        assert len(logs)==4 and all('C0 explicit reindex:' in value for value in logs)
    assert state['active'] is True and commands[-1].endswith('start czero-extraction.timer')
    assert 'private-test-secret' not in repr(logs)
