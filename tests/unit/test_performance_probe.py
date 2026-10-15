# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location('performance_probe', Path(__file__).parents[1] / 'performance_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
PAGE = {'id': 'page-fixture', 'content': {'id': 'revision-fixture'}}


class Browser:
    def __init__(self, *, delay=.01, fault=None):
        self.now = 0
        self.delay = delay
        self.fault = fault
        self.paths = []

    def api(self, path):
        self.paths.append(path)
        self.now += self.delay
        if path.startswith('/api/v1/wiki/pages'):
            value = {'pages': [{}] * (100 if self.fault == 'corpus' else 4)}
        elif path.endswith('health'):
            value = {'status': 'unavailable' if self.fault == 'health' else 'ok', 'service': 'czero'}
        else:
            value = {'retrieval_method': 'hybrid' if self.fault == 'mode' else 'text', 'fallback_reason': None,
                     'hits': [{'id': PAGE['content']['id'], 'resource_id': PAGE['id'],
                               'wiki': {'revision': 1 if self.fault == 'revision' else 2}}]}
        if self.fault == 'private':
            return 403, b'private fixture content', 'private fixture URL'
        if self.fault == 'json':
            return 200, b'private fixture content', 'private fixture URL'
        if self.fault == 'large':
            return 200, b'x' * (1024**2 + 1), ''
        return 200, json.dumps(value).encode(), ''


def test_measures_real_protocol_samples_and_only_returns_numbers():
    browser = Browser()
    result = probe.measure(browser, PAGE, clock=lambda: browser.now)
    assert result['visible_wiki_pages'] == 4
    assert result['health'] == {'requests': 50, 'warmups': 2, 'p95_ms': 10.0, 'maximum_ms': 10.0, 'mean_ms': 10.0}
    assert result['wiki_text_search']['requests'] == 20
    assert len(browser.paths) == 75
    assert all('mode=text' in path and 'rerank=off' in path for path in browser.paths if '/search?' in path)
    assert 'fixture' not in json.dumps(result)


@pytest.mark.parametrize('fault', ['health', 'mode', 'revision', 'private', 'json', 'large', 'corpus'])
def test_rejects_wrong_authority_evidence_or_unbounded_measurements(fault):
    browser = Browser(fault=fault)
    with pytest.raises(AssertionError) as error:
        probe.measure(browser, PAGE, clock=lambda: browser.now)
    assert 'private fixture' not in str(error.value)


def test_rejects_a_slow_service_and_an_overall_timeout():
    for delay, message in [(.6, 'p95 target exceeded'), (16, 'deadline exceeded')]:
        browser = Browser(delay=delay)
        with pytest.raises(AssertionError, match=message):
            probe.measure(browser, PAGE, clock=lambda: browser.now)
