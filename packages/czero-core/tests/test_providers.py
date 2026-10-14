# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json
import time
import httpx2
import pytest
from czero_core.providers import EmbeddingClient,EmbeddingSettings,ScorerSettings,SystemOneClient,ProviderUnavailable,MAX_RESPONSE


def embedding(**kwargs):
    return EmbeddingSettings('https://embedding.example.test/v1/embeddings','fixture-embedding',dimensions=3,**kwargs)


@pytest.mark.parametrize('endpoint',['http://plain.test','https://user:pass@provider.test','https://provider.test?token=bad','https://provider.test/#secret','https://provider.test/\n'])
def test_provider_endpoint_is_admin_owned_https_without_credentials_query_or_fragment(endpoint):
    with pytest.raises(ValueError):EmbeddingSettings(endpoint,'fixture',dimensions=3)


@pytest.mark.parametrize('kwargs',[{'timeout':True},{'timeout':float('nan')},{'timeout':6},{'dimensions':True},{'dimensions':2001},{'api_key':'bad\nkey'}])
def test_provider_limits_and_header_keys_are_validated(kwargs):
    with pytest.raises(ValueError):embedding(**kwargs) if 'dimensions' not in kwargs else EmbeddingSettings('https://provider.test','fixture',**kwargs)


def test_embeddings_float_wire_format_indexes_dimensions_and_private_key(caplog):
    seen=[]
    def handler(request):
        seen.append(json.loads(request.content));assert request.headers['Authorization']=='Bearer unit-only-secret'
        assert request.headers['Accept-Encoding']=='identity'
        return httpx2.Response(200,json={'model':'fixture-embedding','data':[{'index':1,'embedding':[0,2,0]},{'index':0,'embedding':[3,0,0]}], 'usage':{'prompt_tokens':7,'total_tokens':7}})
    settings=embedding(api_key='unit-only-secret',send_dimensions=True)
    result=EmbeddingClient(settings,transport=httpx2.MockTransport(handler)).embed(['First','Second'])
    assert result['vectors']==[[1.,0.,0.],[0.,1.,0.]]
    assert seen==[{'model':'fixture-embedding','input':['First','Second'],'encoding_format':'float','dimensions':3}]
    assert 'unit-only-secret' not in repr(settings) and 'unit-only-secret' not in caplog.text


@pytest.mark.parametrize('data',[
    {'model':'wrong','data':[{'index':0,'embedding':[1,0,0]}]},
    {'model':'fixture-embedding','data':[{'index':True,'embedding':[1,0,0]}]},
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[1,0]}]},
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[0,0,0]}]},
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[True,0,0]}]},
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[1e100,0,0]}]},
])
def test_embedding_model_dimension_index_and_nonfinite_zero_validation(data):
    client=EmbeddingClient(embedding(),transport=httpx2.MockTransport(lambda _:httpx2.Response(200,json=data)))
    with pytest.raises(ProviderUnavailable,match='invalid_response'):client.embed(['fixture'])


@pytest.mark.parametrize('model',['jev-1.13','kev-mock'])
def test_both_jev_and_kev_common_systemone_noul_contract_and_bounded_candidates(model):
    def handler(request):
        body=json.loads(request.content);assert str(request.url).endswith('/v1/systemone')
        assert body['model']==model and body['state']['query']=='inventory'
        assert len(body['state']['candidates'][0]['text'].encode())<=2048
        assert body['questions']['r0']['type']=='noul' and 'candidate-a' in body['questions']['r0']['instructions']
        return httpx2.Response(200,json={'model':model,'answers':{'r0':{'type':'noul','noul':.9},'r1':{'type':'noul','noul':.1}},'usage':{'input_tokens':12,'output_tokens':2}})
    client=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone',model),transport=httpx2.MockTransport(handler))
    result=client.score('inventory',[{'id':'candidate-a','text':'東京'*2000},{'id':'candidate-b','text':'Other'}])
    assert result['scores']=={'candidate-a':.9,'candidate-b':.1} and result['truncated_candidates']==1


@pytest.mark.parametrize('status,reason',[(429,'rate_limited'),(503,'unavailable'),(302,'unavailable')])
def test_http_errors_fall_back_without_following_redirects_or_echoing_body(status,reason):
    calls=[]
    def handler(request):
        calls.append(request.url);return httpx2.Response(status,headers={'Location':'https://arbitrary.test'},text='untrusted provider credential/body')
    with pytest.raises(ProviderUnavailable,match=reason) as error:
        EmbeddingClient(embedding(),transport=httpx2.MockTransport(handler)).embed(['fixture'])
    assert len(calls)==1 and 'credential' not in str(error.value)


def test_absolute_deadline_covers_slow_headers_and_streams():
    async def slow(request):
        await asyncio.sleep(.2)
        return httpx2.Response(200,json={})
    started=time.monotonic()
    with pytest.raises(ProviderUnavailable,match='timeout'):
        EmbeddingClient(embedding(timeout=.05),transport=httpx2.MockTransport(slow)).embed(['fixture'])
    assert time.monotonic()-started<.5


def test_response_byte_limit_and_compression_are_rejected_before_json():
    class Stream(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield b'a'*MAX_RESPONSE
            yield b'a'
    for response in (httpx2.Response(200,stream=Stream()),httpx2.Response(200,headers={'Content-Encoding':'gzip'},content=__import__('gzip').compress(b'compressed'))):
        with pytest.raises(ProviderUnavailable,match='invalid_response'):
            EmbeddingClient(embedding(),transport=httpx2.MockTransport(lambda _:response)).embed(['fixture'])


@pytest.mark.parametrize('answer',[{'type':'score','noul':.5},{'type':'noul','noul':True},{'type':'noul','noul':2},{'type':'noul','noul':float('nan')}])
def test_systemone_scores_are_exact_finite_probabilities(answer):
    response={'model':'kev-mock','answers':{'r0':answer}}
    # Encode NaN as raw malformed JSON; json serializer deliberately permits it.
    client=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone','kev-mock'),transport=httpx2.MockTransport(lambda _:httpx2.Response(200,content=json.dumps(response).encode())))
    with pytest.raises(ProviderUnavailable,match='invalid_response'):client.score('query',[{'id':'candidate','text':'evidence'}])


def test_absolute_deadline_stops_a_slow_drip_body_and_closes_the_stream():
    class SlowStream(httpx2.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(.2)
            yield b'}'
        async def aclose(self):self.closed=True
    stream=SlowStream()
    client=EmbeddingClient(embedding(timeout=.05),transport=httpx2.MockTransport(lambda _:httpx2.Response(200,stream=stream)))
    started=time.monotonic()
    with pytest.raises(ProviderUnavailable,match='timeout'):client.embed(['fixture'])
    assert time.monotonic()-started<.5 and stream.closed


@pytest.mark.parametrize('response',[
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[1,0,0]},{'index':0,'embedding':[0,1,0]}]},
    {'model':'fixture-embedding','data':[{'index':0,'embedding':[1,0,0]}]},
])
def test_embedding_missing_and_duplicate_batch_indexes_never_partial_success(response):
    client=EmbeddingClient(embedding(),transport=httpx2.MockTransport(lambda _:httpx2.Response(200,json=response)))
    with pytest.raises(ProviderUnavailable,match='invalid_response'):client.embed(['First','Second'])


@pytest.mark.parametrize('response',[
    {'model':'kev-mock','answers':{}},
    {'model':'kev-mock','answers':{'r0':{'type':'noul','noul':.7},'extra':{'type':'noul','noul':.9}}},
    {'model':'other-model','answers':{'r0':{'type':'noul','noul':.7}}},
    {'model':'kev-mock','answers':{'r0':{'type':'noul','noul':.7}},'usage':{'input_tokens':True}},
])
def test_scorer_missing_extra_model_or_usage_mismatches_fail_closed(response):
    client=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone','kev-mock'),transport=httpx2.MockTransport(lambda _:httpx2.Response(200,json=response)))
    with pytest.raises(ProviderUnavailable,match='invalid_response'):client.score('query',[{'id':'fixture','text':'evidence'}])


def test_provider_input_limits_reject_before_any_network_call():
    def network(_):raise AssertionError('Invalid input reached the network')
    client=EmbeddingClient(embedding(),transport=httpx2.MockTransport(network))
    for texts in ([],['x']*9,['x'*4097],[''],['\0']):
        with pytest.raises(ValueError):client.embed(texts)
    scorer=SystemOneClient(ScorerSettings('https://score.example.test/v1/systemone','kev-mock'),transport=httpx2.MockTransport(network))
    for rows in ([],[{'id':'a','text':'evidence'}]*17,[{'id':'a','text':'x'},{'id':'a','text':'y'}],[{'id':'bad id','text':'x'}]):
        with pytest.raises(ValueError):scorer.score('query',rows)
