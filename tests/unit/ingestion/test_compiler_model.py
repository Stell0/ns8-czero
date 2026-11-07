# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Provider wire bounds and pinned Codex event decoding without real credentials."""
from copy import deepcopy
import json
from pathlib import Path
import time

import anyio
import httpx2
import pytest

from c0_compiler import model
from c0_ingest.errors import C0Error

PRIVATE = 'synthetic-provider-secret-must-not-appear'
KNOWN_STARTUP = ('Code Mode is unavailable because code-mode host is disabled. '
    'Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.')


@pytest.fixture
def settings(tmp_path):
    tmp_path.chmod(0o700)
    path=tmp_path/'provider.key';path.write_text(PRIVATE);path.chmod(0o600)
    return {'model_key_file':str(path),'model':'gpt-5.4-2026-03-05',
        'max_output_tokens':256,'timeout_seconds':1,'protocol':'Trusted installed compiler protocol.'}


def install_transport(monkeypatch,handler):
    actual=model.httpx2.AsyncClient
    settings=[]
    def client(**kwargs):
        settings.append(kwargs)
        return actual(transport=httpx2.MockTransport(handler),**kwargs)
    monkeypatch.setattr(model.httpx2,'AsyncClient',client)
    return settings


def response():
    return {'id':'resp_disposable','status':'completed','usage':{'total_tokens':17},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]}


def test_responses_payload_has_only_read_tools_and_no_credential_in_prompt(settings,monkeypatch):
    received=[]
    async def handler(request):
        received.append(request)
        return httpx2.Response(200,json=response())
    clients=install_transport(monkeypatch,handler)
    messages=[{'role':'user','content':'Untrusted original instructions remain data.'}]
    schemas={'source_documents_get':{'type':'object','properties':{'space_id':{'type':'string'}}}}
    result=model.Responses(settings).request(messages,schemas)
    assert result==response() and len(received)==1
    request=received[0];body=json.loads(request.content)
    assert str(request.url)=='https://api.openai.com/v1/responses' and request.method=='POST'
    assert request.headers['Authorization']=='Bearer '+PRIVATE
    assert PRIVATE not in request.content.decode()
    assert body['model']==settings['model'] and body['store'] is False
    assert body['parallel_tool_calls'] is False and body['max_output_tokens']==256
    assert body['input']==messages and settings['protocol'] in body['instructions']
    assert len(body['tools'])==1
    tool=body['tools'][0]
    assert tool['type']=='function' and tool['name']=='c0_read' and tool['strict'] is True
    parameters=tool['parameters']
    assert parameters['additionalProperties'] is False
    assert set(parameters['required'])=={'operation','arguments'}
    operations=parameters['properties']['operation']['enum']
    assert set(operations)==set(model.READ_TOOLS)
    assert not any('apply' in name or 'set' in name or 'create' in name or 'shell' in name for name in operations)
    assert clients[0]['follow_redirects'] is False


@pytest.mark.parametrize('status',[307,401,403,429,500])
def test_responses_does_not_follow_redirects_or_retry_and_redacts_http_body(settings,monkeypatch,capsys,caplog,status):
    requests=[]
    async def handler(request):
        requests.append(str(request.url))
        return httpx2.Response(status,text='Bearer '+PRIVATE,
            headers={'Location':'https://untrusted.example.org/collect'})
    install_transport(monkeypatch,handler)
    with pytest.raises(C0Error,match='^model_outcome_uncertain$') as caught:
        model.Responses(settings).request([], {})
    assert requests==['https://api.openai.com/v1/responses']
    captured=capsys.readouterr()
    assert PRIVATE not in str(caught.value)+captured.out+captured.err+caplog.text
    assert caught.value.__cause__ is None


class Slow(httpx2.AsyncByteStream):
    def __init__(self):self.closed=False;self.tail_sent=False
    async def __aiter__(self):
        yield b'{"id":"resp_slow",'
        await anyio.sleep(1)
        self.tail_sent=True
        yield b'"status":"completed","output":[]}'
    async def aclose(self):self.closed=True


def test_responses_total_deadline_cancels_a_slow_stream(settings,monkeypatch):
    stream=Slow()
    async def handler(request):return httpx2.Response(200,stream=stream)
    install_transport(monkeypatch,handler)
    provider=model.Responses({**settings,'timeout_seconds':0.02})
    started=time.monotonic()
    with pytest.raises(C0Error,match='^model_outcome_uncertain$'):provider.request([], {})
    assert time.monotonic()-started<0.75
    assert stream.closed and not stream.tail_sent


class Oversized(httpx2.AsyncByteStream):
    def __init__(self):self.closed=False;self.chunks=0
    async def __aiter__(self):
        for _ in range(4):
            self.chunks+=1
            yield b'x'*524288
    async def aclose(self):self.closed=True


def test_responses_output_cap_stops_reading_before_all_chunks(settings,monkeypatch):
    stream=Oversized()
    async def handler(request):return httpx2.Response(200,stream=stream)
    install_transport(monkeypatch,handler)
    with pytest.raises(C0Error,match='^model_outcome_uncertain$'):
        model.Responses(settings).request([], {})
    assert stream.closed and stream.chunks==3


def test_responses_transport_exception_text_is_not_exposed(settings,monkeypatch,capsys):
    requests=[]
    async def handler(request):
        requests.append(True)
        raise httpx2.ConnectError(PRIVATE,request=request)
    install_transport(monkeypatch,handler)
    with pytest.raises(C0Error,match='^model_outcome_uncertain$') as caught:
        model.Responses(settings).request([], {})
    assert len(requests)==1
    captured=capsys.readouterr()
    assert PRIVATE not in str(caught.value)+captured.out+captured.err


@pytest.mark.parametrize('changes',[{'status':'in_progress'},{'id':None},{'output':{}},{'output':None}])
def test_responses_rejects_incomplete_or_invalid_envelope(settings,monkeypatch,changes):
    async def handler(request):return httpx2.Response(200,json={**response(),**changes})
    install_transport(monkeypatch,handler)
    with pytest.raises(C0Error,match='^model_outcome_uncertain$'):
        model.Responses(settings).request([], {})


def decision(**extra):
    return {'title':'Source-backed concept','synthesis':'Read the original procedure.',
        'classification':'supported_synthesis','citations':[],'topics':[],
        'no_change':True,'operation':None,'arguments':None,**extra}


def events(value=None):
    value=decision() if value is None else value
    return [{'type':'thread.started','thread_id':'thread_disposable'},
        {'type':'item.completed','item':{'id':'startup','type':'error','message':KNOWN_STARTUP}},
        {'type':'turn.started'},
        {'type':'item.completed','item':{'id':'reasoning','type':'reasoning','text':'Source-backed analysis.'}},
        {'type':'item.completed','item':{'id':'final','type':'agent_message','text':json.dumps(value)}},
        {'type':'turn.completed','usage':{'input_tokens':17,'cached_input_tokens':9,'output_tokens':4}}]


def test_codex_decoder_accepts_exact_startup_warning_and_normalizes_final_decision():
    result=model.decode_codex(events())
    assert result['id']=='thread_disposable' and result['status']=='completed'
    assert result['usage']['total_tokens']==21
    item=result['output'][0]
    assert item['type']=='message'
    actual=json.loads(item['content'][0]['text'])
    assert actual=={k:v for k,v in decision().items() if k not in ('operation','arguments')}


def test_codex_decoder_normalizes_only_allowed_read_tool_request():
    value=decision(operation='source_documents_get',arguments='{"logical_document_id":"disposable"}')
    result=model.decode_codex(events(value))
    item=result['output'][0]
    assert item['type']=='function_call' and item['name']=='c0_read' and item['call_id']
    assert json.loads(item['arguments'])=={'operation':value['operation'],'arguments':value['arguments']}


@pytest.mark.parametrize('item_type',['command_execution','mcp_tool_call','web_search','function_call','file_change'])
def test_codex_decoder_rejects_native_tool_execution(item_type):
    value=events()
    value.insert(3,{'type':'item.completed','item':{'id':'unexpected','type':item_type,'text':PRIVATE}})
    with pytest.raises(C0Error):model.decode_codex(value)


@pytest.mark.parametrize('where',['startup','during_turn','top_level','failed_turn'])
def test_codex_decoder_rejects_unknown_errors_and_warning_after_turn_started(where):
    value=events()
    if where=='startup':value[1]['item']['message']='Unexpected startup error '+PRIVATE
    elif where=='during_turn':
        warning=value.pop(1);value.insert(2,warning)
    elif where=='top_level':value.insert(2,{'type':'error','message':PRIVATE})
    else:value[-1]={'type':'turn.failed','error':{'message':PRIVATE}}
    with pytest.raises(C0Error) as caught:model.decode_codex(value)
    assert PRIVATE not in str(caught.value)


@pytest.mark.parametrize('event_type',['turn.started','turn.completed'])
def test_codex_decoder_rejects_repeated_model_turns(event_type):
    value=events();value.append(next(deepcopy(e) for e in value if e['type']==event_type))
    with pytest.raises(C0Error):model.decode_codex(value)


def test_codex_decoder_rejects_malformed_final_json():
    value=events();value[-2]['item']['text']='{not valid JSON '+PRIVATE
    with pytest.raises(C0Error) as caught:model.decode_codex(value)
    assert PRIVATE not in str(caught.value)


@pytest.mark.parametrize('changes',[{'operation':'wiki_pages_upsert','arguments':'{}'},
    {'operation':None,'arguments':'{}'}, {'operation':'source_documents_get','arguments':None}])
def test_codex_decoder_rejects_invalid_or_unpaired_tool_selection(changes):
    with pytest.raises(C0Error):model.decode_codex(events(decision(**changes)))


def codex_provider(timeout=2):
    # Version probing is covered separately; boundary cases exercise real pipes
    # using an owned Python emitter instead of executing an installed model.
    provider=model.Codex.__new__(model.Codex)
    provider.binary='/opt/disposable/codex'
    provider.config={'model':'gpt-6.1-sol','timeout_seconds':timeout,
                     'protocol':'Trusted installed compiler protocol.'}
    return provider


def pipe_emitter(monkeypatch,script,*,on_spawn=None):
    import subprocess
    import sys
    actual=subprocess.Popen
    captured=[]
    def spawn(argv,**kwargs):
        entry={'argv':list(argv),'kwargs':kwargs}
        captured.append(entry)
        if on_spawn:on_spawn(entry)
        process=actual([sys.executable,'-u','-c',script],**kwargs)
        entry['process']=process
        return process
    monkeypatch.setattr(subprocess,'Popen',spawn)
    return captured


def test_codex_real_pipe_invocation_has_closed_tools_environment_and_private_context(monkeypatch):
    import os
    for key in ('C0_API_KEY','OPENAI_API_KEY','DATABASE_URL','CZERO_TEST_DATABASE_URL','AUTH_TOKEN','CREDENTIALS_DIRECTORY'):
        monkeypatch.setenv(key,PRIVATE)
    raw='\n'.join(json.dumps(event) for event in events())+'\n'
    script=('import sys\n'
        'prompt=sys.stdin.buffer.read()\n'
        'assert '+repr(PRIVATE.encode())+' not in prompt\n'
        'assert b"Trusted installed compiler protocol." in prompt\n'
        'assert b"Untrusted original data." in prompt\n'
        'sys.stdout.write('+repr(raw)+')\n')
    inspected=[]
    def inspect_spawn(entry):
        argv=entry['argv'];options=entry['kwargs'];directory=Path(options['cwd'])
        assert argv[0]=='/opt/disposable/codex' and argv[-1]=='-'
        assert directory.stat().st_mode & 0o777==0o700
        assert sorted(p.name for p in directory.iterdir())==['output.json']
        schema=Path(argv[argv.index('--output-schema')+1])
        assert schema.parent==directory and schema.stat().st_mode & 0o777==0o600
        assert json.loads(schema.read_text())==model.CODEX_SCHEMA
        disabled={argv[index+1] for index,item in enumerate(argv[:-1]) if item=='--disable'}
        assert {'shell_tool','unified_exec','apps','plugins','multi_agent','browser_use',
            'computer_use','in_app_browser','code_mode_host','hooks','image_generation','view_image',
            'skill_search','remote_plugin','plugin_discovery_prefetch','skill_mcp_dependency_install'}<=disabled
        assert '--ignore-user-config' in argv and '--ephemeral' in argv
        assert argv[argv.index('--sandbox')+1]=='read-only'
        assert argv[argv.index('-a')+1]=='never'
        overrides={argv[index+1].split('=',1)[0]:argv[index+1].split('=',1)[1]
            for index,item in enumerate(argv[:-1]) if item=='-c'}
        assert overrides['model_reasoning_effort'].strip('"')=='low'
        assert overrides['model_providers.c0_compiler.request_max_retries']=='0'
        assert overrides['model_providers.c0_compiler.stream_max_retries']=='0'
        assert overrides['memories.use_memories']=='false' and overrides['memories.generate_memories']=='false'
        assert Path(json.loads(overrides['sqlite_home'])).is_relative_to(directory)
        assert Path(json.loads(overrides['log_dir'])).is_relative_to(directory)
        for key in ('C0_API_KEY','OPENAI_API_KEY','DATABASE_URL','CZERO_TEST_DATABASE_URL','AUTH_TOKEN','CREDENTIALS_DIRECTORY'):
            assert key not in options['env']
        assert options['start_new_session'] is True
        assert PRIVATE not in json.dumps(argv)
        inspected.append(directory)
    captured=pipe_emitter(monkeypatch,script,on_spawn=inspect_spawn)
    provider=codex_provider()
    result=provider.request([{'role':'user','content':'Untrusted original data.'}],{})
    assert result['status']=='completed' and result['usage']['total_tokens']==21
    assert len(captured)==1 and captured[0]['process'].returncode==0
    assert provider.last_audit['turns_started']==1 and provider.last_audit['turns_completed']==1
    assert inspected and not inspected[0].exists()


def test_codex_real_pipe_timeout_kills_process_and_redacts_stderr(monkeypatch,capsys):
    import signal
    script=('import sys,time\n'
        'sys.stdin.buffer.read()\n'
        'sys.stderr.write('+repr(PRIVATE)+')\n'
        'sys.stderr.flush()\n'
        'time.sleep(5)\n')
    captured=pipe_emitter(monkeypatch,script)
    started=time.monotonic()
    with pytest.raises(C0Error) as caught:codex_provider(timeout=1).request([], {})
    assert time.monotonic()-started<3
    assert len(captured)==1 and captured[0]['process'].returncode==-signal.SIGKILL
    output=capsys.readouterr()
    assert PRIVATE not in str(caught.value)+output.out+output.err
    assert str(caught.value).startswith('model_outcome_uncertain')
    assert not Path(captured[0]['kwargs']['cwd']).exists()


def test_codex_real_pipe_output_cap_stops_and_reaps_child(monkeypatch,capsys):
    script=('import sys,time\n'
        'sys.stdin.buffer.read()\n'
        'sys.stderr.write('+repr(PRIVATE)+')\n'
        'sys.stdout.buffer.write(b"x"*2097152)\n'
        'sys.stdout.buffer.flush()\n'
        'time.sleep(5)\n')
    captured=pipe_emitter(monkeypatch,script)
    started=time.monotonic()
    with pytest.raises(C0Error) as caught:codex_provider(timeout=2).request([], {})
    assert time.monotonic()-started<3
    assert len(captured)==1 and captured[0]['process'].poll() is not None
    output=capsys.readouterr()
    assert PRIVATE not in str(caught.value)+output.out+output.err
    assert str(caught.value).startswith('model_outcome_uncertain')
    assert not Path(captured[0]['kwargs']['cwd']).exists()


@pytest.mark.parametrize('version',['codex-cli 0.166.0','codex-cli 0.165.0'])
def test_codex_initialization_requires_exact_supported_cli_version(monkeypatch,version):
    import shutil
    import subprocess
    from types import SimpleNamespace
    calls=[]
    monkeypatch.setattr(shutil,'which',lambda name:'/opt/disposable/codex' if name=='codex' else None)
    def probe(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(stdout=(version+'\n').encode())
    monkeypatch.setattr(subprocess,'run',probe)
    if version=='codex-cli 0.166.0':
        provider=model.Codex({'model':'gpt-6.1-sol'})
        assert provider.binary=='/opt/disposable/codex'
    else:
        with pytest.raises(C0Error,match='^unsupported_codex_version$'):model.Codex({'model':'gpt-6.1-sol'})
    assert len(calls)==1 and calls[0][0]==['/opt/disposable/codex','--version']
    assert calls[0][1]['timeout']==5 and calls[0][1]['check'] is True


def test_codex_initialization_does_not_fall_back_when_binary_missing(monkeypatch):
    import shutil
    import subprocess
    monkeypatch.setattr(shutil,'which',lambda name:None)
    calls=[]
    monkeypatch.setattr(subprocess,'run',lambda *args,**kwargs:calls.append(True))
    with pytest.raises(C0Error,match='^codex_not_installed$'):model.Codex({'model':'gpt-6.1-sol'})
    assert calls==[]
