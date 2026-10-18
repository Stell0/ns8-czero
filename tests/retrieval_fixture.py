# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable QEMU HTTPS provider; never installed in runtime images."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
from oidc_fixture import STATE, command, task

PORT = 18443


def response(path, body):
    if path == '/v1/embeddings':
        inputs = body['input']
        vectors = [[1., .2 if 'independent' in text.lower() else .8, .1] for text in inputs]
        return {'model': body['model'], 'data': [{'index': i, 'embedding': vector} for i, vector in enumerate(vectors)],
                'usage': {'prompt_tokens': len(inputs) * 4, 'total_tokens': len(inputs) * 4}}
    if path == '/v1/systemone':
        return {'model': body['model'], 'answers': {'r' + str(i): {'type': 'noul',
                'noul': .9 if 'Independent authored' in candidate['text'] else .2}
                for i, candidate in enumerate(body['state']['candidates'])}}
    raise ValueError('unsupported_fixture_endpoint')


def build_server(host='0.0.0.0', port=PORT):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                mode = (STATE / 'retrieval-mode').read_text().strip()
                if mode == 'rate_limited':
                    self.send_response(429); self.end_headers(); return
                if mode == 'unavailable':
                    self.send_response(503); self.end_headers(); return
                length = int(self.headers.get('content-length', '0'))
                if not 0 < length <= 262144:
                    raise ValueError('oversized_fixture_request')
                body = json.loads(self.rfile.read(length))
                if self.headers.get('Authorization') != 'Bearer ' + (STATE / 'retrieval-key').read_text():
                    self.send_response(401); self.end_headers(); return
                result = response(self.path, body)
                if mode == 'mismatch':
                    result['model'] = 'wrong-model'
                data = json.dumps(result).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            except (OSError, ValueError, KeyError):
                self.send_response(400); self.end_headers()
    server = ThreadingHTTPServer((host, port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(STATE / 'retrieval.pem'), str(STATE / 'retrieval.key'))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def prepare(module_id):
    # This server runs only in the disposable guest, outside Czero. Its public
    # test CA is already trusted in the application and worker drop-ins.
    import secrets
    key_file = STATE / 'retrieval-key'
    key_file.write_text(secrets.token_urlsafe(32)); key_file.chmod(0o600)
    (STATE / 'retrieval-mode').write_text('normal')
    (STATE / 'retrieval.ext').write_text('subjectAltName=IP:10.0.2.2,IP:127.0.0.1\n'
        'basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    command(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=Czero disposable retrieval',
             '-keyout', str(STATE / 'retrieval.key'), '-out', str(STATE / 'retrieval.csr')])
    command(['openssl', 'x509', '-req', '-in', str(STATE / 'retrieval.csr'), '-CA', str(STATE / 'ca.pem'),
             '-CAkey', str(STATE / 'ca.key'), '-CAcreateserial', '-days', '2',
             '-extfile', str(STATE / 'retrieval.ext'), '-out', str(STATE / 'retrieval.pem')])
    (STATE / 'retrieval.key').chmod(0o600)
    process = subprocess.Popen([sys.executable, __file__, 'serve'], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (STATE / 'retrieval-pid').write_text(str(process.pid))
    from urllib.request import urlopen, Request
    context = ssl.create_default_context(cafile=str(STATE / 'ca.pem'))
    for attempt in range(30):
        try:
            with urlopen(Request('https://127.0.0.1:18443/v1/embeddings', data=json.dumps({'input': ['fixture'],
                    'model': 'fixture-embedding'}).encode(), headers={'Authorization': 'Bearer ' + key_file.read_text()}),
                    context=context, timeout=2) as result:
                assert result.status == 200
            break
        except OSError:
            if attempt == 29: raise
            time.sleep(.2)
    current = task('module/' + module_id + '/get-configuration', {})
    request = {key: current[key] for key in ('host', 'lets_encrypt', 'idp', 'user_domain', 'owner')}
    request['retrieval'] = {'embedding': {'enabled': True, 'endpoint': 'https://10.0.2.2:18443/v1/embeddings',
        'model': 'fixture-embedding', 'dimensions': 3, 'api_key': key_file.read_text()},
        'scorer': {'mode': 'filter', 'endpoint': 'https://10.0.2.2:18443/v1/systemone', 'model': 'kev-mock',
                   'api_key': key_file.read_text(), 'threshold': .7}}
    task('module/' + module_id + '/configure-module', request)
    configured = task('module/' + module_id + '/get-configuration', {})
    assert configured['retrieval']['embedding']['api_key_configured'], 'Embedding key not saved'
    assert configured['retrieval']['scorer']['api_key_configured'], 'Scorer key not saved'
    assert key_file.read_text() not in json.dumps(configured), 'Configuration leaked fixture key'
    private = command(['runagent', '-m', module_id, 'python3', '-c',
        "import os,pathlib,agent; p=pathlib.Path(os.environ['AGENT_STATE_DIR']); "
        "assert (p/'retrieval.env').stat().st_mode & 0o777==0o600; "
        "assert 'CZERO_RETRIEVAL_CONFIG_B64' not in agent.read_envfile(str(p/'environment'))"])
    (STATE / 'retrieval-config.json').write_text(json.dumps(configured['retrieval']))
    (STATE / 'retrieval-config.json').chmod(0o600)


def snapshot(module_id):
    query = """SELECT json_build_object('profiles',(SELECT json_agg(t ORDER BY id) FROM
        (SELECT id,model,dimensions,generation,active FROM c0_embedding_profiles) t),
        'chunks',(SELECT json_agg(t ORDER BY id) FROM (SELECT id,revision_id,ordinal,start_offset,end_offset,
        content_hash FROM c0_wiki_chunks) t),'vectors',(SELECT json_agg(t ORDER BY id) FROM
        (SELECT id,profile_id,generation,source_chunk_id,wiki_chunk_id,input_hash,embedding::text AS vector
        FROM c0_embeddings) t));"""
    return json.loads(command(['runagent', '-m', module_id, 'podman', 'exec', 'czero-postgres',
                              'psql', '-U', 'czero', '-d', 'czero', '-At', '-c', query]))


def index_complete(module_id):
    # A minimum vector count is not completion: earlier role fixtures add
    # sources/pages, and each batch prepares only two new Wiki revisions.
    query = """SELECT EXISTS(SELECT 1 FROM c0_embedding_profiles WHERE active)
        AND NOT EXISTS(SELECT 1 FROM c0_chunks c JOIN c0_documents d ON d.id=c.document_id
        JOIN c0_source_versions v ON v.id=d.version_id JOIN c0_sources s ON s.id=v.source_id
        WHERE NOT s.deleted AND NOT EXISTS(SELECT 1 FROM c0_embeddings e JOIN c0_embedding_profiles p
        ON p.id=e.profile_id WHERE p.active AND e.generation=p.generation AND e.source_chunk_id=c.id))
        AND NOT EXISTS(SELECT 1 FROM c0_wiki_pages p JOIN c0_wiki_revisions r
        ON r.page_id=p.id AND r.number=p.revision WHERE NOT p.deleted AND
        (NOT EXISTS(SELECT 1 FROM c0_wiki_chunks w WHERE w.revision_id=r.id)
        OR EXISTS(SELECT 1 FROM c0_wiki_chunks w WHERE w.revision_id=r.id AND NOT EXISTS(
        SELECT 1 FROM c0_embeddings e JOIN c0_embedding_profiles ep ON ep.id=e.profile_id
        WHERE ep.active AND e.generation=ep.generation AND e.wiki_chunk_id=w.id))));"""
    return command(['runagent', '-m', module_id, 'podman', 'exec', 'czero-postgres',
                    'psql', '-U', 'czero', '-d', 'czero', '-At', '-c', query]).strip() == 't'


def timer_indexed(module_id):
    # The public index status is selected-space scoped. A global worker may
    # first index protected evidence, so Shared's count cannot prove progress.
    # Require an actual scheduled successful batch for the active generation;
    # manually submitted jobs and previous profiles/generations do not count.
    query = """SELECT EXISTS(SELECT 1 FROM c0_task_runs r
        JOIN c0_scheduled_tasks s ON s.id=r.schedule_id
        JOIN c0_jobs j ON j.id=r.job_id
        JOIN c0_embedding_profiles p ON p.id::text=j.result->>'profile_id'
        WHERE s.handler='embedding.index' AND j.state='succeeded' AND p.active
        AND j.result->>'generation'=p.generation::text
        AND j.result->>'status'='indexed' AND (j.result->'indexed')>'0'::jsonb);"""
    return command(['runagent', '-m', module_id, 'podman', 'exec', 'czero-postgres',
                    'psql', '-U', 'czero', '-d', 'czero', '-At', '-c', query]).strip() == 't'


def complete_indexing(module_id, get, enqueue):
    # Independent client fixtures grow the corpus. Successful bounded jobs do
    # not prove completion; observe the real remaining source/Wiki candidates.
    # Allow three normal one-minute worker opportunities, without changing the
    # installed timer, job budgets, session or delegated grant lifetimes.
    deadline=time.monotonic()+180
    submitted=0
    pending=[]
    while time.monotonic()<deadline:
        if pending:
            states=[get('jobs/'+key)['state'] for key in pending]
            assert 'failed' not in states, 'Fixture index completion job failed'
            if not all(state=='succeeded' for state in states):
                time.sleep(2)
                continue
        if index_complete(module_id):
            return submitted
        assert submitted<32, 'Fixture index completion exceeded its bounded job budget'
        pending=[enqueue()['id'] for _ in range(4)]
        submitted+=len(pending)
    raise AssertionError('Complete derivative indexing did not settle')


def snapshot_difference(before, after):
    # Static categories/counts/column names only; no IDs, bodies or vectors.
    differences = []
    for category in ('profiles', 'chunks', 'vectors'):
        old = {row['id']: row for row in before.get(category) or []}
        new = {row['id']: row for row in after.get(category) or []}
        if old != new:
            fields = sorted({field for key in old.keys() & new.keys() for field in old[key]
                             if old[key][field] != new[key].get(field)})
            differences.append('%s: added=%d removed=%d fields=%s' %
                (category, len(new.keys()-old.keys()), len(old.keys()-new.keys()), ','.join(fields)))
    return '; '.join(differences)


def check(module_id, operation):
    from oidc_probe import Browser, knowledge_request
    payload = json.loads((STATE / 'personas.json').read_text())
    browser = Browser('https://' + payload['host']); profile = browser.login('c0owner', payload['password'])
    get = lambda path: knowledge_request(browser, profile, path)
    if operation == 'seed':
        for attempt in range(60):
            status = get('knowledge/index/status')
            if status['configured'] and timer_indexed(module_id): break
            time.sleep(2)
        assert status['configured'] and timer_indexed(module_id), 'Native timer did not index evidence'
        schedules = get('schedules')['schedules']
        refresh = next(s for s in schedules if s['handler'] == 'embedding.index')
        code, body, _ = browser.api('/api/v1/schedules/' + refresh['id'],
            {'enabled': False, 'interval_seconds': refresh['interval_seconds']}, 'PUT', profile['csrf_token'])
        assert code == 200, 'Embedding refresh pause rejected'
        paused = json.loads(body)
        assert paused['enabled'] is False, 'Embedding refresh did not pause'
        # Retain the actual timer first-batch assertion, then finish all earlier
        # role/persistence fixtures via bounded registered jobs and the worker.
        batches=complete_indexing(module_id,get,lambda:knowledge_request(browser,profile,'jobs',
            {'handler':'embedding.index','payload':{}},'POST',201))
        print('Disposable index completion jobs: %d' % batches)
    refresh = next(s for s in get('schedules')['schedules'] if s['handler'] == 'embedding.index')
    assert refresh['enabled'] is False, 'Paused embedding refresh changed during recovery'
    assert index_complete(module_id), 'Recovered derivative indexing is incomplete'
    config = task('module/' + module_id + '/get-configuration', {})['retrieval']
    assert config == json.loads((STATE / 'retrieval-config.json').read_text()), 'Recovered provider settings changed'
    result = get('knowledge/search?query=independent+authored&mode=hybrid&rerank=filter')
    assert result['retrieval_method'] == 'hybrid+filter' and result['fallback_reason'] is None, 'Configured hybrid/scorer failed'
    assert result['scored_count'] > 0 and len(result['hits']) == 1, 'Scorer did not filter evidence'
    page = json.loads((STATE / 'expected-identities.json').read_text())['knowledge']['page']
    assert result['hits'][0]['wiki']['revision_id'] == page['content']['id'], 'Semantic Wiki identity changed'
    semantic = get('knowledge/search?query=independent+authored&mode=semantic&rerank=filter')
    assert semantic['retrieval_method'] == 'semantic+filter' and semantic['fallback_reason'] is None, 'Semantic-only retrieval failed'
    assert len(semantic['hits']) == 1 and semantic['hits'][0]['wiki']['revision_id'] == page['content']['id'], 'Semantic-only Wiki identity missing'
    text = get('knowledge/search?query=independent+authored&mode=text&rerank=off')
    assert text['retrieval_method'] == 'text' and text['hits'], 'Configured provider-free text missing'
    for mode, reason in [('rate_limited', 'rate_limited'), ('mismatch', 'invalid_response'), ('unavailable', 'unavailable')]:
        (STATE / 'retrieval-mode').write_text(mode)
        try:
            fallback = get('knowledge/search?query=independent+authored&mode=hybrid')
            assert fallback['hits'] == text['hits'], 'Provider failure changed ordinary ranking'
            assert 'embedding_' + reason in fallback['fallback_reasons'], 'Embedding fallback undisclosed'
            assert 'systemone_' + reason in fallback['fallback_reasons'], 'Scorer fallback undisclosed'
        finally:
            (STATE / 'retrieval-mode').write_text('normal')
    rows = snapshot(module_id)
    assert rows['vectors'] and rows['chunks'], 'No derivative vector rows'
    path = STATE / 'expected-vectors.json'
    if operation == 'seed':
        path.write_text(json.dumps(rows)); path.chmod(0o600)
    else:
        before = json.loads(path.read_text())
        assert rows == before, 'Recovered profile/chunk/vector data changed (' + snapshot_difference(before, rows) + ')'
    browser.logout(profile)


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'serve': build_server().serve_forever()
        elif sys.argv[1] == 'prepare': prepare(sys.argv[2])
        else: check(sys.argv[2], sys.argv[1])
    except Exception as error:
        # Never emit credentials, request bytes or native task output.
        print(str(error) if isinstance(error, AssertionError) else 'Retrieval fixture ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
