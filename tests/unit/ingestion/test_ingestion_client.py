# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import copy
import pytest
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from github_vault.bootstrap import check_type, schema
from github_vault.c0_client import C0 as GitHubC0
from c0_ingest.state import atomic


class Transport:
    def __init__(self, *, shared=False, role='editor', account='account', space='target'):
        self.calls = []
        self.closed = False
        self.profile = {'id': account, 'nickname': 'alice'}
        self.space = {'id': space, 'name': 'Selected knowledge', 'shared': shared, 'role': role}
        self.operations = [
            {'name': 'get_profile', 'read_only': True, 'input_schema': {'properties': {}}},
            {'name': 'spaces_get', 'read_only': True, 'input_schema': {'properties': {'space_id': {}}}},
            {'name': 'sources_ingest_text', 'read_only': False, 'input_schema': {'properties': {'space_id': {}}}},
            {'name': 'spaces_create', 'read_only': False, 'input_schema': {'properties': {}}},
            {'name': 'knowledge_search', 'read_only': True, 'input_schema': {'properties': {'options': {}}}},
        ]

    def resource(self, uri):
        assert uri == 'c0://capabilities'
        return {'operations': copy.deepcopy(self.operations)}

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        result = self.profile if name == 'get_profile' else self.space
        return {'structuredContent': copy.deepcopy(result)}

    def close(self):
        self.closed = True


def config():
    return {'url': 'https://c0.example.org/mcp', 'account_id': 'account', 'identity': 'alice',
            'space_id': 'target', 'space_name': 'Selected knowledge'}


def test_wrong_account_closes_before_content_operations():
    transport = Transport(account='another-account')
    with pytest.raises(C0Error, match='account'):
        C0(config(), transport=transport)
    assert transport.closed and [n for n, _ in transport.calls] == ['get_profile']


@pytest.mark.parametrize('shared,role', [(True, 'admin'), (False, 'reader')])
def test_shared_and_reader_targets_fail_without_writes(shared, role):
    transport = Transport(shared=shared, role=role)
    client = C0(config(), transport=transport)
    with pytest.raises(C0Error, match='protected'):
        client.select_space('target')
    assert client.space_id is None and client.writes == 0


def test_every_write_and_nested_search_has_exact_selected_space():
    transport = Transport()
    client = C0(config(), transport=transport)
    with pytest.raises(C0Error, match='space_id'):
        client.call('sources_ingest_text', data={})
    client.select_space('target')
    for name, args in [('sources_ingest_text', {'space_id': 'other', 'data': {}}),
                       ('knowledge_search', {'options': {'space_id': 'other'}}),
                       ('spaces_create', {'data': {}})]:
        with pytest.raises(C0Error):
            client.call(name, **args)
    assert client.writes == 0
    client.call('sources_ingest_text', data={})
    assert transport.calls[-1][1]['space_id'] == 'target'


def test_saved_job_cannot_switch_destination_or_account(tmp_path):
    state = tmp_path / 'space.json'
    atomic(state, {'identity_id': 'account', 'space_id': 'original'})
    transport = Transport()
    client = GitHubC0(config(), transport=transport)
    with pytest.raises(C0Error, match='refusing replacement'):
        client.resolve_space(state)
    assert [n for n, _ in transport.calls] == ['get_profile']


def test_tool_errors_do_not_echo_secrets():
    with pytest.raises(C0Error) as exc:
        C0.decode('sources_ingest_text', {'isError': True, 'content': [{'type': 'text', 'text': 'synthetic-private-payload'}]})
    assert 'synthetic-private-payload' not in str(exc.value)


def test_known_tool_error_preserves_safe_reason_and_recovery():
    with pytest.raises(C0Error, match='insufficient_scope.*inspect authority'):
        C0.decode('sources_ingest_text', {'isError': True, 'content': [{'type': 'text', 'text': 'insufficient_scope'}]})


def test_incompatible_types_are_never_modified():
    valid = {'schema': schema(), 'unique_fields': ['external_key']}
    check_type(valid)
    invalid = copy.deepcopy(valid)
    invalid['schema']['properties']['github_id']['type'] = 'string'
    with pytest.raises(C0Error, match='incompatible'):
        check_type(invalid)
    assert invalid['schema']['properties']['github_id']['type'] == 'string'
