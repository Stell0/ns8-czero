# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_supported_node_log_level_is_set_before_browser_subprocess(monkeypatch):
    monkeypatch.setenv('ROBOT_FRAMEWORK_BROWSER_PINO_LOG_LEVEL','info')
    configure=runpy.run_path(str(ROOT/'browser_privacy.py'))['configure_browser_diagnostics']
    configure()
    import os
    assert os.environ['ROBOT_FRAMEWORK_BROWSER_PINO_LOG_LEVEL']=='silent'


@pytest.mark.parametrize('query', ['state=private-fixture-value', 'nonce=private-fixture-value',
    'code_challenge=private-fixture-value', 'code=private-fixture-value',
    'access_token=private-fixture-value', 'id_token=private-fixture-value', 'refresh_token=private-fixture-value'])
def test_browser_response_diagnostics_cannot_publish_oauth_query_values(tmp_path, query):
    check=runpy.run_path(str(ROOT/'browser_privacy.py'))['assert_no_oauth_queries']
    path=tmp_path/'playwright-log.txt'
    path.write_text('{"msg":"currentBrowser: {\\"location\\":\\"https://idp.example.test/auth?'+query+'\\"}"}')
    with pytest.raises(AssertionError,match='^OAuth query values entered browser test output$') as error:
        check([path])
    assert 'private-fixture-value' not in str(error.value)


def test_xml_escaped_oauth_query_is_rejected(tmp_path):
    check = runpy.run_path(str(ROOT / 'browser_privacy.py'))['assert_no_oauth_queries']
    path = tmp_path / 'output.xml'
    path.write_text('<arg>https://idp.example.test/auth?client_id=public&amp;state=private-fixture-value</arg>')
    with pytest.raises(AssertionError, match='^OAuth query values entered browser test output$'):
        check([path])


def test_browser_assertions_and_safe_api_diagnostics_remain_available(tmp_path):
    check=runpy.run_path(str(ROOT/'browser_privacy.py'))['assert_no_oauth_queries']
    path=tmp_path/'output.xml';path.write_text('PASS objects_get; GET /api/v1/me HTTP/1.1')
    check([path,tmp_path/'missing-log.txt'])


def test_retained_action_and_dom_traces_redact_one_time_keys():
    import json
    import secrets
    scrub = runpy.run_path(str(ROOT/'browser_privacy.py'))['redact_api_keys']
    keys = ['c0k_'+secrets.token_urlsafe(32) for _ in range(2)]
    trace = json.dumps({'input_value':keys[0], 'snapshot':{'value':keys[1]}, 'title':'Workflow'}).encode()
    cleaned = scrub(trace)
    assert all(key.encode() not in cleaned for key in keys)
    value = json.loads(cleaned)
    assert value['input_value'] == value['snapshot']['value'] == '<redacted-api-key>'
    assert value['title'] == 'Workflow'
