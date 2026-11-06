# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the actual production package roots and container COPY inputs exclude BEIR."""
from pathlib import Path
import shlex
import tomllib

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_distributions_do_not_include_benchmark():
    for directory in ('app', 'packages/czero-core'):
        package = ROOT / directory
        metadata = tomllib.loads((package / 'pyproject.toml').read_text())
        assert metadata['tool']['setuptools']['packages']['find']['where'] == ['src']
        assert not any('beir' in dependency or 'ingestion' in dependency or 'pytrec' in dependency
                       for dependency in metadata['project']['dependencies'])
        assert not list((package / 'src').rglob('*beir*'))
        assert not list((package / 'src').rglob('*benchmark*'))
    plugin = ROOT / 'plugins/c0-knowledge'
    assert not list(plugin.rglob('*beir*'))
    assert not list(plugin.rglob('*benchmark*'))


def test_production_copy_rules_never_include_benchmark():
    containerfiles = list((ROOT / 'containers').glob('*/Containerfile')) + [ROOT / 'ui/Containerfile']
    # The NS8 module image is assembled separately by build-images.sh.
    text = (ROOT / 'build-images.sh').read_text()
    assert 'buildah add "${container}" imageroot /imageroot' in text
    assert 'buildah add "${container}" ui/dist /ui' in text
    assert 'benchmarks' not in text
    for path in containerfiles:
        lines = path.read_text().replace('\\\n', ' ').splitlines()
        for line in lines:
            if not line.startswith('COPY '):
                continue
            words = shlex.split(line)
            if any(word.startswith('--from=') for word in words):
                continue
            sources = [word for word in words[1:-1] if not word.startswith('--')]
            for source in sources:
                assert source not in ('.', './', '/', '*')
                assert not source.startswith(('benchmarks', 'samples', 'tests'))
        assert 'c0-beir' not in path.read_text()


def test_private_state_and_venv_are_ignored():
    ignore = (ROOT / '.gitignore').read_text().splitlines()
    assert '.local/benchmark/' in ignore and '.venv-benchmark/' in ignore
