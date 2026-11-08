#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Complete-diff classification and fail-closed merge acceptance policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


# Reviewed against Containerfile COPYs, package readme/license inputs and the
# module builder. Never replace this with **/*.md or docs/**.
DOCS = frozenset({
    'README.md', 'PLAN.md', 'AGENTS.md', 'docs/ci-policy.md',
    'docs/c0-agent-memory-baseline.md', 'docs/m14-readiness.md',
    'docs/m14-release-notes.md', 'docs/retrieval-benchmark.md',
    'docs/installation-candidate.md', 'docs/index.md', 'docs/user-guide.md', 'docs/administration.md',
    'docs/chatgpt.md', 'docs/plugin.md', 'docs/development.md',
    'docs/reference.md', 'docs/vue-website.md', 'docs/release-readiness.md', 'docs/tool-evaluations.md',
    'docs/history/README.md', 'docs/history/AGENTS.md', 'docs/history/PLAN.md',
    '.agents/references/development.md',
    *('.agents/skills/'+name+'/SKILL.md' for name in (
        'c0-create-feature', 'c0-develop-core', 'c0-contribute-upstream', 'c0-upgrade-from-upstream', 'c0-evaluate-tools', 'c0-ingest-sources')),
})
SHA = re.compile(r'[0-9a-f]{40}\Z')
EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
POLICY_VERSION = 2
# Presentation-only candidates still need a complete diff review before auto-merge.
# Authentication/admin pages, executable application code, vendors and all unknown
# paths deliberately stay native-required. File additions/deletions/modes broaden.
OPTIONAL_NATIVE_UI = frozenset({
    'app/frontend/src/style.css',
})
FAST_TESTS = ['app/tests/test_app.py', 'app/tests/test_compiled_website.py', 'packages/czero-core/tests', 'tests/unit']
APP_TESTS = {
    'sources.py': ['tests/integration/test_sources_http.py', 'tests/integration/test_source_text_http.py'],
    'knowledge.py': ['tests/integration/test_knowledge_http.py', 'tests/integration/test_wiki_memory_http.py'],
    'objects.py': ['tests/integration/test_objects_http.py', 'tests/integration/test_object_type_regression.py'],
    'annotations.py': ['tests/integration/test_annotations_http.py'],
    'bundles.py': ['tests/integration/test_bundle_http.py'],
    'retrieval.py': ['tests/integration/test_retrieval.py', 'tests/integration/test_hybrid_retrieval.py'],
    'spaces.py': ['tests/integration/test_spaces_http.py'],
    'jobs.py': ['tests/integration/test_jobs_http.py'],
}


def area(path):
    if (not isinstance(path, str) or not path or path.startswith('/')
            or any(p in ('', '.', '..') for p in path.split('/'))):
        return 'unknown'
    if path in DOCS:
        return 'docs'
    if path.startswith(('app/static/', 'ui/', 'tests/ui/')):
        # Dependency locks/metadata and build configuration always broaden.
        return 'broad' if Path(path).name in {'package.json', 'yarn.lock', 'vue.config.js', '.yarnrc.yml'} else 'ui'
    if path.startswith('app/src/czero_app/'):
        return 'app' if Path(path).name in APP_TESTS else 'broad'
    if path.startswith(('packages/', 'app/', 'containers/', 'imageroot/', '.github/',
                        'scripts/', 'tests/', 'examples/', 'samples/', 'plugins/')):
        return 'broad'
    if path in {'build-images.sh', 'renovate.json', 'c0-upstream.json', '.gitignore'}:
        return 'broad'
    return 'unknown'


def presentation_path(path):
    return area(path) != 'unknown' and (path in OPTIONAL_NATIVE_UI or
            (path.startswith('ui/src/assets/') and Path(path).suffix in {'.css', '.scss'}))


def ui_test_path(path):
    return area(path) != 'unknown' and ((path.startswith('tests/ui/') and Path(path).suffix in {'.js', '.cjs'}) or (
        path.startswith('tests/e2e/test_') and Path(path).suffix == '.py'))


def git_changes(base, head, *, cwd='.', pr=True):
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError('invalid_diff_source')
    if base == EMPTY_TREE:
        subprocess.run(['git', 'hash-object', '-w', '-t', 'tree', '--stdin'],
            input=b'', stdout=subprocess.DEVNULL, cwd=cwd, check=True)
    revisions = [base+'...'+head] if pr else [base, head]
    raw = subprocess.check_output(['git', 'diff', '--no-ext-diff', '--raw', '-z', '-M',
        *revisions, '--'], cwd=cwd).decode('utf-8', 'strict').split('\0')
    result = []
    index = 0
    while index < len(raw) and raw[index]:
        header = raw[index].split(); index += 1
        if len(header) != 5 or not header[0].startswith(':'):
            raise ValueError('invalid_diff_record')
        old = path = raw[index]; index += 1
        status = header[4]
        if status.startswith(('R', 'C')):
            path = raw[index]; index += 1
        result.append({'status': status, 'old_path': old, 'path': path,
                       'old_mode': header[0][1:], 'mode': header[1]})
    return result


def classify_source(base, head, *, cwd='.', pr=True):
    selected = classify(git_changes(base, head, cwd=cwd, pr=pr))
    if selected['native_reason'] != 'ui_allowlist':
        return selected
    paths = [path for path in selected['paths'] if presentation_path(path)]
    revisions = [base+'...'+head] if pr else [base, head]
    raw = subprocess.check_output(['git', 'diff', '--no-ext-diff', '--unified=0',
        *revisions, '--', *paths], cwd=cwd).decode('utf-8', 'strict') if paths else ''
    changed = []
    in_hunk = False
    for line in raw.splitlines():
        if line.startswith('diff --git '):
            in_hunk = False
        elif line.startswith('@@'):
            in_hunk = True
        elif in_hunk and line.startswith(('+', '-')):
            changed.append(line[1:])
    # These can change executable wiring, identity controls or dependencies even
    # inside a presentation file. Conservative matches need full acceptance.
    sensitive = (r'url\s*\(|@import\b|@font-face\b|'
        r'<\s*/?\s*(?:script|link|base|style|meta|iframe|object|embed|form|input|button|select|textarea)\b|'
        r'\b(?:on\w+|src|integrity|nonce|action|method|data-[\w-]+|id|hidden)\s*=|'
        r'/(?:auth|oauth|api)/|javascript\s*:|\[hidden\]')
    if re.search(sensitive, '\n'.join(changed), re.I):
        selected.update(native_required=True, native_reason='ui_behavior_or_dependency')
    return selected


def classify(changes):
    paths = sorted({p for c in changes for p in (c['old_path'], c['path'])})
    areas = {'ui' if presentation_path(p) or ui_test_path(p) else area(p) for p in paths}
    if not changes or any(c['status'][0] not in 'AMDRC' or
            c['old_mode'] not in {'000000', '100644', '100755'} or
            c['mode'] not in {'000000', '100644', '100755'} for c in changes):
        areas.add('broad')
    feedback = next((a for a in ('unknown', 'broad', 'app', 'ui') if a in areas), 'docs')
    digest = hashlib.sha256(json.dumps(changes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    presentation = feedback == 'ui' and all(
        path in DOCS or presentation_path(path) or ui_test_path(path) for path in paths)
    presentation = presentation and all(
        c['path'] in DOCS or ui_test_path(c['path']) or
        (c['status'] == 'M' and c['old_mode'] == c['mode'] == '100644') for c in changes)
    native_required = feedback != 'docs' and not presentation
    return {'kind': 'docs' if feedback == 'docs' else 'runtime', 'feedback': feedback,
            'paths': paths, 'changes': changes, 'diff_hash': digest,
            'pytest': FAST_TESTS.copy(), 'node': True,
            'vue': any(p.startswith('ui/') for p in paths),
            'native_required': native_required,
            'native_reason': 'risk_or_unknown' if native_required else 'ui_allowlist' if presentation else 'docs_allowlist'}


def validation_mode(kind, feedback, event, draft, *, native_required=True):
    if event == 'workflow_dispatch' or feedback == 'unknown':
        return 'full'
    if kind == 'docs':
        return 'docs'
    return 'full' if native_required else 'fast'


def required_jobs(kind, mode, *, version=POLICY_VERSION):
    if mode == 'full':
        jobs = ('classify', 'retire-feedback', 'local', 'producer', 'released', 'renovate', 'images', 'native', 'artifacts')
        return (*jobs, 'feedback') if version == POLICY_VERSION else jobs
    return ('classify', 'docs') if kind == 'docs' else ('classify', 'feedback')


def verify_gate(proof, source, base, diff_hash, *, require_full=False, native_required=None):
    if (proof.get('source') != source or proof.get('base') != base
            or proof.get('diff_hash') != diff_hash or not SHA.fullmatch(source)):
        raise ValueError('stale_validation_source')
    if type(proof.get('draft')) is not bool:
        raise ValueError('invalid_classification')
    if proof['draft']:
        raise ValueError('ready_for_review_required')
    kind, mode = proof.get('kind'), proof.get('mode')
    version = proof.get('policy_version', 1)
    if type(version) is not int or version not in {1, POLICY_VERSION}:
        raise ValueError('invalid_policy_version')
    if kind not in {'docs', 'runtime'} or mode not in {'docs', 'scoped', 'fast', 'full'}:
        raise ValueError('invalid_classification')
    if kind == 'docs' and mode in {'scoped', 'fast'}:
        raise ValueError('invalid_classification')
    if version == POLICY_VERSION:
        if type(proof.get('native_required')) is not bool or proof.get('native_reason') not in {
                'risk_or_unknown', 'ui_behavior_or_dependency', 'ui_allowlist', 'docs_allowlist'}:
            raise ValueError('invalid_native_policy')
        if native_required is not None and proof['native_required'] != native_required:
            raise ValueError('native_classification_changed')
    if require_full and mode != 'full':
        raise ValueError('full_validation_required')
    if kind == 'runtime' and mode != 'full' and not (
            version == POLICY_VERSION and mode == 'fast' and
            proof.get('native_required') is False and proof.get('native_reason') == 'ui_allowlist' and
            native_required is False and proof.get('images_verified') is False and proof.get('native_verified') is False):
        raise ValueError('full_validation_required')
    if any(proof.get('jobs', {}).get(name) != 'success' for name in required_jobs(kind, mode, version=version)):
        raise ValueError('required_job_not_successful')
    if mode == 'full' and (proof.get('images_verified') is not True or proof.get('native_verified') is not True):
        raise ValueError('full_artifacts_not_verified')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--event', choices=('pull_request', 'push', 'workflow_dispatch'), required=True)
    parser.add_argument('--draft', choices=('true', 'false'), default='false')
    parser.add_argument('--output', default='ci-selection.json')
    args = parser.parse_args()
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if actual != args.head:
        raise SystemExit('Tested checkout does not match source')
    value = classify_source(args.base, args.head, pr=args.event == 'pull_request')
    value.update(source=args.head, base=args.base, draft=args.draft == 'true', event=args.event,
                 policy_version=POLICY_VERSION)
    value['mode'] = validation_mode(value['kind'], value['feedback'], args.event, value['draft'],
                                    native_required=value['native_required'])
    Path(args.output).write_text(json.dumps(value, indent=2)+'\n')
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            for key in ('source', 'base', 'kind', 'feedback', 'mode'):
                out.write(key+'='+value[key]+'\n')
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
