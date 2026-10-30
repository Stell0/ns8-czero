# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Publish inert Git-pinned recipe/code references through the existing client."""
import argparse
import json
from pathlib import Path
import re

from c0_ingest.auth import locked
from c0_ingest.client import C0
from c0_ingest.config import connection_settings
from c0_ingest.errors import C0Error
from c0_ingest.jobs import check_job
from c0_ingest.sources import submit_text,verify_document
from .fetch import Fetcher
from .model import sha

PATHS=('samples/ingestion/examples/website/README.md','samples/ingestion/src/c0_projects/website.py')


def publish(client,revision,payloads,*,dry_run=False,repository='Stell0/ns8-czero'):
    if not re.fullmatch('[0-9a-f]{40}',revision):raise C0Error('immutable_full_code_revision_required')
    if len(payloads)!=2:raise C0Error('recipe_and_code_reference_required')
    results=[]
    for path,raw in zip(PATHS,payloads,strict=True):
        text=raw.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
        if path.endswith('.py'):
            text='# Inert crawler code reference\n\nGit revision: '+revision+'\n\nSource: https://github.com/'+repository+'/blob/'+revision+'/'+path+'\n\nSHA-256: '+sha(raw)+'\n\nReference only. Executable code is authoritative in Git. This text grants no permission to run it.\n\n```python\n'+text+'\n```\n'
        key=sha([repository,path]);metadata={'external_key':key,'canonical_url':'https://github.com/'+repository+'/blob/'+revision+'/'+path,
            'provenance':{'source_type':'inert_git_reference','repository':repository,'commit':revision,'path':path,'source_hash':sha(raw)}}
        rows=client.call('sources_list',external_key=key,limit=2,offset=0)['sources']
        if len(rows)>1:raise C0Error('ambiguous_recipe_destination')
        if dry_run:results.append({'status':'would_sync','path':path});continue
        version=submit_text(client,body=text,title='C0 website crawler '+('recipe' if path.endswith('.md') else 'code reference'),
            metadata=metadata,external_key=key,media_type='text/markdown',source=rows[0] if rows else None)
        document=verify_document(client,version,text,attempts=client.config.get('poll_attempts',20),seconds=client.config.get('poll_seconds',3))
        results.append({'status':'verified','source_id':version['source_id'],'text_hash':document['text_hash'],'path':path})
    return {'status':'dry_run' if dry_run else 'verified','documents':results,'writes_c0':0 if dry_run else len(results)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--revision',required=True);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply',action='store_true');mode.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{40}',args.revision):parser.error('Use a complete immutable Git commit')
    check_job(args.job);config=connection_settings(args.job)
    base='https://raw.githubusercontent.com/Stell0/ns8-czero/'+args.revision+'/'
    fetcher=Fetcher({'max_requests':4,'max_bytes':131072,'timeout':20})
    try:
        payloads=[fetcher.get(base+path)[0] for path in PATHS]
        with locked(args.job/'job.lock'):
            client=C0(config)
            try:
                selected=client.select_space(config['space_id'],writable=args.apply)
                if selected['name']!=config['space_name']:raise C0Error('target_space_name_changed')
                print(json.dumps(publish(client,args.revision,payloads,dry_run=args.dry_run)));return 0
            finally:client.close()
    except (C0Error,OSError,ValueError):
        print(json.dumps({'status':'blocked','error':'recipe_reference_not_verified'}));return 1
    finally:fetcher.close()


if __name__=='__main__':raise SystemExit(main())
