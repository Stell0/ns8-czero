# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Development feedback must never masquerade as exact-source acceptance."""
from copy import deepcopy
from pathlib import Path
import runpy
import subprocess

import pytest


def policy():
    return runpy.run_path(str(Path(__file__).parents[2] / 'scripts/ci_policy.py'))


@pytest.mark.parametrize('path,area', [
    ('plugins/c0-knowledge/plugin.json', 'broad'),
    ('plugins/c0-knowledge/skills/c0-setup/SKILL.md', 'broad'),
    ('docs/plugin.md', 'docs'),
    ('docs/history/PLAN.md', 'docs'),
    ('README.md', 'docs'), ('PLAN.md', 'docs'), ('AGENTS.md', 'docs'),
    ('docs/ci-policy.md', 'docs'), ('app/static/agents.html', 'ui'),
    ('app/static/reader.js', 'ui'), ('ui/src/views/Status.vue', 'ui'),
    ('app/src/czero_app/sources.py', 'app'),
    ('app/src/czero_app/auth.py', 'broad'),
    ('app/src/czero_app/mcp_transport.py', 'broad'),
    ('packages/czero-core/README.md', 'broad'),
    ('samples/ingestion/README.md', 'broad'),
    ('samples/ingestion/src/c0_ingest/client.py', 'broad'),
    ('.agents/skills/c0-ingest-sources/SKILL.md', 'docs'),
    ('packages/czero-core/src/czero_core/access.py', 'broad'),
    ('packages/czero-core/src/czero_core/migrations/versions/0017.py', 'broad'),
    ('app/uv.lock', 'broad'), ('containers/czero-app/Containerfile', 'broad'),
    ('imageroot/actions/restore-module/40restoreDB', 'broad'),
    ('.github/workflows/test-local.yml', 'broad'),
    ('scripts/ci_policy.py', 'broad'), ('api/openapi.json', 'unknown'),
    ('docs/new-unreviewed.md', 'unknown'), ('new-runtime.txt', 'unknown'),
])
def test_impact_is_not_inferred_from_document_extension(path, area):
    assert policy()['area'](path) == area


def change(path, status='M', old=None, **extra):
    return {'status': status, 'old_path': old or path, 'path': path,
            'old_mode': '100644', 'mode': '100644', **extra}


def test_complete_diff_renames_deletions_and_modes_fail_closed():
    classify = policy()['classify']
    assert classify([change('README.md', 'D', mode='000000')])['kind'] == 'docs'
    assert classify([change('README.md', 'R100', 'app/static/agents.html')])['kind'] == 'runtime'
    assert classify([change('app/static/agents.html', 'R100', 'README.md')])['kind'] == 'runtime'
    assert classify([change('README.md', mode='120000')])['feedback'] == 'broad'
    assert classify([change('README.md'), change('app/uv.lock', 'D', mode='000000')])['feedback'] == 'broad'
    assert classify([])['feedback'] == 'broad'


def test_git_diff_includes_deleted_and_both_renamed_paths(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    (tmp_path / 'README.md').write_text('retained\n' * 30)
    (tmp_path / 'PLAN.md').write_text('delete this\n')
    git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'baseline')
    base = git('rev-parse', 'HEAD')
    initial = policy()['git_changes'](policy()['EMPTY_TREE'], base, cwd=tmp_path, pr=False)
    assert {c['path'] for c in initial} == {'README.md', 'PLAN.md'}
    assert all(c['status'] == 'A' for c in initial)
    (tmp_path / 'runtime.html').write_bytes((tmp_path / 'README.md').read_bytes())
    (tmp_path / 'README.md').unlink()
    (tmp_path / 'PLAN.md').unlink()
    git('add', '-A')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'rename and delete')
    changes = policy()['git_changes'](base, git('rev-parse', 'HEAD'), cwd=tmp_path)
    assert {c['old_path'] for c in changes} == {'README.md', 'PLAN.md'}
    assert next(c for c in changes if c['status'].startswith('R'))['path'] == 'runtime.html'
    assert policy()['classify'](changes)['kind'] == 'runtime'


SHA = 'a' * 40
BASE = 'b' * 40


def evidence(kind='runtime', mode='full'):
    required = policy()['required_jobs'](kind, mode)
    return {'source': SHA, 'base': BASE, 'diff_hash': 'c' * 64, 'kind': kind,
            'mode': mode, 'draft': False, 'run_id': 12, 'run_attempt': 1,
            'jobs': {name: 'success' for name in required},
            'images_verified': mode == 'full', 'native_verified': mode == 'full'}


def test_scoped_success_cannot_authorize_runtime_merge():
    p = policy()
    with pytest.raises(ValueError, match='full_validation_required'):
        p['verify_gate'](evidence(mode='scoped'), SHA, BASE, 'c' * 64)
    p['verify_gate'](evidence(), SHA, BASE, 'c' * 64)
    p['verify_gate'](evidence('docs', 'docs'), SHA, BASE, 'c' * 64)


@pytest.mark.parametrize('state', ['skipped', 'cancelled', 'failure', 'pending', None])
def test_every_required_full_job_must_actually_succeed(state):
    value = evidence()
    value['jobs']['native'] = state
    with pytest.raises(ValueError, match='required_job_not_successful'):
        policy()['verify_gate'](value, SHA, BASE, 'c' * 64)


@pytest.mark.parametrize('field,value', [('source', 'd'*40), ('base', 'd'*40),
    ('diff_hash', 'd'*64), ('draft', True), ('images_verified', False), ('native_verified', False)])
def test_stale_or_incomplete_proof_cannot_authorize_merge(field, value):
    proof = deepcopy(evidence()); proof[field] = value
    with pytest.raises(ValueError):
        policy()['verify_gate'](proof, SHA, BASE, 'c' * 64)


def test_ready_and_subsequent_updates_always_require_full_runtime_validation():
    decide = policy()['validation_mode']
    assert decide('runtime', 'app', 'pull_request', True) == 'scoped'
    for event in ('ready_for_review', 'synchronize', 'reopened'):
        assert decide('runtime', 'app', 'pull_request', False) == 'full', event
    assert decide('docs', 'docs', 'push', False) == 'docs'
    assert decide('docs', 'docs', 'workflow_dispatch', False) == 'full'
    assert decide('runtime', 'unknown', 'pull_request', True) == 'full'


def test_document_label_and_missing_readiness_cannot_bypass_gate():
    for proof in (evidence('docs', 'scoped'), {k:v for k,v in evidence().items() if k != 'draft'}):
        with pytest.raises(ValueError, match='invalid_classification'):
            policy()['verify_gate'](proof, SHA, BASE, 'c'*64)


@pytest.mark.parametrize('damage', ['revision', 'digest', 'siblings', 'missing'])
def test_candidate_identity_verifier_rejects_retagged_or_partial_images(damage):
    verify = runpy.run_path(str(Path(__file__).parents[2]/'scripts/verify-ci-images.py'))['verify_records']
    tag = 'ci-'+SHA+'-12-1'
    refs = ['ghcr.io/example/'+name+':'+tag for name in ('czero', 'czero-app', 'czero-postgres')]
    rows = [{'reference':ref, 'digest':'sha256:'+'c'*64, 'revision':SHA} for ref in refs]
    rows[0]['siblings'] = refs[1:]
    verify(rows, SHA, 'example', tag)
    if damage == 'missing':rows.pop()
    elif damage == 'siblings':rows[0]['siblings'] = [refs[1].rsplit(':',1)[0]+':main', refs[2]]
    else:rows[1][damage] = 'd'*40 if damage == 'revision' else 'sha256:wrong'
    with pytest.raises(ValueError):verify(rows, SHA, 'example', tag)


def test_every_selected_application_test_exists():
    root = Path(__file__).parents[2]
    for paths in policy()['APP_TESTS'].values():
        assert all((root/path).is_file() for path in paths)


@pytest.mark.parametrize('supports_flag', [True, False])
def test_completed_job_log_reader_allows_then_strips_terminal_escapes(monkeypatch, supports_flag):
    audit = runpy.run_path(str(Path(__file__).parents[2]/'scripts/audit-ci-artifacts.py'))
    def output(args, **kwargs):
        if args == ['gh', 'api', '--help']:
            return '--allow-escape-sequences' if supports_flag else 'Legacy API help'
        if supports_flag and '--allow-escape-sequences' not in args:
            raise ValueError('GH refuses terminal escapes without explicit capture permission')
        assert ('--allow-escape-sequences' in args) == supports_flag
        return '\x1b[32mC0 installed candidates: {}\x1b[0m\n'
    monkeypatch.setattr(subprocess, 'check_output', output)
    assert audit['gh']('api', 'repos/example/repo/actions/jobs/1/logs') == 'C0 installed candidates: {}\n'


@pytest.mark.parametrize('later_path,allowed', [('README.md', True), ('app.py', False)])
def test_main_documentation_merge_does_not_strand_accepted_runtime(tmp_path, monkeypatch, later_path, allowed):
    """Exercise the actual publication command with a real ancestor/diff graph."""
    import json
    import sys
    root = Path(__file__).parents[2]
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(root/'scripts'))
    monkeypatch.setenv('GITHUB_REPOSITORY', 'example/ns8-czero')
    monkeypatch.delenv('C0_RELEASE_TAG', raising=False)
    actual_output, actual_run = subprocess.check_output, subprocess.run
    def git(*args):
        return actual_output(['git', *args], text=True).strip()
    git('init', '-q')
    (tmp_path/'app.py').write_text('baseline\n');git('add', '.')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-qm','baseline')
    base = git('rev-parse','HEAD')
    (tmp_path/'app.py').write_text('accepted runtime\n');git('add','.')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-qm','accepted')
    source = git('rev-parse','HEAD')
    (tmp_path/later_path).write_text('later change\n');git('add','.')
    git('-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-qm','later')
    current = git('rev-parse','HEAD')
    p = policy()
    selected = p['classify'](p['git_changes'](base,source,pr=False))
    proof = {**evidence(), 'source':source, 'base':base, 'diff_hash':selected['diff_hash']}
    Path('ci-proof.json').write_text(json.dumps(proof))
    images = [{'reference':'ghcr.io/example/'+name+':ci-owned','digest':'sha256:'+'c'*64}
        for name in ('czero','czero-app','czero-postgres')]
    Path('candidate-images.json').write_text(json.dumps({'source':source,'images':images}))
    copies=[]
    def output(args, **kwargs):
        if args[0]=='gh':return json.dumps({'object':{'sha':current}})
        if args[:2]==['skopeo','inspect']:return json.dumps({'Digest':images[0]['digest'],
            'Labels':{'org.opencontainers.image.revision':source}})
        return actual_output(args, **kwargs)
    def run(args, **kwargs):
        if args[:2]==['skopeo','copy']:copies.append(args);return subprocess.CompletedProcess(args,0)
        if args[0]=='git' and 'fetch' in args:return subprocess.CompletedProcess(args,0)
        return actual_run(args, **kwargs)
    monkeypatch.setattr(subprocess,'check_output',output)
    monkeypatch.setattr(subprocess,'run',run)
    if allowed:
        runpy.run_path(str(root/'scripts/promote-ci-images.py'))
        assert len(copies)==6
        assert json.loads(Path('main-publication.json').read_text())['publication_ref_commit']==current
    else:
        with pytest.raises(SystemExit,match='Main runtime advanced'):
            runpy.run_path(str(root/'scripts/promote-ci-images.py'))
        assert not copies


def test_development_cancellation_covers_mode_changes_without_cancelling_acceptance():
    import re
    workflow = (Path(__file__).parents[2]/'.github/workflows/validate.yml').read_text()
    jobs = dict(re.findall(r'^  ([a-z-]+):\n(.*?)(?=^  [a-z-]+:\n|\Z)', workflow, re.M | re.S))
    groups = []
    for name in ('docs', 'feedback'):
        job = jobs[name]
        groups.append(re.search(r'^      group: (.+)$', job, re.M).group(1))
        assert 'cancel-in-progress: true' in job
    assert len(set(groups)) == 1
    assert "needs.classify.outputs.mode == 'full'" in jobs['retire-feedback']
    assert 'retire-feedback' in policy()['required_jobs']('runtime', 'full')
    for name in ('retire-feedback', 'local', 'released', 'renovate', 'producer', 'images', 'native', 'artifacts', 'gate', 'publish-canonical'):
        assert 'concurrency:' not in jobs[name], name


@pytest.mark.parametrize('damage,expected', [
    ('docs', [9]), ('scoped', [9]), ('full', []), ('missing', []),
    ('different_pr', []), ('different_source', []), ('newer', []),
    ('same_source', []), ('finished', []), ('superseded', []),
])
def test_retirement_requires_old_development_proof_and_preserves_full_runs(tmp_path, monkeypatch, damage, expected):
    import json
    retire = runpy.run_path(str(Path(__file__).parents[2]/'scripts/retire-ci-feedback.py'))['retire']
    selection = {'source': SHA, 'mode': 'full', 'pr_number': 14}
    run = {'id': 9, 'head_sha': BASE, 'status': 'in_progress', 'created_at': '2026-10-18T15:00:00Z'}
    prior = {'source': BASE, 'mode': damage, 'pr_number': 14, 'event': 'pull_request'}
    if damage == 'different_pr': prior.update(mode='scoped', pr_number=99)
    if damage == 'different_source': prior.update(mode='scoped', source='c'*40)
    if damage == 'newer': run['created_at'] = '2026-10-18T17:00:00Z'
    if damage == 'same_source': run['head_sha'] = SHA
    calls = []
    def gh(*args):
        calls.append(args)
        if args[0] == 'run':
            if damage == 'missing': raise subprocess.CalledProcessError(1, 'gh')
            Path(args[args.index('--dir')+1], 'ci-selection.json').write_text(json.dumps(prior))
            return ''
        if '--method' in args:
            assert args[-1].endswith('/9/cancel')
            return ''
        path = args[1]
        if path.endswith('/runs/100'):
            return json.dumps({'created_at': '2026-10-18T16:00:00Z'})
        if path.endswith('/pulls/14'):
            return json.dumps({'head': {'sha': 'c'*40 if damage == 'superseded' else SHA}})
        if 'workflows/validate.yml/runs?' in path:
            return json.dumps({'workflow_runs': [run]})
        assert path.endswith('/runs/9')
        return json.dumps({'status': 'completed' if damage == 'finished' else 'in_progress'})
    monkeypatch.setitem(retire.__globals__, 'gh', gh)
    assert retire(selection, 'example/ns8-czero', '100', 'feature/example') == expected
    assert sum('--method' in call for call in calls) == len(expected)


@pytest.mark.parametrize('mode,ref,gate,classify_result,cancelled,expected', [
    ('full', 'refs/heads/main', 'success', 'success', False, True),
    ('full', 'refs/tags/0.44.0', 'success', 'success', False, True),
    ('full', 'refs/tags/core-v0.29.0', 'success', 'success', False, False),
    ('full', 'refs/pull/18/merge', 'success', 'success', False, False),
    ('full', 'refs/heads/feature', 'success', 'success', False, False),
    ('docs', 'refs/heads/main', 'success', 'success', False, False),
    ('scoped', 'refs/heads/main', 'success', 'success', False, False),
    ('full', 'refs/heads/main', 'failure', 'success', False, False),
    ('full', 'refs/heads/main', 'skipped', 'success', False, False),
    ('full', 'refs/heads/main', 'cancelled', 'success', False, False),
    ('full', 'refs/heads/main', 'success', 'failure', False, False),
    ('full', 'refs/heads/main', 'success', 'success', True, False),
])
def test_actual_publication_condition_handles_skipped_ancestors_and_failed_gates(mode, ref, gate, classify_result, cancelled, expected):
    import re
    workflow = (Path(__file__).parents[2]/'.github/workflows/validate.yml').read_text()
    publisher = workflow.split('  publish-canonical:\n', 1)[1]
    condition = re.search(r'^    if: (.+)$', publisher, re.M).group(1)
    # GitHub injects success() unless a status function is explicit; a skipped
    # docs/feedback ancestor makes that implicit dependency-chain check false.
    # See actions/runner#2205. Evaluate the real job expression, not a copy.
    explicit = re.search(r'\b(?:always|cancelled|success|failure)\(', condition)
    expression = condition
    for key, value in {'needs.classify.outputs.mode': mode, 'github.ref': ref,
            'needs.gate.result': gate, 'needs.classify.result': classify_result}.items():
        expression = expression.replace(key, repr(value))
    expression = expression.replace('always()', 'True').replace('cancelled()', repr(cancelled))
    expression = expression.replace('&&', ' and ').replace('||', ' or ').replace('!', ' not ')
    result = bool(eval(expression, {'__builtins__': {}, 'startsWith': lambda value, prefix: value.startswith(prefix)})) if explicit else False
    assert result is expected


def test_broad_feedback_rejects_a_syntax_error_in_the_second_shell_file(tmp_path, monkeypatch):
    # bash -n accepts positional arguments but parses only the first script.
    # Exercise actual bash against an independent invalid later input.
    import json
    import sys
    root=Path(__file__).parents[2]
    for name in ('build-images.sh','imageroot/actions/configure-module/80start_services',
                 'imageroot/actions/create-module/40scheduler',
                 'imageroot/update-module.d/60scheduler','imageroot/update-module.d/80restart'):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('true\n')
    (tmp_path/'imageroot/actions/configure-module/80start_services').write_text('if then\n')
    selection=tmp_path/'selection.json';selection.write_text(json.dumps({'feedback':'broad','node':False,'vue':False}))
    actual_run=subprocess.run
    def run(args, **kwargs):
        if args[0]=='bash':return actual_run(args, **kwargs)
        return subprocess.CompletedProcess(args,0)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys,'argv',['run-ci-feedback.py',str(selection)])
    monkeypatch.setattr(subprocess,'run',run)
    with pytest.raises(subprocess.CalledProcessError):
        runpy.run_path(str(root/'scripts/run-ci-feedback.py'),run_name='__main__')
