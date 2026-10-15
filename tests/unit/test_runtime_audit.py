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
