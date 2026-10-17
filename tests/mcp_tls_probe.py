# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Git-only installed SDK client, fed private JSON on stdin inside the app.

Route only the synthetic application vhost to the disposable node gateway.
TLS/SNI/Host/resource identities stay canonical; provider DNS is untouched.
"""
import asyncio
import hashlib
import json
import ssl
import sys
from urllib.parse import urlsplit
from uuid import uuid4

import httpcore2
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


class ApplicationRoute(httpcore2.AsyncNetworkBackend):
    def __init__(self, host, address):
        self.host, self.address, self.backend = host, address, httpcore2.AnyIOBackend()

    async def connect_tcp(self, host, port, **options):
        return await self.backend.connect_tcp(self.address if host == self.host else host, port, **options)

    async def connect_unix_socket(self, path, **options):
        return await self.backend.connect_unix_socket(path, **options)

    async def sleep(self, seconds):
        await self.backend.sleep(seconds)


class ResponseBody(httpx2.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        async for part in self.stream:
            yield part

    async def aclose(self):
        await self.stream.aclose()


class NodeTransport(httpx2.AsyncBaseTransport):
    def __init__(self, host, address, ca):
        self.pool = httpcore2.AsyncConnectionPool(ssl_context=ssl.create_default_context(cafile=ca),
            network_backend=ApplicationRoute(host, address))

    async def handle_async_request(self, request):
        response = await self.pool.handle_async_request(httpcore2.Request(method=request.method,
            url=httpcore2.URL(scheme=request.url.raw_scheme, host=request.url.raw_host,
                port=request.url.port, target=request.url.raw_path), headers=request.headers.raw,
            content=request.stream, extensions=request.extensions))
        return httpx2.Response(response.status, headers=response.headers,
            stream=ResponseBody(response.stream), extensions=response.extensions)

    async def aclose(self):
        await self.pool.aclose()


async def typed_objects(client):
    """Disposable-only typed lifecycle through the real installed MCP wire."""
    name = 'robot-regression-' + uuid4().hex
    schema = {'type':'object','required':['name','manufacturer'],'properties':{
        'name':{'type':'string','maxLength':128}, 'manufacturer':{'type':'string'},
        'category':{'type':'string'}, 'source_url':{'type':'string'}},'additionalProperties':False}
    async def call(operation, arguments, error=None, status=None):
        result = await client.call_tool(operation, arguments)
        assert result.is_error == bool(error), 'Installed typed operation error state mismatch'
        if error:
            assert result.content[0].text == error, 'Installed typed validation/conflict code mismatch'
            assert result.meta['c0/error'] == {'code':error,'status':status}, 'Installed typed error metadata mismatch'
        else:
            assert json.loads(result.content[0].text) == result.structured_content, 'Installed typed result representations differ'
            return result.structured_content
    descriptor = {'name':name,'label':'Disposable typed CRUD','schema':schema,'unique_fields':['name']}
    await call('object_types_create', {'data':{**descriptor,'schema':{
        'type':'object','properties':{'name':{'type':'string'}}}}}, 'unique_string_too_long', 422)
    await call('object_types_create', {'data':{**descriptor,'schema':{'type':'array'}}}, 'invalid_schema', 422)
    created = await call('object_types_create', {'data':descriptor})
    assert created['schema']['properties']['name']['maxLength'] == 128, 'Installed unique schema changed'
    assert await call('object_types_get', {'type_name':name}) == created, 'Installed typed schema retrieval mismatch'
    assert created in (await call('object_types_list', {'limit':100}))['types'], 'Installed new type not discoverable'
    await call('object_types_create', {'data':descriptor}, 'object_conflict', 409)
    record = {'name':'Digit 5','manufacturer':'Disposable fixture','source_url':'https://example.invalid/fixture'}
    row = await call('objects_create', {'data':{'type_name':name,'data':record}})
    assert row['revision'] == 1 and row['data'] == record, 'Installed typed create mismatch'
    assert await call('objects_get', {'object_id':row['id']}) == row, 'Installed typed read mismatch'
    query = {'type_name':name,'where':json.dumps({'name':'Digit 5'})}
    assert (await call('objects_list', query))['objects'] == [row], 'Installed typed query mismatch'
    await call('objects_create', {'data':{'type_name':name,'data':record}}, 'object_conflict', 409)
    updated = await call('objects_update', {'object_id':row['id'],
        'data':{'expected_revision':1,'data':{**record,'category':'updated'}}})
    assert updated['revision'] == 2 and updated['data']['category'] == 'updated', 'Installed typed update mismatch'
    await call('objects_update', {'object_id':row['id'],
        'data':{'expected_revision':1,'data':record}}, 'object_conflict', 409)
    for data, error in [({'name':'Missing'},'record_invalid::required'),
            ({**record,'name':42},'record_invalid:name:type'),
            ({**record,'extra':'ignored?'},'record_invalid::additionalProperties')]:
        await call('objects_create', {'data':{'type_name':name,'data':data}}, error, 422)
    assert await call('objects_get', {'object_id':row['id']}) == updated, 'Installed failed write changed record'
    deleted = await call('objects_delete', {'object_id':row['id'],'expected_revision':2})
    assert deleted == {'id':row['id'],'revision':2,'deleted':True}, 'Installed typed delete mismatch'
    await call('objects_get', {'object_id':row['id']}, 'object_not_found', 404)
    assert (await call('objects_list', {'type_name':name}))['objects'] == [], 'Installed typed deletion incomplete'
    # Type definitions and their audit history are immutable; the disposable
    # installation owns their lifecycle. No direct database cleanup is used.


async def text_evidence(client, http, previous=None):
    """One real timer extraction, then replay/read it in both SDK protocol modes."""
    data = previous['request'] if previous else {'title':'HTTP Wiki evidence '+uuid4().hex,
        'body':'Selected MCP memory evidence café 東京', 'media_type':'text/markdown',
        'metadata':{'origin':'disposable SDK investigation'}, 'idempotency_key':'sdk-text-'+uuid4().hex}
    response = await client.call_tool('sources_ingest_text', {'data':data})
    assert not response.is_error, 'Installed SDK text ingestion failed'
    receipt = response.structured_content
    assert receipt['state'] == 'queued', 'Installed new text receipt claimed extraction completion'
    assert receipt['content_hash'] == hashlib.sha256(data['body'].encode()).hexdigest(), 'Installed text receipt hash mismatch'
    if previous:
        assert receipt == previous['receipt'], 'Installed SDK text replay changed receipt'
    deadline = asyncio.get_running_loop().time()+75
    while True:
        versions = await client.call_tool('source_versions_list', {'source_id':receipt['source_id']})
        assert not versions.is_error, 'Installed text version lookup failed'
        version = next(v for v in versions.structured_content['versions'] if v['id']==receipt['id'])
        if version['state'] == 'ready':
            break
        assert version['state'] == 'queued', 'Installed text extraction failed'
        assert asyncio.get_running_loop().time() < deadline, 'Installed text extraction did not finish'
        await asyncio.sleep(1)
    document = await client.call_tool('documents_get', {'version_id':receipt['id']})
    assert not document.is_error and document.structured_content['body']==data['body'], 'Installed text document mismatch'
    chunks = await client.call_tool('document_chunks_list', {'document_id':document.structured_content['id']})
    assert not chunks.is_error and chunks.structured_content['chunks'], 'Installed text chunks unavailable'
    chunk = chunks.structured_content['chunks'][0]
    citation = await client.call_tool('citations_get', {'chunk_id':chunk['id']})
    assert not citation.is_error, 'Installed text citation unavailable'
    citation = citation.structured_content
    assert citation['version_id']==receipt['id'] and citation['source_hash']==receipt['content_hash'], 'Installed text provenance mismatch'
    rest = await http.post('/api/v1/sources/ingest-text', json=data)
    assert rest.status_code==202 and rest.json()==receipt, 'Installed text REST/MCP replay differs'
    conflict = await http.post('/api/v1/sources/ingest-text', json={**data,'body':'Conflicting retry'})
    assert conflict.status_code==409, 'Installed text replay accepted changed content'
    if previous:
        assert document.structured_content==previous['document'] and citation==previous['citation'], 'Installed evidence changed across SDK sessions'
        claim_id = previous['claim_id']
    else:
        entity = await client.call_tool('entities_create', {'data':{'kind':'system','label':'SDK evidence '+uuid4().hex,
            'idempotency_key':'sdk-entity-'+uuid4().hex}})
        assert not entity.is_error, 'Installed evidence entity creation failed'
        claim = await client.call_tool('claims_create', {'data':{'entity_id':entity.structured_content['id'],
            'predicate':'observed-evidence','value':{'recorded':True}, 'evidence_chunk_ids':[chunk['id']],
            'idempotency_key':'sdk-claim-'+uuid4().hex}})
        assert not claim.is_error, 'Installed ready-evidence claim creation failed'
        claim_id = claim.structured_content['id']
    claim = await client.call_tool('claims_get', {'claim_id':claim_id})
    assert not claim.is_error and claim.structured_content['evidence'][0]['chunk_id']==chunk['id'], 'Installed sourced claim lost evidence'
    return {'request':data,'receipt':receipt,'document':document.structured_content,'citation':citation,'claim_id':claim_id}


async def wiki_memory(client, http):
    """Installed safe maintenance using real current or legacy SDK serialization."""
    data = {'slug':'sdk-memory/'+uuid4().hex, 'title':'Reusable procedure',
        'body':'Original selected observation café 東京', 'metadata':{'status':'unverified'},
        'idempotency_key':'sdk-wiki-'+uuid4().hex}
    first = await client.call_tool('wiki_pages_upsert', {'data':data})
    assert not first.is_error, 'Installed create-only Wiki upsert failed'
    first = first.structured_content
    assert first['revision']==1 and first['content']['content_hash']==hashlib.sha256(data['body'].encode()).hexdigest(), 'Installed Wiki receipt mismatch'
    resolved = await client.call_tool('wiki_pages_resolve', {'slug':data['slug']})
    assert not resolved.is_error and resolved.structured_content==first, 'Installed exact-slug lookup failed'
    async def denied(name, arguments, code, status):
        result = await client.call_tool(name, arguments)
        assert result.is_error and result.content[0].text==code, 'Installed Wiki error code mismatch'
        assert result.meta['c0/error']=={'code':code,'status':status}, 'Installed Wiki structured error missing'
    await denied('wiki_pages_upsert', {'data':{**data,'idempotency_key':uuid4().hex}}, 'knowledge_conflict', 409)
    update = {**data,'body':data['body']+'\nLater observation retained.', 'expected_revision':1,
        'idempotency_key':'sdk-revise-'+uuid4().hex}
    second = await client.call_tool('wiki_pages_upsert', {'data':update})
    assert not second.is_error and second.structured_content['revision']==2, 'Installed revision-checked upsert failed'
    second = second.structured_content
    await denied('wiki_pages_upsert', {'data':{**update,'idempotency_key':uuid4().hex}}, 'knowledge_conflict', 409)
    assert (await client.call_tool('wiki_pages_upsert', {'data':data})).structured_content==first, 'Installed create receipt changed'
    assert (await client.call_tool('wiki_pages_upsert', {'data':update})).structured_content==second, 'Installed update receipt changed'
    assert (await http.get('/api/v1/wiki/pages/resolve',params={'slug':data['slug']})).json()==second, 'Installed Wiki REST/SDK parity failed'
    assert (await client.call_tool('wiki_pages_get', {'page_id':first['id'],'revision':1})).structured_content['content']==first['content'], 'Installed Wiki history lost'
    history = await client.call_tool('wiki_revisions_list', {'page_id':first['id']})
    assert [r['number'] for r in history.structured_content['revisions']]==[2,1], 'Installed Wiki revisions missing'
    archived = await client.call_tool('wiki_pages_archive', {'page_id':first['id'],
        'data':{'expected_revision':2,'idempotency_key':uuid4().hex}})
    assert not archived.is_error and archived.structured_content['deleted'], 'Installed Wiki archive failed'
    await denied('wiki_pages_resolve', {'slug':data['slug']}, 'knowledge_not_found', 404)
    retained = await client.call_tool('wiki_pages_resolve', {'slug':data['slug'],'include_deleted':True})
    assert not retained.is_error and retained.structured_content['revision']==3, 'Installed archived Wiki lookup failed'
    await denied('wiki_pages_upsert', {'data':{'body':'PRIVATE synthetic marker'}}, 'invalid_knowledge_request', 422)


async def check(value):
    origin = value['origin']
    typed_lifecycles = 0
    text_lifecycles, text_state = 0, None
    wiki_lifecycles = 0
    transport = NodeTransport(urlsplit(origin).hostname, value['address'], value['ca'])
    async with httpx2.AsyncClient(transport=transport, base_url=origin, timeout=20,
            headers={'Authorization':'Bearer ' + value['access_token']}) as http:
        response = await http.get('/api/v1/object-types')
        assert response.status_code == 200, 'Installed scoped REST read failed'
        expected = response.json()
        profile = await http.get('/api/v1/me')
        assert profile.status_code == 200, 'Installed scoped profile read failed'
        role = profile.json()['role']
        metadata = await http.get('/.well-known/oauth-protected-resource/mcp')
        assert metadata.status_code == 200, 'Installed protected-resource metadata unavailable'
        metadata = metadata.json()
        assert metadata['resource'] == origin + '/mcp', 'Installed resource metadata audience mismatch'
        assert metadata['authorization_servers'] == [origin + '/oauth'], 'Installed authorization-server mismatch'
        assert metadata['scopes_supported'] == ['c0:read'], 'Installed initial read scope mismatch'
        authority = await http.get('/.well-known/oauth-authorization-server/oauth')
        assert authority.status_code == 200, 'Installed authorization metadata unavailable'
        authority = authority.json()
        assert authority['issuer'] == origin + '/oauth', 'Installed OAuth issuer mismatch'
        for field, path in [('authorization_endpoint','authorize'), ('token_endpoint','token'),
                ('revocation_endpoint','revoke')]:
            assert authority[field] == origin + '/oauth/' + path, 'Installed OAuth endpoint mismatch'
        assert set(authority['scopes_supported']) == {'c0:read','c0:write','c0:admin'}, 'Installed OAuth scope catalog mismatch'
        for mode in ('auto', 'legacy'):
            # A preceding mode can register an immutable isolated type.
            response = await http.get('/api/v1/object-types')
            assert response.status_code == 200, 'Installed current type discovery failed'
            expected = response.json()
            async with Client(streamable_http_client(origin + '/mcp', http_client=http), mode=mode) as client:
                tools = (await client.list_tools()).tools
                assert 'object_types_list' in {tool.name for tool in tools}, 'Installed MCP read tool missing'
                for tool in tools:
                    schemes = tool.meta.get('securitySchemes') if tool.meta else None
                    assert isinstance(schemes, list) and len(schemes) == 1, 'Installed tool OAuth metadata missing'
                    assert schemes[0]['type'] == 'oauth2' and len(schemes[0]['scopes']) == 1, 'Installed tool OAuth scheme invalid'
                    scope = schemes[0]['scopes'][0]
                    assert scope in {'c0:read','c0:write','c0:admin'}, 'Installed tool OAuth scope invalid'
                    assert scope != 'c0:admin' or role == 'admin', 'Installed Admin tool discovery crossed role'
                    assert scope != 'c0:write' or role in {'editor','admin'}, 'Installed write tool discovery crossed role'
                result = await client.call_tool('object_types_list', {})
                assert not result.is_error and result.structured_content == expected, 'Installed REST/MCP result mismatch'
                if role != 'admin' or 'c0:admin' not in value['scope'].split():
                    denied = await client.call_tool('object_types_create', {'data':{
                        'name':'denied-'+uuid4().hex,'label':'Disposable role boundary','schema':{'type':'object'}}})
                    assert denied.is_error, 'Installed type registration bypassed authorization'
                    if role != 'admin':
                        assert denied.content[0].text == 'permission_denied', 'Installed type role denial mismatch'
                        assert not denied.meta or 'mcp/www_authenticate' not in denied.meta, 'Type role denial requested scope upgrade'
                    else:
                        assert denied.content[0].text == 'insufficient_scope', 'Installed type scope denial mismatch'
                        assert 'scope="c0:admin"' in denied.meta['mcp/www_authenticate'][0], 'Installed type scope upgrade mismatch'
                else:
                    tool = next(t for t in tools if t.name == 'object_types_create')
                    assert 'maxLength <=128' in tool.description, 'Installed type bound guidance missing'
                    if 'c0:write' in value['scope'].split():
                        await typed_objects(client)
                        typed_lifecycles += 1
                if value['scope'] == 'c0:read':
                    denied = await client.call_tool('objects_create', {'data':{'type_name':'absent','data':{}}})
                    assert denied.is_error, 'Read token mutation scope not enforced'
                    if role == 'reader':
                        assert all(tool.annotations.read_only_hint for tool in tools), 'Reader discovered mutation'
                        assert denied.content[0].text == 'permission_denied', 'Installed Reader role not enforced'
                        assert not denied.meta or 'mcp/www_authenticate' not in denied.meta, 'Role denial requested scope upgrade'
                    else:
                        assert 'objects_create' in {tool.name for tool in tools}, 'Role-eligible write tool hidden'
                        assert denied.content[0].text == 'insufficient_scope', 'Missing scope upgrade response'
                        challenge, = denied.meta['mcp/www_authenticate']
                        assert 'error="insufficient_scope"' in challenge and 'error_description="' in challenge, 'Invalid scope upgrade challenge'
                        assert 'scope="c0:write"' in challenge and 'c0:admin' not in challenge, 'Scope upgrade requested excess authority'
                        assert 'resource_metadata="' + origin + '/.well-known/oauth-protected-resource/mcp"' in challenge, 'Scope upgrade metadata route mismatch'
                if value['scope'] == 'c0:read':
                    denied_wiki = await client.call_tool('wiki_pages_upsert', {'data':{
                        'slug':'denied-'+uuid4().hex,'title':'Denied','body':'Synthetic','idempotency_key':uuid4().hex}})
                    expected_code = 'permission_denied' if role=='reader' else 'insufficient_scope'
                    assert denied_wiki.is_error and denied_wiki.content[0].text==expected_code, 'Installed Wiki role/scope denial mismatch'
                    assert denied_wiki.meta['c0/error']=={'code':expected_code,'status':403}, 'Installed Wiki authorization metadata missing'
                    denied_text = await client.call_tool('sources_ingest_text', {'data':{
                        'title':'Denied text probe','body':'Synthetic evidence','idempotency_key':uuid4().hex}})
                    assert denied_text.is_error, 'Installed text operation bypassed role/scope checks'
                    if role == 'reader':
                        assert denied_text.content[0].text == 'permission_denied', 'Installed Reader ingested text'
                        assert not denied_text.meta or 'mcp/www_authenticate' not in denied_text.meta, 'Reader text denial requested scope upgrade'
                    else:
                        assert denied_text.content[0].text == 'insufficient_scope', 'Installed text scope challenge missing'
                        assert 'scope="c0:write"' in denied_text.meta['mcp/www_authenticate'][0], 'Installed text requested wrong scope'
                if 'c0:write' in value['scope'].split():
                    await wiki_memory(client, http)
                    wiki_lifecycles += 1
                    text_state = await text_evidence(client, http, text_state)
                    text_lifecycles += 1
                    # Disposable-only fixture records; archive through the same
                    # delegated transport after checking the actual write result.
                    key = 'mcp-scope-' + uuid4().hex
                    created = await client.call_tool('wiki_pages_create', {'data':{
                        'slug':key, 'title':'Disposable scope-upgrade proof',
                        'body':'Isolated delegated-write fixture.', 'idempotency_key':key}})
                    assert not created.is_error, 'Installed scoped MCP write failed'
                    page = created.structured_content
                    archived = await client.call_tool('wiki_pages_archive', {'page_id':page['id'],
                        'data':{'expected_revision':page['revision'],'idempotency_key':key + '-archive'}})
                    assert not archived.is_error and archived.structured_content['deleted'], 'Installed scoped fixture archive failed'
                assert str((await client.list_resources()).resources[0].uri) == 'c0://capabilities', 'Installed resource missing'
        guard_body = {'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}
        guard_headers = {'Accept':'application/json, text/event-stream', 'MCP-Protocol-Version':'2025-11-25'}
        response = await http.post('/mcp', json=guard_body, headers=guard_headers)
        assert response.status_code == 200, 'Installed guard positive control failed'
        for tool in response.json()['result']['tools']:
            assert tool['securitySchemes'] == tool['_meta']['securitySchemes'], 'Installed wire OAuth extension lost'
        for label, headers, allowed in [('origin', {'Origin':'https://unapproved.invalid'}, (400,403,421)),
                ('host', {'Host':'unapproved.invalid'}, (400,403,404,421))]:
            # Traefik rejects unknown virtual hosts before the app with 404.
            # Origin still reaches the canonical route and must fail there.
            status = (await http.post('/mcp', json=guard_body, headers={**guard_headers, **headers})).status_code
            assert status in allowed, 'Installed %s guard returned HTTP %d' % (label, status)
    expected_typed = 2 if role == 'admin' and {'c0:read','c0:write','c0:admin'} <= set(value['scope'].split()) else 0
    assert typed_lifecycles == expected_typed, 'Installed typed lifecycle coverage mismatch'
    print('Installed typed object lifecycles completed: %d' % typed_lifecycles)
    assert wiki_lifecycles == (2 if 'c0:write' in value['scope'].split() else 0), 'Installed Wiki lifecycle coverage mismatch'
    print('Installed Wiki memory lifecycles completed: %d' % wiki_lifecycles)
    assert text_lifecycles == (2 if 'c0:write' in value['scope'].split() else 0), 'Installed text lifecycle coverage mismatch'
    print('Installed text evidence lifecycles completed: %d' % text_lifecycles)
    print('Installed TLS SDK current/legacy tools, resources, REST parity, scopes and host/origin checks passed')


if __name__ == '__main__':
    try:
        asyncio.run(check(json.load(sys.stdin)))
    except AssertionError as error:
        print('Installed MCP assertion failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except BaseException as error:
        # SDK task groups may contain token/body/URL data in nested errors.
        print('Installed MCP client failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
