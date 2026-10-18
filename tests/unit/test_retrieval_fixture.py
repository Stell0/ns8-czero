# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import runpy
import httpx2
import pytest
from czero_core.providers import EmbeddingClient, EmbeddingSettings, ScorerSettings, SystemOneClient, ProviderUnavailable

ROOT = Path(__file__).resolve().parents[2]


def test_disposable_provider_wire_format_matches_both_runtime_adapters(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests'))
    response = runpy.run_path(str(ROOT / 'tests/retrieval_fixture.py'))['response']
    def transport(request):
        return httpx2.Response(200, json=response(request.url.path, json.loads(request.content)))
    client = EmbeddingClient(EmbeddingSettings('https://fixture.example.test/v1/embeddings', 'fixture', dimensions=3),
                             transport=httpx2.MockTransport(transport))
    result = client.embed(['Independent authored claims', 'other'])
    assert len(result['vectors']) == 2 and len(result['vectors'][0]) == 3
    scorer = SystemOneClient(ScorerSettings('https://fixture.example.test/v1/systemone', 'kev-mock'),
                            transport=httpx2.MockTransport(transport))
    result = scorer.score('independent', [{'id':'wiki_revision:fixture','text':'Independent authored claims'},
                                          {'id':'wiki_revision:other','text':'other evidence'}])
    assert result['scores'] == {'wiki_revision:fixture': .9, 'wiki_revision:other': .2}


def test_native_browser_selects_one_hostname_input_after_form_expansion():
    script = (ROOT / 'tests/czero.robot').read_text()
    assert 'iframe >>> .ns-text-input input    ' not in script
    assert 'iframe >>> .ns-text-input input >> nth=0' in script


def test_snapshot_diagnostics_report_counts_and_columns_without_private_values(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tests'))
    difference=runpy.run_path(str(ROOT / 'tests/retrieval_fixture.py'))['snapshot_difference']
    before={'profiles':[{'id':'private-id','active':True}], 'chunks':[],
            'vectors':[{'id':'private-vector-id','vector':'private-vector-value'}]}
    after={'profiles':[{'id':'private-id','active':False}], 'chunks':[],
           'vectors':[{'id':'new-private-id','vector':'new-private-value'}]}
    result=difference(before,after)
    assert result=='profiles: added=0 removed=0 fields=active; vectors: added=1 removed=1 fields='
    assert 'private' not in result


def test_disposable_https_server_checks_credentials_models_and_failures(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import ipaddress
    import threading
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    monkeypatch.syspath_prepend(str(ROOT / 'tests'))
    namespace = runpy.run_path(str(ROOT / 'tests/retrieval_fixture.py'))
    build = namespace['build_server']; build.__globals__['STATE'] = tmp_path
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Disposable test provider')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .sign(key,hashes.SHA256()))
    ca = tmp_path/'retrieval.pem';ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private = tmp_path/'retrieval.key';private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));private.chmod(0o600)
    (tmp_path/'retrieval-key').write_text('private-fixture-key')
    (tmp_path/'retrieval-mode').write_text('normal')
    monkeypatch.setenv('SSL_CERT_FILE',str(ca))
    server=build('127.0.0.1',0)
    thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);thread.start()
    try:
        origin='https://127.0.0.1:'+str(server.server_port)
        embedding=EmbeddingClient(EmbeddingSettings(origin+'/v1/embeddings','fixture',api_key='private-fixture-key',dimensions=3,timeout=1))
        scorer=SystemOneClient(ScorerSettings(origin+'/v1/systemone','kev-mock',api_key='private-fixture-key',timeout=1))
        assert len(embedding.embed(['fixture'])['vectors'])==1
        assert scorer.score('query',[{'id':'fixture','text':'Independent authored claims'}])['scores']['fixture']==.9
        for mode,reason in [('rate_limited','rate_limited'),('mismatch','invalid_response'),('unavailable','unavailable')]:
            (tmp_path/'retrieval-mode').write_text(mode)
            with pytest.raises(ProviderUnavailable,match=reason):embedding.embed(['fixture'])
            with pytest.raises(ProviderUnavailable,match=reason):scorer.score('query',[{'id':'fixture','text':'evidence'}])
        (tmp_path/'retrieval-mode').write_text('normal')
        wrong=EmbeddingClient(EmbeddingSettings(origin+'/v1/embeddings','fixture',api_key='wrong-key',dimensions=3,timeout=1))
        with pytest.raises(ProviderUnavailable,match='unavailable'):wrong.embed(['fixture'])
    finally:
        server.shutdown();server.server_close();thread.join(timeout=1)


@pytest.mark.parametrize('outcome',['failed','never_complete','queued_timeout'])
def test_native_index_completion_stops_failed_or_unbounded_work(monkeypatch,outcome):
    monkeypatch.syspath_prepend(str(ROOT/'tests'))
    function=runpy.run_path(str(ROOT/'tests/retrieval_fixture.py'))['complete_indexing']
    function.__globals__['index_complete']=lambda _:False
    created=[]
    def enqueue():
        value={'id':str(len(created))};created.append(value);return value
    def get(path):return {'state':'failed' if outcome=='failed' else 'queued' if outcome=='queued_timeout' else 'succeeded'}
    if outcome=='queued_timeout':
        from types import SimpleNamespace
        ticks=iter(range(0,1000,10))
        function.__globals__['time']=SimpleNamespace(monotonic=lambda:next(ticks),sleep=lambda _:None)
    expected={'failed':'Fixture index completion job failed',
              'never_complete':'Fixture index completion exceeded its bounded job budget',
              'queued_timeout':'Complete derivative indexing did not settle'}[outcome]
    with pytest.raises(AssertionError,match='^'+expected+'$'):function('disposable',get,enqueue)
    assert len(created)==(32 if outcome=='never_complete' else 4)
