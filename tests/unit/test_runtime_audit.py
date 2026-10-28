# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize('suffix', ['.h', '.pxd', '.pxi', '.pyx'])
def test_image_audit_rejects_extension_build_sources(tmp_path, monkeypatch, suffix):
    module = runpy.run_path(str(Path(__file__).parents[1] / 'audit_runtime.py'))
    monkeypatch.setattr(module['importlib'].util, 'find_spec', lambda name: None)
    (tmp_path / ('extension' + suffix)).write_text('build-only')
    with pytest.raises(SystemExit, match='Development files'):
        module['audit'](tmp_path)
    (tmp_path / ('extension' + suffix)).unlink()
    (tmp_path / 'extension.so').write_bytes(b'runtime')
    module['audit'](tmp_path)


@pytest.mark.parametrize('state',['missing','incorrect_metadata','valid'])
def test_image_audit_requires_declared_core_license(tmp_path,state):
    module=runpy.run_path(str(Path(__file__).parents[1]/'audit_runtime.py'))
    if state!='missing':
        metadata=tmp_path/'.venv/lib/python3.13/site-packages/czero_core-0.24.1.dist-info'
        (metadata/'licenses').mkdir(parents=True)
        (metadata/'licenses/LICENSE').write_bytes((Path(__file__).parents[2]/'LICENSE').read_bytes())
        (metadata/'METADATA').write_text('License-Expression: '+('unknown' if state=='incorrect_metadata' else 'GPL-3.0-or-later'))
    if state=='valid':module['audit_core_distribution'](tmp_path)
    else:
        with pytest.raises(SystemExit,match='Core runtime license'):
            module['audit_core_distribution'](tmp_path)


@pytest.mark.parametrize('change', ['valid', 'missing', 'extra', 'symlink', 'development_skill'])
def test_product_workflows_are_a_closed_runtime_allowlist(tmp_path, monkeypatch, change):
    module = runpy.run_path(str(Path(__file__).parents[1] / 'audit_runtime.py'))
    monkeypatch.setattr(module['importlib'].util, 'find_spec', lambda name: None)
    source = Path(__file__).parents[2] / 'plugins/c0-knowledge'
    product = tmp_path / 'agent-packages'
    paths = ['plugin.json', 'memory-skill.md', 'LICENSE',
             'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
             'skills/c0-maintain-knowledge/SKILL.md',
             'skills/c0-projects/SKILL.md',
             'references/connection.md', 'references/maintenance.md', 'references/projects.md']
    paths += ['project/'+name+'.md' for name in ('skill','workflows','daily','weekly','recovery','scheduler')]
    for name in paths:
        target = product / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / name if name != 'LICENSE' else source.parents[1] / name).read_bytes())
    if change == 'missing':
        (product / 'plugin.json').unlink()
    elif change == 'extra':
        (product / 'unexpected.txt').write_text('extra')
    elif change == 'symlink':
        (product / 'plugin.json').unlink()
        (product / 'plugin.json').symlink_to(source / 'plugin.json')
    elif change == 'development_skill':
        (tmp_path / 'SKILL.md').write_text('developer instructions')
    if change == 'valid':
        module['audit'](tmp_path)
    else:
        with pytest.raises(SystemExit, match='allowlist|Development files'):
            module['audit'](tmp_path)
