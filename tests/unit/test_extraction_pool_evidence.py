# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[2]
evidence=runpy.run_path(str(ROOT/'tests/extraction_pool_evidence.py'))


def record(stage,workers):
    seed=stage=='seed'
    return {'stage':stage,'workers':workers,'units':9,'body_hash_verified':True,'staging_cleared':True,
        'native_limits_verified':seed,'backup_readback':not seed,'ocr_pages':1,'ocr_text_verified':True,
        'memory_peak_bytes':100000000 if seed else None,'parser_peak_rss_bytes':40000000 if seed else None,
        'memory_limit_bytes':workers*1073741824 if seed else None,
        'swap_limit_bytes':workers*1073741824 if seed else None,'pids_limit':256 if seed else None,
        'duration_seconds':2.5 if seed else None}


def test_both_actual_worker_budgets_and_backup_readbacks_are_required():
    values=[record(stage,workers) for stage in ('seed','verify') for workers in (2,4)]
    assert evidence['require_stages'](values)==values
    with pytest.raises(AssertionError): evidence['require_stages'](values[:-1])
    with pytest.raises(AssertionError): evidence['require_stages']([*values,values[0]])
    assert evidence['validate_measurement']({**record('seed',2),'memory_peak_bytes':None})['memory_peak_bytes'] is None


@pytest.mark.parametrize('change',[{'memory_peak_bytes':True},{'memory_peak_bytes':0},
    {'memory_limit_bytes':0},{'swap_limit_bytes':0},{'pids_limit':0},
    {'duration_seconds':float('nan')},{'duration_seconds':131},{'workers':True},
    {'parser_peak_rss_bytes':False},{'parser_peak_rss_bytes':536870913},
    {'units':True},{'body_hash_verified':False},{'backup_readback':True},
    {'private':'private-test-canary'}])
def test_incomplete_invented_or_private_measurements_are_rejected(change):
    with pytest.raises(AssertionError): evidence['validate_measurement']({**record('seed',2),**change})
