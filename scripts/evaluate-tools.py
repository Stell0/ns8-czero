#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit local model evaluation. Never contacts the accepted installation."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime,timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from evaluation.codex_driver import evaluate, fingerprint
from evaluation.corpus import CASES, INITIAL, RUBRIC_VERSION
from evaluation.fixture import Fixture, disposable_database
from evaluation.grader import grade
from evaluation.skill_input import load_plugin


async def run(args):
    os.umask(0o077)
    if not args.database_url:
        raise SystemExit('Supply CZERO_EVAL_DATABASE_URL for a disposable loopback PostgreSQL administrator')
    output = Path(args.output).resolve()
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    import czero_app
    app_root = Path(czero_app.__file__).resolve().parents[3]
    source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=app_root,text=True).strip()
    dirty = bool(subprocess.check_output(['git','status','--porcelain'],cwd=app_root,text=True))
    driver_files = [Path(__file__),*sorted((ROOT/'tests/evaluation').glob('*.py'))]
    packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}
    runtime_names=('czero-core','mcp','fastapi','starlette','httpx','httpx2','sqlalchemy',
        'psycopg','pydantic','pydantic-core','joserfc','cryptography','jsonschema')
    runtime_versions={name:packages[name] for name in runtime_names}

    skill_instructions, skill_proof = load_plugin(args.plugin) if args.plugin else ('', None)
    proof = {'source':source,'dirty':dirty,'app_version':czero_app.__version__,'rubric_version':RUBRIC_VERSION,
        'driver_sha256':fingerprint({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in driver_files}),
        'corpus_sha256':fingerprint(CASES),'started_at':datetime.now(timezone.utc).isoformat(),
        'requested_model':args.model,'effort':args.effort,'cases':[],'plugin':skill_proof,
        'python_version':sys.version,'runtime_versions':runtime_versions,
        'runtime_versions_sha256':fingerprint(runtime_versions),'installed_packages':dict(sorted(packages.items())),
        'boundary':'Experimental eager Codex app-server adapter; real authenticated MCP/DB. No native discovery or ChatGPT quality claim.'}
    cases = args.cases or list(INITIAL)
    for case in cases:
        entry = {'case':case,'status':'started'}; proof['cases'].append(entry)
        (output/'suite.json').write_text(json.dumps(proof,indent=2)+'\n')
        print('Starting '+case,flush=True)
        try:
            async with disposable_database(args.database_url) as url:
                with tempfile.TemporaryDirectory(prefix='c0-eval-fixture-') as directory:
                    fixture = Fixture(url,directory)
                    try:
                        await fixture.seed(case)
                        async with fixture.mcp(case) as client:
                            tools = (await client.list_tools()).tools
                            capability = json.loads((await client.read_resource('c0://capabilities')).contents[0].text)
                            # Workflows are projected from actual granted scopes. Models
                            # receive no oracle, IDs beyond requested context, or DB URL.
                            from czero_app.agent_guidance import SERVER_INSTRUCTIONS
                            instructions = 'Client discovery already completed authenticated tools/list and resources/read(c0://capabilities). The actual-scope guidance is provided here.\n'+SERVER_INSTRUCTIONS+'\n'+json.dumps(capability.get('guidance',{}))
                            annotations = {t.name:(t.annotations.model_dump(by_alias=True,exclude_none=True)
                                if t.annotations else {}) for t in tools}
                            instructions += '\nClient projection of actual tools/list annotations (advisory, never authorization): '+json.dumps(annotations)
                            instructions += '\nReport the final answer using the required output schema. Citations are exact values read from C0; use an empty list when none support the task. Do not invent successful actions.'
                            if skill_instructions:
                                instructions += '\n'+skill_instructions
                            prompt = CASES[case].format(finance_id=fixture.ground['Finance']['id'])
                            async def call(name,arguments):
                                return await fixture.intercept(client,case,name,arguments)
                            runner,calls = await evaluate(tools=tools,instructions=instructions,prompt=prompt,
                                call_tool=call,output=output/case,model=args.model,effort=args.effort,
                                timeout=args.timeout,codex=args.codex)
                        (output/case/'discovery.json').write_text(json.dumps({
                            'tools':[t.model_dump(mode='json',by_alias=True,exclude_none=True) for t in tools],
                            'capabilities':capability},indent=2)+'\n')
                        after = fixture.snapshot()
                        readonly = {name:fixture.app.state.operations.definition(name)['read_only']
                            for name in fixture.app.state.operations._operations}
                        result = grade(case,runner,calls,fixture.before,after,fixture.ground,readonly)
                        (output/case/'state.json').write_text(json.dumps({'before':fixture.before,'after':after,
                            'ground':fixture.ground,'effects':fixture.effects},indent=2)+'\n')
                        (output/case/'grade.json').write_text(json.dumps(result,indent=2)+'\n')
                        entry.update(status='passed' if result['passed'] else 'quality_failure',grade=result)
                    finally:
                        # Preserve actual effects even when the driver or a tool
                        # fails after a write. Never drop a failed case's evidence.
                        if hasattr(fixture,'before'):
                            try:
                                state={'before':fixture.before,'after':fixture.snapshot(),
                                    'ground':fixture.ground,'effects':fixture.effects}
                                (output/(case+'-state-final.json')).write_text(json.dumps(state,indent=2)+'\n')
                            except Exception as observer_error:
                                (output/(case+'-observer-failure.json')).write_text(json.dumps({
                                    'failure_type':type(observer_error).__name__})+'\n')
                        await fixture.close()
        except Exception as exc:
            entry.update(status='runner_or_fixture_failure',failure_type=type(exc).__name__)
            # Raw errors can include synthetic identities/URLs; retain privately.
            import traceback
            (output/(case+'-failure.txt')).write_text(traceback.format_exc())
        (output/'suite.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(case+': '+entry['status'],flush=True)
    return 0 if all(c['status']=='passed' for c in proof['cases']) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,help='New private output directory; never reuse a failed run')
    parser.add_argument('--plugin',type=Path,help='Generated plugin root; inject allowlisted skills/references and record exact hashes')
    parser.add_argument('--cases',nargs='+',choices=tuple(CASES))
    parser.add_argument('--model',default='gpt-6-astra')
    parser.add_argument('--effort',choices=('low','medium','high','xhigh'),default='high')
    parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--codex',default='codex')
    args = parser.parse_args(); args.database_url = os.getenv('CZERO_EVAL_DATABASE_URL')
    if not 10 <= args.timeout <= 180: parser.error('Case timeout must be 10–180 seconds')
    return asyncio.run(run(args))


if __name__=='__main__':
    raise SystemExit(main())
