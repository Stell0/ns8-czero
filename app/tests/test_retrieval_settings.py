# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
from czero_core.retrieval_config import load_settings, default_config
from czero_app.job_handlers import build_registry


def test_api_worker_registry_load_same_native_configuration(monkeypatch, tmp_path):
    value = default_config()
    value['embedding'].update(enabled=True, endpoint='https://provider.example.test/v1/embeddings',
                              model='fixture-model', dimensions=3, api_key='fixture-private-key')
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64', base64.b64encode(json.dumps(value).encode()).decode())
    settings = load_settings()
    assert settings.embedding.dimensions == 3
    assert settings.embedding.api_key == 'fixture-private-key'
    assert 'fixture-private-key' not in repr(settings)
    monkeypatch.setenv('CZERO_SOURCE_DIR', str(tmp_path))
    # Standalone worker has no database until Worker invokes each handler with
    # its transaction; construction must load settings without network calls.
    registry = build_registry()
    assert registry.get('embedding.index') is not None
    assert registry.get('embedding.reindex') is not None


def test_corrupt_optional_settings_preserve_default_text_policy(monkeypatch):
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64', 'broken')
    settings = load_settings()
    assert settings.embedding is None and settings.scorer is None
    assert settings.issue == 'retrieval_configuration_invalid'
