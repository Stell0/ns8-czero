# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import base64,json
import pytest
from czero_core.retrieval_config import RetrievalSettings,default_config,load_settings


def test_defaults_are_provider_free_and_never_construct_a_network_client(monkeypatch):
    monkeypatch.delenv('CZERO_RETRIEVAL_CONFIG_B64',raising=False)
    settings=load_settings()
    assert settings.clients()==(None,None) and settings.scorer_mode=='off' and settings.issue is None


def test_instance_settings_decode_only_private_environment_and_mask_keys(monkeypatch):
    value=default_config()
    value['embedding'].update(enabled=True,endpoint='https://embed.example.test/v1/embeddings',model='fixture',dimensions=3,api_key='unit-only-key')
    value['scorer'].update(mode='rerank',endpoint='https://score.example.test/v1/systemone',model='kev-mock',api_key='unit-only-score-key')
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64',base64.b64encode(json.dumps(value).encode()).decode())
    settings=load_settings()
    assert settings.embedding.model=='fixture' and settings.scorer.model=='kev-mock'
    assert 'unit-only' not in repr(settings)
    assert settings.clients()[0].settings.dimensions==3


@pytest.mark.parametrize('field,change',[
    ('embedding',{'enabled':'true'}),('embedding',{'enabled':True}),
    ('embedding',{'dimensions':2001}),('embedding',{'api_key':'bad\nkey'}),
    ('embedding',{'endpoint':0}),('embedding',{'model':False}),
    ('scorer',{'endpoint':None}),('scorer',{'model':[]}),
    ('scorer',{'mode':'shell'}),('scorer',{'mode':'filter'}),
    ('scorer',{'threshold':float('nan')}),('limits',{'max_limit':51}),
    ('limits',{'graph_depth':True}),('limits',{'arbitrary_url':'https://unknown.test'}),
])
def test_native_settings_have_strict_fields_and_safe_bounds(field,change):
    value=default_config();value[field].update(change)
    with pytest.raises(ValueError):RetrievalSettings.parse(value)


@pytest.mark.parametrize('raw',['not base64','A'*32769,base64.b64encode(b'[]').decode(),
    base64.b64encode(b'{"format":9}').decode(),base64.b64encode(b'\xff').decode()])
def test_corrupt_optional_configuration_fails_closed_with_usable_text_defaults(monkeypatch,raw):
    monkeypatch.setenv('CZERO_RETRIEVAL_CONFIG_B64',raw)
    settings=load_settings()
    assert settings.clients()==(None,None) and settings.issue=='retrieval_configuration_invalid'
