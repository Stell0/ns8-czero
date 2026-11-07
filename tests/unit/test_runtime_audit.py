# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize('suffix', ['.h', '.pxd', '.pxi', '.pyx'])
def test_image_audit_rejects_extension_build_sources(tmp_path, monkeypatch, suffix):
    module = runpy.run_path(str(Path(__file__).parents[1] / 'audit_runtime.py'))
    monkeypatch.setattr(module['importlib'].util, 'find_spec', lambda name: None)
    website_fixture(tmp_path / 'frontend')
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
    website_fixture(tmp_path / 'frontend')
    source = Path(__file__).parents[2] / 'plugins/c0-knowledge'
    product = tmp_path / 'agent-packages'
    paths = ['plugin.json', 'memory-skill.md', 'LICENSE',
             'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
             'skills/c0-maintain-knowledge/SKILL.md',
             'skills/c0-projects/SKILL.md', 'skills/c0-knowledge-compiler/SKILL.md', 'references/compiler.md', 'references/scheduling.md',
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


@pytest.mark.parametrize('change', ['valid', 'missing', 'source', 'traversal', 'symlink'])
def test_compiled_website_inventory_is_closed(tmp_path, change):
    import json
    module=runpy.run_path(str(Path(__file__).parents[1]/'audit_runtime.py'))
    root=tmp_path/'frontend'
    manifest=website_fixture(root)
    if change=='missing':(root/'vendor/poppins-LICENSE').unlink()
    elif change=='source':(root/'assets/App.vue').write_text('<template>source</template>')
    elif change=='traversal':manifest['index.html']['file']='../unexpected.js'
    elif change=='symlink':
        (root/'assets/index-fixture.js').unlink()
        (root/'assets/index-fixture.js').symlink_to(root/'index.html')
    (root/'.vite/manifest.json').write_text(json.dumps(manifest))
    if change=='valid':module['audit_website'](root)
    else:
        with pytest.raises(SystemExit,match='allowlist'):module['audit_website'](root)


def website_fixture(root):
    import json
    paths=['index.html','.vite/manifest.json','markdown-worker.js','vendor/markdown-it-15.0.2.min.js',
           'vendor/markdown-it-LICENSE','vendor/poppins-LICENSE','vendor/poppins-latin-400-normal.woff2',
           'vendor/poppins-latin-500-normal.woff2','vendor/third-party-notices.txt','assets/index-fixture.js','assets/index-fixture.css']
    for name in paths:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    manifest={'index.html':{'file':'assets/index-fixture.js','isEntry':True,'css':['assets/index-fixture.css']}}
    (root/'.vite/manifest.json').write_text(json.dumps(manifest))
    return manifest


def test_runtime_requires_compiled_website(tmp_path, monkeypatch):
    module=runpy.run_path(str(Path(__file__).parents[1]/'audit_runtime.py'))
    monkeypatch.setattr(module['importlib'].util, 'find_spec', lambda name: None)
    with pytest.raises(SystemExit,match='Compiled website assets are missing'):
        module['audit'](tmp_path)
