# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import pytest
from czero_core.retrieval_config import RetrievalSettings, default_config

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def native(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / 'imageroot/bin'))
    monkeypatch.setenv('AGENT_INSTALL_DIR', str(ROOT / 'imageroot'))
    monkeypatch.setenv('AGENT_STATE_DIR', str(tmp_path))
    monkeypatch.setitem(sys.modules, 'agent', SimpleNamespace(
        safe_open=lambda path: open(path, 'w'), set_status=lambda status: None))
    from czero_retrieval_config import defaults, read, merge, public
    return tmp_path, SimpleNamespace(defaults=defaults, read=read, merge=merge, public=public)


def step(monkeypatch, name, data=None):
    monkeypatch.setattr(sys, 'stdin', StringIO(json.dumps(data)))
    runpy.run_path(str(ROOT / 'imageroot' / name))


def test_private_settings_roundtrip_runtime_contract(native, monkeypatch, capsys):
    state, config = native
    assert config.defaults() == default_config()
    step(monkeypatch, 'bin/czero-create-retrieval-state')
    patch = {'embedding': {'enabled': True, 'endpoint': 'https://embedding.example.test/v1/embeddings',
                          'model': 'fixture', 'dimensions': 3, 'api_key': 'private-fixture-key'}}
    step(monkeypatch, 'actions/configure-module/12validate-retrieval', {'retrieval': patch})
    assert config.read(state / 'retrieval.env')['embedding']['enabled'] is False
    assert (state / 'retrieval-pending.env').stat().st_mode & 0o777 == 0o600
    step(monkeypatch, 'actions/configure-module/35persist-retrieval')
    value = config.read(state / 'retrieval.env')
    assert RetrievalSettings.parse(value).embedding.api_key == 'private-fixture-key'
    assert (state / 'retrieval.env').stat().st_mode & 0o777 == 0o600
    assert not (state / 'retrieval-pending.env').exists()
    safe = config.public(value)
    assert safe['embedding']['api_key_configured'] is True
    assert 'private-fixture-key' not in json.dumps(safe)
    assert capsys.readouterr().out == ''


def test_secret_preserve_clear_rotate_and_endpoint_change(native):
    _, config = native
    previous = config.merge(config.defaults(), {'embedding': {'endpoint': 'https://a.example.test/',
                            'model': 'fixture', 'api_key': 'old-fixture-key'}})
    assert config.merge(previous, {'embedding': {'api_key': ''}})['embedding']['api_key'] == 'old-fixture-key'
    assert config.merge(previous, {'embedding': {'clear_api_key': True}})['embedding']['api_key'] == ''
    assert config.merge(previous, {'embedding': {'endpoint': 'https://b.example.test/'}})['embedding']['api_key'] == ''
    rotated = config.merge(previous, {'embedding': {'endpoint': 'https://b.example.test/', 'api_key': 'new-fixture-key'}})
    assert rotated['embedding']['api_key'] == 'new-fixture-key'
    with pytest.raises(ValueError):
        config.merge(previous, {'embedding': {'clear_api_key': True, 'api_key': 'contradictory'}})


@pytest.mark.parametrize('patch', [
    {'embedding': {'enabled': True}}, {'embedding': {'endpoint': 'http://bad.test/', 'model': 'x'}},
    {'embedding': {'endpoint': 'https://user:secret@bad.test/', 'model': 'x'}},
    {'embedding': {'endpoint': 'https://good.test/?secret=x', 'model': 'x'}},
    {'embedding': {'dimensions': 2001}}, {'embedding': {'api_key': 'bad\nkey'}},
    {'scorer': {'timeout': True}}, {'scorer': {'threshold': float('nan')}},
    {'limits': {'max_limit': 50, 'candidates': 49}}, {'limits': {'graph_depth': 4}},
    {'limits': {'scorer_candidates': 17}}, {'unknown': {}},
])
def test_validation_error_keeps_existing_private_file_and_redacts(native, monkeypatch, capsys, patch):
    state, _ = native
    step(monkeypatch, 'bin/czero-create-retrieval-state')
    before = (state / 'retrieval.env').read_bytes()
    with pytest.raises(SystemExit) as error:
        step(monkeypatch, 'actions/configure-module/12validate-retrieval', {'retrieval': patch})
    assert error.value.code == 2
    assert (state / 'retrieval.env').read_bytes() == before
    assert not (state / 'retrieval-pending.env').exists()
    assert json.loads(capsys.readouterr().out) == [{'field': 'retrieval', 'parameter': 'retrieval',
                                                'error': 'invalid_retrieval_configuration'}]


def test_upgrade_restore_keep_settings_and_restrict_mode(native, monkeypatch):
    state, config = native
    step(monkeypatch, 'bin/czero-create-retrieval-state')
    before = (state / 'retrieval.env').read_bytes()
    (state / 'retrieval.env').chmod(0o644)
    step(monkeypatch, 'bin/czero-create-retrieval-state')
    assert (state / 'retrieval.env').read_bytes() == before
    assert (state / 'retrieval.env').stat().st_mode & 0o777 == 0o600
    (state / 'retrieval.env').write_text('broken-private-state')
    with pytest.raises(SystemExit, match='Invalid private retrieval configuration'):
        step(monkeypatch, 'bin/czero-create-retrieval-state')
    assert (state / 'retrieval.env').read_text() == 'broken-private-state'
