# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
import hashlib
import json
import pytest

from czero_core.embedding_context import contextual_input
from czero_core.embeddings import profile_identity
from czero_core.providers import EmbeddingSettings
from czero_core.retrieval_config import default_config,RetrievalSettings


def test_context_is_recorded_metadata_and_original_headings_not_replacement_evidence():
    original='# Configuration\n\n## Recovery\n\nRun the verified procedure.'
    body='Run the verified procedure.'
    row={'body':body,'start_offset':original.index(body),'document_body':original,
         'title':'Firewall manual','media_type':'text/markdown',
         'metadata':{'provenance':{'product':'ACME firewall','product_version':'8'}}}
    value=contextual_input(row)
    assert value.endswith('\n'+body)
    assert 'product: ACME firewall' in value and 'product_version: 8' in value
    assert 'title: Firewall manual' in value and '# Configuration > ## Recovery' in value
    assert row['body']==body
    changed=contextual_input({**row,'title':'New title'})
    assert hashlib.sha256(value.encode()).digest()!=hashlib.sha256(changed.encode()).digest()


def test_context_is_bounded_and_missing_metadata_is_not_invented():
    assert contextual_input({'body':'plain evidence'})=='plain evidence'
    for length in [1200,3800,4096]:
        body='字'*length
        value=contextual_input({'body':body,'title':'Title '*1000,'metadata':{'provenance':[]}})
        assert value.endswith(body) and len(value)<=4096
        assert 'product:' not in value


def test_input_format_changes_profile_but_preserves_legacy_identity_and_credentials_binding():
    settings=EmbeddingSettings('https://embedding.example.test/v1','fixture',dimensions=3)
    raw=json.dumps({'endpoint':settings.endpoint,'model':settings.model,'dimensions':3,
                    'send_dimensions':False},sort_keys=True,separators=(',',':'))
    assert profile_identity(settings)[1]==hashlib.sha256(raw.encode()).hexdigest()
    assert profile_identity(settings)==profile_identity(replace(settings,api_key='rotated'))
    assert profile_identity(settings)!=profile_identity(replace(settings,input_format='context-v1'))


def test_old_native_configs_remain_legacy_and_context_requires_explicit_selection():
    config=default_config();config['embedding'].pop('input_format',None)
    config['embedding'].update(enabled=True,endpoint='https://embedding.example.test/v1',model='fixture')
    assert RetrievalSettings.parse(config).embedding.input_format=='legacy'
    config['embedding']['input_format']='context-v1'
    assert RetrievalSettings.parse(config).embedding.input_format=='context-v1'
    config['embedding']['input_format']='generated-context'
    with pytest.raises(ValueError):RetrievalSettings.parse(config)
