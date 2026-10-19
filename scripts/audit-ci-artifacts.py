#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect actual native outputs, checked-out sources, scans and privacy controls."""
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from renewal_evidence import validate_measurement


REQUIRED_UI = {
    'Check saved settings and application HTTPS in a browser',
    'Check rejected sign-in can switch accounts in a browser',
    'Check OAuth consent, delegated scopes and SDK calls in a browser',
    'Check object CRUD and Reader controls in a browser',
    'Check source ingestion, history, search and Reader controls in a browser',
    'Check Wiki revisions, provenance, graph and Reader controls in a browser',
    'Check hybrid search, citations and Reader behavior in a browser',
    'Check protected spaces, grants and revocation in a browser',
}
QUERY = re.compile(r'[?&](?:state|nonce|code_challenge|code|access_token|id_token)=')


def gh(*args):
    command = ['gh', *map(str, args)]
    job_log = args[0] == 'api' and str(args[1]).endswith('/logs')
    if job_log:
        # New CLI versions refuse terminal escapes even on captured stdout.
        # Older versions accept logs but do not know the explicit-capture flag.
        help_text = subprocess.check_output(['gh', 'api', '--help'], text=True)
        if '--allow-escape-sequences' in help_text:
            command.append('--allow-escape-sequences')
    value = subprocess.check_output(command, text=True)
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', value) if job_log else value


def marker_values(logs, marker):
    result = []
    for line in logs.splitlines():
        if marker in line:
            try:
                result.append(json.JSONDecoder().raw_decode(line.split(marker, 1)[1].strip())[0])
            except json.JSONDecodeError:
                continue
    return result


def audit_reports(directory, source, images, logs):
    reports = sorted(directory.rglob('output.xml'))
    assert len(reports) == 2, 'Both native reports are required'
    actual_ui = set(); privacy = 0; audited = 0; summaries = []; renewal = []
    for report in reports:
        raw = report.read_text()
        measured = marker_values(html.unescape(raw), 'C0 renewable session: ')
        assert len(measured) == 1, 'One measured renewal proof per native distribution is required'
        renewal.append(validate_measurement(measured[0]))
        root = ET.fromstring(raw)
        tests = list(root.iter('test'))
        assert tests and all(t.find('status').get('status') in {'PASS', 'SKIP'} for t in tests)
        expected_skips = {'Update an unconfigured instance without starting it',
            'Preserve a legacy prefix during native upgrade', 'Exercise the native module update'} if '-install-' in str(report) else set()
        skips = {t.get('name') for t in tests if t.find('status').get('status') == 'SKIP'}
        assert skips == expected_skips, 'Unexpected or missing native skips'
        ui = {t.get('name') for t in tests if any(tag.text == 'ui' for tag in t.findall('tag'))}
        assert all(t.find('status').get('status') == 'PASS' for t in tests if t.get('name') in ui)
        actual_ui |= ui
        assert len(tests) == 21 + len(ui), 'Native cases were omitted'
        for name in ('Verify exact installed candidate images', 'Verify protected Core spaces in the installed runtime',
                'Preserve admitted identities through update and clean restore'):
            assert any(t.get('name') == name and t.find('status').get('status') == 'PASS' for t in tests), name
        sso = [kw for kw in root.iter('kw') if kw.get('name') == 'Verify Disposable Sso']
        assert len(sso) == 2 and all(kw.find('status').get('status') == 'PASS' for kw in sso)
        for name, count in (('Prepare Disposable Identity Persistence', 1), ('Verify Disposable Identity Persistence', 2)):
            found = [kw for kw in root.iter('kw') if kw.get('name') == name]
            assert len(found) == count and all(kw.find('status').get('status') == 'PASS' for kw in found)
        guards = [kw for kw in root.iter('kw') if 'private' in kw.get('name', '').lower() and 'password' in kw.get('name', '').lower()]
        assert all(kw.find('status').get('status') == 'PASS' for kw in guards)
        privacy += len(guards)
        for path in (report, report.parent / 'playwright-log.txt'):
            if path.exists():
                assert not QUERY.search(html.unescape(path.read_text(errors='strict'))), 'OAuth query in native artifacts'
                audited += 1
        version = report.parent / 'diag/module-version.txt'
        assert version.is_file() and images[0]['digest'] in version.read_text(), 'Tested module digest differs'
        if '-update-' in str(report):
            predecessors = re.findall(r'ghcr.io/[^\s\x27\x22]+@sha256:([0-9a-f]{64})', Path('tests/czero.robot').read_text())
            assert len(set(predecessors)) == 3 and all(p in raw for p in predecessors), 'Genuine predecessor images missing'
        summaries.append({'artifact': report.parent.name, 'passed': len(tests)-len(skips), 'skipped': len(skips), 'ui': len(ui)})
    assert actual_ui == REQUIRED_UI and privacy >= 8 and audited == 3
    installed = marker_values(logs, 'C0 installed candidates: ')
    assert len(installed) == 2
    for value in installed:
        assert value['source'] == source
        assert [i['digest'] for i in value['images']] == [i['digest'] for i in images[1:]], 'Installed app/database digests differ'
    measurements = marker_values(logs, 'C0 accessibility: ')
    assert len(measurements) >= 25
    for value in measurements:
        assert all(type(v) is int and v >= 0 for k, v in value.items() if k not in {'page', 'role'})
        assert all(v == 0 for k, v in value.items() if k.startswith(('unnamed_', 'missing_')))
    return {'source': source, 'accepted': True, 'reports': summaries, 'browser_workflows': 8,
            'privacy_guards': privacy, 'query_artifacts': audited, 'oauth_query_candidates': 0,
            'accessibility_contexts': len(measurements), 'three_installed_candidate_images_verified': True,
            'renewal_measurements': renewal}


def main():
    repo = os.environ['GITHUB_REPOSITORY']; run = os.environ['GITHUB_RUN_ID']
    candidate = json.loads(Path('candidate-images.json').read_text()); source = candidate['source']
    gh('run', 'download', run, '--repo', repo, '--pattern', 'test-outputs-*', '--dir', 'native-reports')
    gh('run', 'download', run, '--repo', repo, '--pattern', 'trivy-*', '--dir', 'scan-reports')
    scans = sorted(Path('scan-reports').glob('*'))
    assert len(scans) == 5, 'Five actual scan/report pairs required'
    for scan in scans:
        sarif = json.loads((scan/'trivy-results.sarif').read_text())
        sbom = json.loads((scan/'sbom.cdx.json').read_text())
        assert sarif['version'] == '2.1.0' and sarif['runs'] and sbom['bomFormat'] == 'CycloneDX'
        assert sbom.get('metadata'), 'Missing SBOM metadata'
        if scan.name == 'trivy-ui' or '-czero-app-' in scan.name or '-czero-postgres-' in scan.name:
            assert sbom.get('components'), 'Empty package-bearing SBOM'
    jobs = json.loads(gh('api', 'repos/'+repo+'/actions/runs/'+run+'/jobs?per_page=100'))['jobs']
    native = [j for j in jobs if j['name'].startswith('native /') and j['name'].endswith(('debian13', 'rocky9'))]
    assert len(native) == 2 and all(j['conclusion'] == 'success' for j in native)
    logs = ''
    for job in native:
        text = gh('api', 'repos/'+repo+'/actions/jobs/'+str(job['id'])+'/logs')
        assert 'git checkout --progress --force '+source in text
        lines = text.splitlines()
        assert any('git log -1 --format=%H' in line and n+1 < len(lines) and lines[n+1].strip().endswith(source) for n, line in enumerate(lines))
        logs += text+'\n'
    # Preserve failed evidence as an artifact too; it contains only existing CI
    # logs/reports and is covered by the same privacy checks before acceptance.
    Path('native-job-logs.txt').write_text(logs)
    proof = audit_reports(Path('native-reports'), source, candidate['images'], logs)
    proof['actual_scan_pairs'] = 5
    Path('native-acceptance.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
