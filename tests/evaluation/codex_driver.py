# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned experimental app-server adapter with real parent-owned MCP calls."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib

CLI_VERSION = 'codex-cli 0.163.0'
MAX_CALLS = 16
MAX_LINE = 2 * 1024 * 1024
MAX_TRACE = 16 * 1024 * 1024
FINAL_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{'answer':{'type':'string'},
        'outcome':{'type':'string','enum':['completed','clarification','denied','unavailable']},
        'citations':{'type':'array','items':{'type':'object','additionalProperties':False,
            'properties':{key:{'type':'integer' if key in ('start_offset','end_offset') else 'string'}
                for key in ('source_id','version_id','document_id','chunk_id','content_hash','source_hash','start_offset','end_offset')},
            'required':['source_id','version_id','document_id','chunk_id','content_hash','source_hash','start_offset','end_offset']}}},
    'required':['answer','outcome','citations']}


class RunnerFailure(RuntimeError):
    """Invalid measurement, distinct from an application/model quality failure."""


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def isolated_arguments(config, state):
    flags = {'features.shell_tool':False,'features.apps':False,'features.multi_agent':False,
        'features.shell_snapshot':False,'features.view_image':False,'features.browser_use':False,
        'features.browser_use_external':False,'features.computer_use':False,'features.plugins':False,
        'features.remote_plugin':False,'memories.use_memories':False,'memories.generate_memories':False,
        'project_doc_max_bytes':0,'web_search':'disabled','sqlite_home':str(state/'sqlite'),
        'log_dir':str(state/'logs')}
    for name in config.get('mcp_servers',{}):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name):
            raise RunnerFailure('Unsupported configured server identifier; isolation cannot be proven')
        flags['mcp_servers.'+name+'.enabled'] = False
    return [part for key,value in flags.items() for part in ('-c',key+'='+json.dumps(value))]


def audit_event(value):
    """Reject activity that bypasses the parent-controlled tool boundary."""
    method = value.get('method','')
    rendered = json.dumps(value).lower()
    if method == 'mcpServer/startupStatus/updated' or ('warning' in method.lower() and 'unrecognized configuration' in rendered):
        raise RunnerFailure('Unrelated server startup or ignored configuration')
    item = value.get('params',{}).get('item',{})
    if method in ('item/started','item/completed') and item.get('type') in (
            'commandExecution','fileChange','mcpToolCall','webSearch','imageGeneration','collabAgentToolCall'):
        raise RunnerFailure('Native tool bypassed the evaluation boundary')


async def evaluate(*, tools, instructions, prompt, call_tool, output, model='gpt-6-astra',
                   effort='high', timeout=180, codex='codex'):
    """No bearer, DB URL, grader or expected answer enters the model workspace."""
    output = Path(output)
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    config_path = Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))) / 'config.toml'
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    probe = await asyncio.create_subprocess_exec(codex,'--version',stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    version_bytes,_ = await asyncio.wait_for(probe.communicate(),10)
    version = version_bytes.decode().strip()
    if probe.returncode or version != CLI_VERSION:
        raise RunnerFailure('App-server protocol is pinned to '+CLI_VERSION)
    definitions = [{'type':'function','name':t.name,'description':t.description or '',
                    'inputSchema':t.input_schema,'deferLoading':False} for t in tools]
    if not definitions or len({t['name'] for t in definitions}) != len(definitions):
        raise RunnerFailure('Missing or duplicate actual MCP definitions')
    if len(json.dumps(definitions).encode()) > 2*1024*1024:
        raise RunnerFailure('Catalog exceeds evaluation bound')
    names = {t['name'] for t in definitions}
    events, calls, final, usage = 0, [], None, None
    proof = {'valid':False,'driver':'codex-app-server-eager-mcp','cli':version,
        'requested_model':model,'effort':effort,'catalog_sha256':fingerprint(definitions),
        'instructions_sha256':fingerprint(instructions),'prompt_sha256':fingerprint(prompt),
        'experimental_api':True,'native_discovery_proven':False}
    started = time.monotonic()
    # A fresh cwd and process state for every measured session. No project/skill
    # files, ground truth or private artifacts are placed here.
    with tempfile.TemporaryDirectory(prefix='c0-eval-workspace-') as cwd, \
            tempfile.TemporaryDirectory(prefix='c0-eval-state-') as state, \
            (output/'rpc.jsonl').open('x',encoding='utf-8') as trace, \
            (output/'stderr.log').open('xb') as stderr:
        process = None
        def record(direction,value):
            nonlocal events
            encoded = json.dumps({'direction':direction,'message':value})+'\n'
            events += len(encoded.encode())
            if events > MAX_TRACE:
                raise RunnerFailure('RPC trace exceeds bound')
            trace.write(encoded); trace.flush()
        async def send(value):
            record('sent',value)
            process.stdin.write((json.dumps(value)+'\n').encode())
            await process.stdin.drain()
        async def receive():
            try:
                line = await process.stdout.readline()
            except (ValueError,asyncio.LimitOverrunError) as exc:
                raise RunnerFailure('RPC line exceeds bound') from exc
            if not line:
                raise RunnerFailure('App-server exited before completed turn')
            if len(line)>MAX_LINE:
                raise RunnerFailure('RPC line exceeds bound')
            if stderr.tell()>1024*1024:
                raise RunnerFailure('App-server stderr exceeds bound')
            value = json.loads(line)
            record('received',value); audit_event(value)
            return value
        async def request(identifier,method,params):
            await send({'id':identifier,'method':method,'params':params})
            while True:
                value = await receive()
                if value.get('id') == identifier:
                    if 'error' in value:
                        raise RunnerFailure('App-server rejected '+method)
                    return value['result']
                if 'id' in value and value.get('method'):
                    raise RunnerFailure('Unexpected request during initialization')
        try:
            args = [codex,'app-server','--stdio',*isolated_arguments(config,Path(state))]
            process = await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,stderr=stderr,cwd=cwd,limit=MAX_LINE)
            async with asyncio.timeout(timeout):
                await request(1,'initialize',{'clientInfo':{'name':'c0-tool-evaluation','version':'1'},
                    'capabilities':{'experimentalApi':True}})
                await send({'method':'initialized'})
                thread = await request(2,'thread/start',{'model':model,'cwd':cwd,'ephemeral':True,
                    'sandbox':'read-only','approvalPolicy':'never','dynamicTools':definitions})
                proof['reported_thread_model'] = thread.get('model')
                await request(3,'turn/start',{'threadId':thread['thread']['id'],
                    'input':[{'type':'text','text':instructions+'\n\nUser task:\n'+prompt}],
                    'effort':effort,'outputSchema':FINAL_SCHEMA})
                while True:
                    value = await receive(); method = value.get('method')
                    if method == 'item/tool/call':
                        params = value['params']; name = params['tool']; arguments = params['arguments']
                        if name not in names or params.get('namespace') is not None or not isinstance(arguments,dict):
                            raise RunnerFailure('Tool routing left actual MCP catalog')
                        if len(calls)>=MAX_CALLS or len(json.dumps(arguments).encode())>262144:
                            raise RunnerFailure('Tool call budget exceeded')
                        row = {'name':name,'arguments':arguments,'started':time.monotonic()-started}
                        calls.append(row)
                        (output/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
                        try:
                            result = await call_tool(name,arguments)
                        except BaseException as exc:
                            row['execution_error_type'] = type(exc).__name__
                            raise
                        payload = result.model_dump(mode='json',by_alias=True,exclude_none=True)
                        row['result'] = payload
                        if len(json.dumps(payload).encode())>1024*1024:
                            raise RunnerFailure('Tool response exceeds bound')
                        (output/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
                        await send({'id':value['id'],'result':{'success':not result.is_error,
                            'contentItems':[{'type':'inputText','text':json.dumps(payload)}]}})
                    elif 'id' in value and method:
                        raise RunnerFailure('Unexpected approval or auxiliary tool request')
                    elif method == 'item/completed':
                        item = value['params']['item']
                        if item.get('type') == 'agentMessage' and item.get('phase') == 'final_answer':
                            final = item.get('text')
                    elif method == 'thread/tokenUsage/updated':
                        usage = value['params'].get('tokenUsage')
                    elif method == 'turn/completed':
                        if value['params']['turn']['status'] != 'completed':
                            raise RunnerFailure('Model turn did not complete')
                        break
                # Clarification can legitimately need no calls; discovery still
                # came from the real authenticated MCP list. Grade per-case calls.
                if not final:
                    raise RunnerFailure('Completed turn has no final message')
                from jsonschema import validate
                parsed = json.loads(final); validate(parsed,FINAL_SCHEMA)
                stderr.flush()
                if stderr.tell()>1024*1024:
                    raise RunnerFailure('App-server stderr exceeds bound')
                if 'unrecognized configuration' in (output/'stderr.log').read_text(errors='replace').lower():
                    raise RunnerFailure('Ignored configuration')
                proof.update(valid=True,final=parsed,calls=len(calls),token_usage=usage)
        except BaseException as exc:
            proof['failure_type'] = type(exc).__name__
            raise
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(),5)
                except TimeoutError:
                    process.kill(); await process.wait()
            proof['calls'] = len(calls)
            (output/'calls.json').write_text(json.dumps(calls,indent=2)+'\n')
            proof['elapsed_seconds'] = time.monotonic()-started
            (output/'runner.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof,calls
