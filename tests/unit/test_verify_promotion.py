# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Promotion requires the actual native suites, not screenshot publishing."""
from copy import deepcopy
import json
from pathlib import Path
import runpy

import pytest


@pytest.fixture
def promotion(monkeypatch):
    scripts = Path(__file__).parents[2] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    verify = runpy.run_path(str(scripts / 'verify-promotion.py'))['accepted_source']
    policy = verify.__globals__
    source, base = 'a' * 40, 'b' * 40
    proof = {'source': source, 'base': base, 'diff_hash': 'c' * 64,
             'kind': 'runtime', 'mode': 'full', 'draft': False,
             'policy_version': 2, 'native_required': True,
             'native_reason': 'risk_or_unknown', 'run_id': 12,
             'images_verified': True, 'native_verified': True,
             'jobs': {name: 'success' for name in policy['required_jobs']('runtime', 'full')}}
    jobs = [{'name': name, 'status': 'completed', 'conclusion': 'success'}
            for name in proof['jobs'] if name != 'native']
    jobs.extend({'name': name, 'status': 'completed', 'conclusion': result}
                for name, result in [
                    ('native / debian / update debian13', 'success'),
                    ('native / rocky / install rocky9', 'success'),
                    ('native / debian / screenshots', 'skipped'),
                    ('native / rocky / screenshots', 'success'),
                    ('C0 merge gate', 'success')])

    def gh(*args):
        if args[:2] == ('run', 'list'):
            return json.dumps([{'headSha': source, 'status': 'completed',
                                'conclusion': 'success', 'databaseId': 12}])
        if args[:2] == ('run', 'download'):
            (Path(args[-1]) / 'ci-proof.json').write_text(json.dumps(proof))
            return ''
        assert args[0] == 'api' and '/actions/runs/12/jobs?' in args[1]
        return json.dumps({'jobs': jobs})

    monkeypatch.setitem(policy, 'gh', gh)
    monkeypatch.setitem(policy, 'classify_source', lambda *a, **kw: deepcopy(proof))
    monkeypatch.setattr(policy['subprocess'], 'check_output', lambda *a, **kw: 'false\n')
    monkeypatch.setattr(policy['subprocess'], 'run', lambda *a, **kw: None)
    return lambda: verify('example/czero', source, require_full=True), jobs, proof


def test_skipped_screenshot_publishing_does_not_reject_successful_suites(promotion):
    verify, _, proof = promotion
    assert verify() == proof


@pytest.mark.parametrize('suite', ['native / debian / update debian13', 'native / rocky / install rocky9'])
@pytest.mark.parametrize('defect', ['missing', 'failure', 'skipped', 'in_progress', 'duplicate'])
def test_both_exact_native_suites_are_required(promotion, suite, defect):
    verify, jobs, _ = promotion
    jobs[:] = [j for j in jobs if not j['name'].endswith(' / screenshots')]
    job = next(j for j in jobs if j['name'] == suite)
    if defect == 'missing':
        jobs.remove(job)
    elif defect == 'duplicate':
        jobs.append(deepcopy(job))
    elif defect == 'in_progress':
        job.update(status='in_progress', conclusion=None)
    else:
        job['conclusion'] = defect
    with pytest.raises(ValueError, match='actual_required_jobs_missing'):
        verify()


def test_other_required_jobs_still_reject_skips(promotion):
    verify, jobs, _ = promotion
    next(j for j in jobs if j['name'] == 'local')['conclusion'] = 'skipped'
    with pytest.raises(ValueError, match='actual_required_jobs_missing'):
        verify()
