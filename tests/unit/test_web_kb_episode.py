"""Regression coverage for the live retrieval broker's pre-execution controls."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import web_kb_episode as episode


def test_public_web_boundary_after_kb_read():
    question = 'Where do I find the public release notes?'
    refs = {'turn52search3'}
    request = {'system2_search_query': [{'q': question}]}
    assert episode.web_allowed(request, True, question, refs)
    assert episode.web_allowed({'open': [{'ref_id': 'turn52search3'}]}, True, question, refs)
    for body in (
        {'system2_search_query': [{'q': question, 'domains': ['private.example']}]},
        {'system2_search_query': [{'q': 'FAQ answer'}]},
        {'open': [{'ref_id': 'https://example.org/FAQ-answer'}]},
        {'open': [{'ref_id': 'turn52search3', 'private': 'extra'}]},
        {'system2_search_query': [{'q': question}, {'q': question}]},
        {'find': [{'ref_id': 'turn52search3', 'pattern': 'private'}]},
    ):
        assert not episode.web_allowed(body, True, question, refs)


def test_live_catalog_is_fail_closed_and_read_only():
    class Broker:
        async def request(self, method, params):
            assert method == 'mcpServerStatus/list'
            return {'data': [{'name': 'codex_apps', 'tools': {name: {'inputSchema': {}}
                for name in ('kbnethesis.sources_archive', 'kbnethesis.knowledge_search',
                             'github.search', 'search_service.web_run')}}]}

    async def names(arm):
        return {row['name'] for row in await episode.catalog(Broker(), 'thread', arm)}

    assert asyncio.run(names('web-only')) == {episode.WEB}
    assert asyncio.run(names('web-plus-kb')) == {episode.WEB, 'kbnethesis_knowledge_search'}


def test_web_preflight_rejects_unresolved_url(monkeypatch):
    def fake(question, arm):
        return {'status': 'ok', 'usage': {'total_tokens': 1}, 'calls': [{
            'kind': 'web', 'name': episode.WEB, 'arguments': {'open': [{'ref_id': 'invalid'}]},
            'evidence': 'Open failed: https://github.com/NethServer/ns8-core', 'success': True}]}
    monkeypatch.setattr(episode, 'run_episode', fake)
    assert episode.run_preflight()['status'] == 'blocked'


def test_native_mcp_event_blocks_answering_process():
    async def check():
        stream = asyncio.StreamReader()
        stream.feed_data(json.dumps({"method": "item/started", "params": {
            "item": {"type": "mcpToolCall", "server": "unexpected", "tool": "read"}}}).encode() + b"\n")
        with pytest.raises(episode.Blocked, match="Unexpected native item"):
            await episode.RPC(SimpleNamespace(stdout=stream), broker=False).receive()

    asyncio.run(check())


def listing(rpc, name, method, *, identifier='call-1', result=None, arguments=None):
    rpc.check_discovery(method, {
        'id': identifier, 'tool': name, 'arguments': {} if arguments is None else arguments,
        'status': 'inProgress' if method == 'item/started' else 'completed', 'result': result,
    })


@pytest.mark.parametrize('tool,field', episode.DISCOVERY.items())
def test_verified_empty_native_listing_continues_and_matches_start(tool, field):
    rpc = episode.RPC(None, broker=False)
    result = {'content': [{'type': 'text', 'text': json.dumps({field: []})}]}
    with pytest.raises(episode.Blocked):
        listing(rpc, tool, 'item/started')
    rpc.native_catalog_empty = True
    with pytest.raises(episode.Blocked):
        listing(rpc, tool, 'item/completed', result=result)
    with pytest.raises(episode.Blocked):
        listing(rpc, tool, 'item/started', arguments={'server': 'foreign'})
    listing(rpc, tool, 'item/started')
    listing(rpc, tool, 'item/completed', result=result)
    assert not rpc.pending_discovery
    for result in (
        {'content': [{'type': 'text', 'text': json.dumps({field: [{'secret': 'sentinel'}]})}]},
        {'content': [{'type': 'text', 'text': json.dumps({field: [], 'cursor': 'more'})}]},
        {'content': [{'type': 'text', 'text': json.dumps({field: []})}], '_meta': {'x': 1}},
    ):
        listing(rpc, tool, 'item/started')
        with pytest.raises(episode.Blocked):
            listing(rpc, tool, 'item/completed', result=result)


def test_timeout_retains_partial_usage(monkeypatch):
    async def measure(question, arm, row):
        row['usage'].update(input_tokens=9, cached_input_tokens=3, total_tokens=10)
        raise TimeoutError

    monkeypatch.setattr(episode, 'measure', measure)
    result = episode.run_episode('public question', 'web-only')
    assert result['status'] == 'timeout'
    assert result['usage']['total_tokens'] is None
    assert result['partial_usage']['uncached_input_tokens'] == 6


def test_catalog_deferred_is_canonical_requires_real_operation(monkeypatch):
    monkeypatch.delenv('WEB_KB_CANDIDATE_CHANGES', raising=False)
    names = {'kbnethesis.spaces_list', 'kbnethesis.citations_get', 'search_service.web_run',
             'kbnethesis.documents_get', 'kbnethesis.knowledge_search', 'kbnethesis.sources_archive'}

    class Broker:
        async def request(self, method, params):
            return {'data': [{'name': 'codex_apps', 'tools': {n: {'inputSchema': {}} for n in names}}]}

    with pytest.raises(episode.Blocked, match='knowledge_search_compact'):
        asyncio.run(episode.catalog(Broker(), 't', episode.CANDIDATE))
    names.add('kbnethesis.knowledge_search_compact')
    defs = asyncio.run(episode.catalog(Broker(), 't', episode.CANDIDATE))
    routes = episode.catalog_routes(defs)
    assert len([1 for ns, _ in routes if ns is None]) == 4
    assert (None, episode.KB + 'knowledge_search_compact') in routes
    assert (episode.SPECIALISTS, episode.KB + 'documents_get') in routes
    assert (None, episode.KB + 'documents_get') not in routes
    assert not any(n.endswith('sources_archive') for _, n in routes)
    assert all(t['deferLoading'] for t in defs[-1]['tools'])


def test_routing_respects_explicit_selection_and_denial(monkeypatch):
    chosen = '5da87779-d956-4dda-bca1-98246b79b135'
    fallback = '69152d37-fbaa-4984-a28c-41e4ae02e6e5'
    monkeypatch.setenv('WEB_KB_START_SPACE', chosen)
    monkeypatch.setenv('WEB_KB_FALLBACK_SPACES', fallback)
    monkeypatch.setenv('WEB_KB_CANDIDATE_CHANGES', 'routing')
    search = episode.KB + 'knowledge_search'
    original = {'options': {'query': 'public'}}
    route = episode.SpaceRoute(episode.CANDIDATE)
    args, space, reject = route.arguments(search, original)
    assert not reject and space == args['options']['space_id'] == chosen
    assert 'space_id' not in original['options']
    explicit = {'options': {**original['options'], 'space_id': fallback}}
    assert route.arguments(search, explicit)[2]
    assert route.arguments(search, {'options': {'space_id': None}})[2]
    route.observe(search, chosen, '{"hits":[]}', True)
    assert route.arguments(search, explicit) == (explicit, fallback, None)
    route.observe(search, fallback, 'denied', False)
    assert route.arguments(search, original)[2]
    assert route.arguments(episode.KB + 'spaces_list', {})[2]
    override = episode.SpaceRoute(episode.CANDIDATE, selected_space=fallback)
    assert override.arguments(search, original)[1] == fallback and not override.fallbacks
    assert chosen not in episode.instructions(episode.CANDIDATE)
    baseline = episode.SpaceRoute('web-plus-kb')
    assert baseline.arguments(search, original)[2]
    assert baseline.arguments(search, explicit)[2]
    assert not baseline.arguments(search, args)[2]
    baseline.observe(search, chosen, '{"hits":[]}', True)
    assert not baseline.arguments(search, explicit)[2]
    monkeypatch.setenv('WEB_KB_CANDIDATE_CHANGES', 'compact')
    assert episode.SpaceRoute(episode.CANDIDATE).arguments(search, original)[2]


@pytest.mark.parametrize('rerank,expected', [('off', {'rerank': 'off'}), ('instance', {}),
                                             ('filter', {'rerank': 'filter'})])
def test_after_private_read_sentinel_never_reaches_public_connector(monkeypatch, rerank, expected):
    from contextlib import asynccontextmanager
    sentinel = 'secret-fixture-evidence'
    monkeypatch.setenv('WEB_KB_SEARCH_RERANK', rerank)
    public = 'Public launch question?'
    requests = []
    search = episode.KB + 'knowledge_search'
    events = []
    for name, args in (
        (search, {'options': {'query': public, 'rerank': 'rerank'}}),
        (episode.WEB, {'open': [{'ref_id': f'https://example.test/{sentinel}'}]}),
        (episode.WEB, {'system2_search_query': [{'q': sentinel}]}),
        (episode.WEB, {'system2_search_query': [{'q': public}]}),
    ):
        events.append({'method': 'item/tool/call', 'id': len(events),
                       'params': {'tool': name, 'arguments': args}})
    events.extend([
        {'method': 'thread/tokenUsage/updated', 'params': {'tokenUsage': {'total': {
            'inputTokens': 12, 'cachedInputTokens': 5, 'outputTokens': 3, 'totalTokens': 15}}}},
        {'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'phase': 'final_answer',
         'text': '{"answer":"done","citations":[]}'}}},
        {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}},
    ])

    class RPC:
        pending_discovery = {}
        async def receive(self):
            return events.pop(0)
        async def send(self, message):
            pass
        async def request(self, method, params):
            if method == 'mcpServer/tool/call':
                requests.append(params)
                body = sentinel if params['tool'].startswith('kbnethesis.') else 'public search result'
                return {'content': [{'type': 'text', 'text': body}]}
            if method == 'mcpServerStatus/list':
                return {'data': []}
            if method == 'thread/start':
                return {'model': episode.MODEL, 'thread': {'id': 't'}}
            assert method == 'turn/start'

    async def catalog(broker, thread, arm):
        options = {'properties': {'mode': {'enum': ['text']}, 'rerank': {'anyOf': [{'enum': ['off', 'filter']}]}}}
        return [{'type': 'function', 'name': name, 'inputSchema': {'properties': {'options': options}}}
                for name in [episode.WEB, search]]

    @asynccontextmanager
    async def server(broker, *, before_close=None):
        try:
            yield RPC()
        finally:
            before_close()
            # Deterministic evidence that process teardown is excluded from answer latency.
            clock.now += 4

    class Probe:
        async def communicate(self):
            return episode.VERSION.encode(), b''

    async def subprocess(*args, **kwargs):
        return Probe()

    clock = SimpleNamespace(now=0)
    def monotonic():
        clock.now += 0.001
        return clock.now
    monkeypatch.setattr(episode, 'time', SimpleNamespace(monotonic=monotonic))
    monkeypatch.setattr(episode, 'catalog', catalog)
    monkeypatch.setattr(episode, 'server', server)
    monkeypatch.setattr(episode.asyncio, 'create_subprocess_exec', subprocess)
    row = episode.run_episode(public, 'web-plus-kb')
    assert row['status'] == 'ok' and row['usage']['uncached_input_tokens'] == 7
    assert [call['forwarded'] for call in row['calls']] == [True, False, False, True]
    assert len(requests) == 2 and sentinel not in json.dumps(requests)
    assert requests[0]['arguments']['options'] == {'query': public, 'mode': 'text', **expected}
    assert row['calls'][0]['requested_arguments'] == {'options': {'query': public, 'rerank': 'rerank'}}
    assert row['calls'][0]['result_bytes'] == len(sentinel.encode())
    assert row['calls'][0]['completed_seconds'] >= row['calls'][0]['started_seconds'] >= row['setup_seconds']
    assert row['eager_schema_bytes'] == row['catalog_schema_bytes']
    assert row['seconds'] == row['final_answer_seconds']
    assert row['seconds'] >= row['calls'][-1]['completed_seconds']
    assert row['wall_seconds'] >= row['seconds'] + 8


def test_provider_pins_come_from_selected_operations_schema():
    name = episode.KB + 'knowledge_search'
    structured = episode.KB + 'knowledge_search_structured'
    with pytest.raises(episode.Blocked, match='mode/rerank'):
        episode.search_controls({(None, name): {'inputSchema': {'properties': {'options': {}}}}})
    options = {'properties': {'mode': {'enum': ['text']}, 'rerank': {'anyOf': [{'enum': ['off']}]}}}
    spec = {'$defs': {'SearchOptions': options}, 'properties': {'options': {'$ref': '#/$defs/SearchOptions'}}}
    routes = {(None, name): {'inputSchema': spec},
              (episode.SPECIALISTS, structured): {'inputSchema': {'properties': {'data': {}}}}}
    assert episode.search_controls(routes) == {name: True, structured: False}

def test_study_pagination_applies_after_eligibility(monkeypatch):
    chosen = '5da87779-d956-4dda-bca1-98246b79b135'
    monkeypatch.setenv('WEB_KB_START_SPACE', chosen)
    records = [{'id': str(i)} for i in range(100)] + [{'id': chosen}]
    class Broker:
        async def request(self, method, args):
            page = args['arguments']
            return {'structuredContent': {'spaces': records[page['offset']:page['offset']+page['limit']]}}
    route = episode.SpaceRoute('web-plus-kb')
    for offset, expected in [(0, [{'id':chosen}]), (1, [])]:
        trace = {}
        result = asyncio.run(route.discover(Broker(), {'arguments':{'limit':1,'offset':offset}}, trace))
        assert json.loads(result['content'][0]['text'])['spaces'] == expected
        assert [p['offset'] for p in trace['backend_pages']] == [0,100]


def test_tool_free_grader_checks_native_catalog_before_inference(monkeypatch):
    from contextlib import asynccontextmanager
    import web_kb_prepare as prepare
    class ReviewRPC:
        native_catalog_empty = False
        pending_discovery = {}
        def __init__(self):
            self.catalog = []
            self.events = [
                {'method':'item/completed','params':{'item':{'type':'agentMessage','phase':'final_answer','text':'{}'}}},
                {'method':'turn/completed','params':{'turn':{'status':'completed'}}}]
        async def request(self,method,params):
            if method == 'mcpServerStatus/list':
                return {'data':self.catalog}
            assert method == 'turn/start' and self.native_catalog_empty
        async def receive(self):
            return self.events.pop(0)
    rpc=ReviewRPC()
    @asynccontextmanager
    async def server(broker):
        assert not broker
        yield rpc
    async def thread(*args, **kwargs):
        return 't'
    monkeypatch.setattr(prepare,'server',server)
    monkeypatch.setattr(prepare,'start_thread',thread)
    assert asyncio.run(prepare.inference('fixture','Grade',{},{})) == {}
    rpc.catalog = ['unexpected']
    with pytest.raises(episode.Blocked,match='Unexpected native catalog'):
        asyncio.run(prepare.inference('fixture','Grade',{},{}))
