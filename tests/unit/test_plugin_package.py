# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""The offline handoff must bind one instance, preserve bytes and never overwrite."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).parents[2]
PACKAGE = runpy.run_path(str(ROOT / 'scripts/package-chatgpt-plugin.py'))
DOCS = runpy.run_path(str(ROOT / 'scripts/documentation.py'))


def build(output, **kwargs):
    return PACKAGE['build'](kwargs.pop('url', 'https://knowledge.example.org/mcp'),
        kwargs.pop('connection', 'asdk_app_fixture'), kwargs.pop('name', 'acme-knowledge'), output, **kwargs)


def files(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_reproducible_archive_binding_checksums_and_web_dependencies(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    one, two = build(a), build(b)
    assert one['archive_sha256'] == two['archive_sha256']
    assert files(a) == files(b)
    with zipfile.ZipFile(a/'plugin.zip') as archive:
        payload = {n: archive.read(n) for n in archive.namelist()}
        assert list(payload) == sorted(payload)
        assert all(i.date_time == (1980,1,1,0,0,0) and i.external_attr >> 16 == 0o100644 for i in archive.infolist())
    prefix='plugins/acme-knowledge/'
    assert payload == {n.removeprefix(prefix):v for n,v in files(a).items() if n.startswith(prefix)}
    assert 'plugin.json' in payload and '.app.json' in payload
    assert not any(n.startswith(('plugins/','.agents/')) for n in payload)
    for line in (a/'SHA256SUMS').read_text().splitlines():
        digest, path = line.split('  ',1)
        assert hashlib.sha256((a/path).read_bytes()).hexdigest() == digest
    manifest = json.loads(payload['plugin.json'])
    extension = manifest['extensions']['com.openai']
    base = a/'plugins/acme-knowledge'
    binding = json.loads((base/extension['apps']).read_text())
    assert binding == {'apps': {'c0': {'id':'asdk_app_fixture','required':True}}}
    assert (base/extension['onboardingSkill']).is_file()
    assert not any(Path(n).name in ('mcp.json','.mcp.json') for n in payload)
    assert not any('mcpServers' in v.decode() for n,v in payload.items() if n.endswith('.json'))
    assert payload['LICENSE'] == (ROOT/'LICENSE').read_bytes()
    assert {name for name in payload if name.startswith('skills/') and name.endswith('/SKILL.md')} == {
        'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
        'skills/c0-maintain-knowledge/SKILL.md', 'skills/c0-projects/SKILL.md'}
    assert b'project_get' in payload['skills/c0-projects/SKILL.md']
    assert b'project_run_claim' in payload['references/projects.md']
    assert b'{{' not in payload['references/projects.md']
    market = json.loads((a/'.agents/plugins/marketplace.json').read_text())
    assert a.joinpath(market['plugins'][0]['source']['path']).resolve() == base
    assert DOCS['check']([str(p.relative_to(a)) for p in a.rglob('*.md')], root=a) > 0


def test_distinct_instance_never_reuses_other_binding(tmp_path):
    build(tmp_path/'a')
    build(tmp_path/'b', url='https://other.example.net/mcp', connection='plugin_connector_second', name='other-knowledge')
    a, b = files(tmp_path/'a'), files(tmp_path/'b')
    assert a['plugin.zip'] != b['plugin.zip']
    for path, content in b.items():
        assert b'knowledge.example.org' not in content and b'asdk_app_fixture' not in content
    assert json.loads(b['plugins/other-knowledge/.app.json'])['apps']['c0']['id'] == 'connector_second'
    assert b'https://other.example.net/mcp' in b['plugins/other-knowledge/references/instance.md']


@pytest.mark.parametrize('url', [
    'http://knowledge.example.org/mcp','https://user:secret@knowledge.example.org/mcp',
    'https://knowledge.example.org/mcp?token=x','https://knowledge.example.org/mcp#x',
    'https://knowledge.example.org/mcp?','https://knowledge.example.org/mcp#',
    'https://knowledge.example.org/czero/x/mcp','https://knowledge.example.org/mcp/',
    'https://127.00.0.1/mcp','https://localhost/mcp','https://127.0.0.1/mcp','https://[::1]/mcp',
    'https://knowledge.example.org:8443/mcp','https://-bad.example.org/mcp',
    'https://bad-.example.org/mcp','https://bad..example.org/mcp',
    'https://knowledge.example.org./mcp','https://Knowledge.example.org/mcp',
    'https://knowledge.example.org/\\mcp','https://knowledge.example.org/mcp\n',
])
def test_bad_url_is_rejected_before_any_output(tmp_path, url):
    with pytest.raises(ValueError): build(tmp_path/'output', url=url)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('connection', ['plugin_random','https://chatgpt.com/connector/x','asdk_app_','asdk_app_x\n','../connector_x'])
def test_invalid_registered_app_identity(tmp_path, connection):
    with pytest.raises(ValueError): build(tmp_path/'output', connection=connection)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind', ['directory','file','symlink','dangling'])
def test_existing_output_is_never_touched(tmp_path, kind):
    output=tmp_path/'output'
    if kind=='directory':
        output.mkdir(); (output/'draft').write_text('keep')
    elif kind=='file': output.write_text('keep')
    else:
        target=tmp_path/'target'
        if kind=='symlink': target.mkdir(); (target/'draft').write_text('keep')
        output.symlink_to(target, target_is_directory=True)
    before={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError): build(output)
    assert before == {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert output.exists() or output.is_symlink()


@pytest.mark.parametrize('failure', ['missing','symlink'])
def test_unsafe_template_preflight_has_no_partial_output(tmp_path, failure):
    template=tmp_path/'template';shutil.copytree(ROOT/'plugins/c0-knowledge',template)
    target=template/'skills/c0-setup/SKILL.md';target.unlink()
    if failure=='symlink': target.symlink_to(ROOT/'plugins/c0-knowledge/skills/c0-setup/SKILL.md')
    with pytest.raises(ValueError):build(tmp_path/'output',template=template)
    assert {p.name for p in tmp_path.iterdir()} == {'template'}


def test_cli_failure_does_not_echo_private_input(tmp_path):
    result=subprocess.run(['python3',str(ROOT/'scripts/package-chatgpt-plugin.py'),
        '--mcp-url','https://secret:private@knowledge.example.org/mcp','--chatgpt-app-id','asdk_app_fixture',
        '--name','acme-knowledge','--output',str(tmp_path/'output')],capture_output=True,text=True)
    assert result.returncode == 2 and 'private' not in result.stderr and not result.stdout


def test_model_input_is_only_generated_skills_and_references(tmp_path):
    result=build(tmp_path/'package')
    root=tmp_path/'package/plugins/acme-knowledge'
    loader=runpy.run_path(str(ROOT/'tests/evaluation/skill_input.py'))['load_plugin']
    (root/'grader-secret.txt').write_text('THIS_ORACLE_MUST_STAY_OUT')
    instructions, proof=loader(root)
    assert 'THIS_ORACLE_MUST_STAY_OUT' not in instructions
    expected={'plugin.json','.app.json',*runpy.run_path(str(ROOT/'tests/evaluation/skill_input.py'))['FILES']}
    assert set(proof['files'])==expected
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in proof['files'].items())
    assert proof['automatic_skill_activation_proven'] is False
    (root/'plugin.json').unlink()
    (root/'plugin.json').symlink_to(ROOT/'plugins/c0-knowledge/plugin.json')
    with pytest.raises(ValueError): loader(root)


def test_standalone_memory_skill_is_deterministic_and_instance_specific():
    from czero_app.agent_packages import skill_payload, zip_bytes
    first = skill_payload('https://knowledge.example.org/mcp')
    second = skill_payload('https://other.example.net/mcp')
    assert set(first) == {'SKILL.md', 'agents/openai.yaml', 'LICENSE'}
    assert zip_bytes(first) == zip_bytes(skill_payload('https://knowledge.example.org/mcp'))
    assert zip_bytes(first) != zip_bytes(second)
    for content in second.values():
        assert b'knowledge.example.org' not in content and b'{{' not in content
    frontmatter = second['SKILL.md'].decode().split('---', 2)[1]
    metadata = dict(line.split(': ', 1) for line in frontmatter.strip().splitlines())
    assert metadata['name'].startswith('c0-memory-other-example-net-') and len(metadata['name']) <= 64
    assert 'other.example.net' in metadata['description']
    assert b'https://other.example.net/mcp' in second['agents/openai.yaml']
    assert b'transport: "streamable_http"' in second['agents/openai.yaml']
    assert second['LICENSE'] == (ROOT/'LICENSE').read_bytes()
