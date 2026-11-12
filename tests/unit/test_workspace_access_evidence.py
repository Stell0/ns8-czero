# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[2]
MODULE=runpy.run_path(str(ROOT/'tests/workspace_access_evidence.py'))
VALID=[{'phase':phase,**copy.deepcopy(fields)} for phase,fields in MODULE['EXPECTED'].items()]


def test_all_actual_access_stages_are_required():
    assert MODULE['require_stages'](VALID)==VALID
    for index in range(len(VALID)):
        with pytest.raises(AssertionError):MODULE['require_stages'](VALID[:index]+VALID[index+1:])
    with pytest.raises(AssertionError):MODULE['require_stages'](VALID+[VALID[0]])


@pytest.mark.parametrize('phase,key,value',[
    ('approved','allowed_scopes',['c0:read']),('approved','user_role','editor'),
    ('disconnected','member_statuses',[401,401]),('disconnected','other_status',401),
    ('disconnected','refresh_status',200),('blocked_after_restart','blocked_signins',0),
    ('blocked','blocked',1),('blocked_after_restart','restart_changed',False),('unblocked','member_statuses',[200,401]),
    ('manage_permissions','workspace_status',403),('editor_permissions','workspace_status',200),
    ('unblocked','clients_disabled',False),('prepare','fresh_reader',False),
    ('prepare','self_service_read',False),('prepare','default_space_read',False),
    ('blocked_after_restart','public_space_preserved',False),
])
def test_false_or_private_access_evidence_is_rejected(phase,key,value):
    rows=copy.deepcopy(VALID);row=next(r for r in rows if r['phase']==phase);row[key]=value
    with pytest.raises(AssertionError):MODULE['require_stages'](rows)
    row[key]=MODULE['EXPECTED'][phase][key];row['private']='must-not-appear'
    with pytest.raises(AssertionError):MODULE['require_stages'](rows)
