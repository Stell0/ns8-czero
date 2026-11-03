# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import os
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmarks.ingestion import benchmark
from benchmarks.selective_context import benchmark as context_benchmark,frozen_plan

pytestmark=pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'),reason='owned disposable databases required')


def test_actual_whole_cold_and_current_warm_measurements_have_exact_readback(tmp_path):
    args=SimpleNamespace(database_url=os.environ['CZERO_TEST_DATABASE_URL'],output=str(tmp_path/'extraction'),
        cases=['plain.txt'],arms=['whole','units-1-cold','units-2-warm'],repeats=3,smoke=True)
    report=asyncio.run(benchmark(args))
    assert report['smoke_only'] and len(report['rows'])==3
    assert all(all(row['quality'].values()) for row in report['rows'])
    assert report['rows'][2]['queue']['cache_hits']==1
    assert all(row['cpu_seconds']>0 and row['sampled_process_tree_peak_rss_kib']>0 for row in report['rows'])
    assert all(row['reported_ocr_cost'] is None for row in report['rows'])


def test_real_sdk_context_fixture_control_is_not_reported_as_model_quality(tmp_path):
    args=SimpleNamespace(database_url=os.environ['CZERO_TEST_DATABASE_URL'],fixture_check=True,model='gpt-6-astra')
    directory=tmp_path/'context';directory.mkdir(mode=0o700)
    report=asyncio.run(context_benchmark(args,directory,frozen_plan(args)))
    assert report['fixture_only'] and len(report['episodes'])==8
    assert all(e['status']=='fixture_passed' for e in report['episodes'])
    assert report['summary']['lower_selective_context'] and report['summary']['all_evidence_checks_pass']
    assert report['summary']['model_quality_acceptance'] is False
    assert all(e['tokens'] is None for e in report['episodes'])
