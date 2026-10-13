# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('state,running',[('activating',True),('inactive',False)])
def test_oneshot_status_distinguishes_running_from_idle(monkeypatch,capsys,state,running):
    def run(command,**options):
        if 'show' in command:return SimpleNamespace(stdout=state+'\n',returncode=0)
        return SimpleNamespace(returncode=1 if 'is-failed' in command else 0)
    monkeypatch.setattr(subprocess,'run',run)
    runpy.run_path(str(ROOT/'imageroot/actions/get-scheduler-status/20read'))
    assert json.loads(capsys.readouterr().out)=={
        'timer_active':True,'timer_enabled':True,'worker_running':running,'worker_failed':False}
