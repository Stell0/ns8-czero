# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
from types import SimpleNamespace

import pytest
import jsonschema
from pathlib import Path
from czero_app import runtime_check
from czero_core.retrieval_config import default_config

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('ready', [True, False])
def test_runtime_diagnostic_reuses_health_closes_and_never_exposes_descriptors(monkeypatch, ready):
    config=default_config()
    config['embedding'].update(enabled=True, endpoint='https://private-provider.test/api', model='pinned', api_key='private-key-value')
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64',base64.b64encode(json.dumps(config).encode()).decode())
    closed=[]
    health={'status':'ok','schema_revision':'0013_oauth_consent','vector_version':'0.8.7'} if ready else {'status':'unavailable','reason':'database_unavailable'}
    monkeypatch.setattr(runtime_check,'Database',lambda:SimpleNamespace(health=lambda:health,close=lambda:closed.append(True)))
    result=runtime_check.status()
    assert result['database']==health and closed==[True]
    assert result['retrieval']=={'configuration_valid':True,'embeddings_configured':True,'scorer_mode':'off'}
    encoded=json.dumps(result)
    assert 'private-provider' not in encoded and 'private-key-value' not in encoded and 'pinned' not in encoded
    jsonschema.validate(result,json.loads((ROOT/'imageroot/actions/get-runtime-status/validate-output.json').read_text()))


def test_runtime_bad_database_and_optional_settings_fail_closed(monkeypatch):
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64','invalid-private-value')
    monkeypatch.setattr(runtime_check,'Database',lambda:(_ for _ in ()).throw(ValueError('private-database-url')))
    result=runtime_check.status()
    assert result['database']=={'status':'unavailable','reason':'database_configuration_invalid'}
    assert result['retrieval']=={'configuration_valid':False,'embeddings_configured':False,'scorer_mode':'off'}
    assert 'private' not in json.dumps(result)
