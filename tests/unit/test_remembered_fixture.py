# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native remembered proof requires every actual stage and strict public booleans."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from remembered_fixture import FIELDS,validate,require_recovery


@pytest.mark.parametrize('stage',FIELDS)
def test_native_proof_rejects_missing_false_extra_or_untyped_evidence(stage):
    proof={'stage':stage,**{key:True for key in FIELDS[stage]}}
    assert validate(proof)==proof
    for key in FIELDS[stage]:
        for bad in (None,False,1,'true'):
            with pytest.raises(AssertionError):validate({**proof,key:bad})
        with pytest.raises(AssertionError):validate({k:v for k,v in proof.items() if k!=key})
    with pytest.raises(AssertionError):validate({**proof,'private':True})


def test_all_three_measured_recovery_stages_are_required():
    values=[{'stage':stage,**{key:True for key in FIELDS[stage]}} for stage in FIELDS]
    assert require_recovery(values)==values
    for invalid in ([],values[:1],values[:2],[*values,values[0]],[values[0],values[1],values[1]]):
        with pytest.raises(AssertionError):require_recovery(invalid)


@pytest.mark.parametrize('stage',[None,[],{},True,'private.example.test'])
def test_invalid_stage_is_rejected_without_private_output(stage):
    with pytest.raises(AssertionError):validate({'stage':stage})
