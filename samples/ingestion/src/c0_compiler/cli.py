# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Installed external runner. Never installs timers or enables compilation."""
import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import sys

from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from c0_ingest.state import encoded
from .config import load, install_key, private_file
from .runner import Runner


def main(argv=None):
    parser=argparse.ArgumentParser(description='External model-driven C0 knowledge compilation; installs no schedules')
    parser.add_argument('command',choices=('dry-run','daily','weekly','bootstrap','compile','status','recover'))
    parser.add_argument('--config',type=Path,required=True,help='Private JSON configuration path; no credentials in arguments')
    parser.add_argument('--apply',action='store_true',help='Authorize coordination/model work and policy-eligible publication')
    parser.add_argument('--tick',action='store_true',help='Run only the latest eligible local daily/weekly occurrence')
    parser.add_argument('--project-lease-file',type=Path,help='Existing project host workflow lease; no second project scheduler')
    args=parser.parse_args(argv)
    if args.tick and args.command not in ('daily','weekly'): parser.error('--tick requires daily or weekly')
    if args.command not in ('dry-run','status','recover') and not args.apply:
        parser.error('Execution requires --apply; start with dry-run')
    client=None;fd=None;previous=os.environ.get('C0_API_KEY');prior_logging=logging.root.manager.disable
    try:
        # SDK/HTTP library logs can carry challenged URLs or provider text.
        logging.disable(logging.CRITICAL)
        config=load(args.config)
        lock=Path(config['state_dir'])/'runner.lock'
        fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise C0Error('already_running') from None
        install_key(config)
        client=C0(config)
        client.space_id=config['space_id']  # Exact operation authorization is rechecked by Core.
        runner=Runner(client,config)
        if args.command=='recover' and args.apply:
            result=runner.recover()
        elif args.command in ('status','recover'):
            report=runner.inspect()
            result={'outcome':'reconcile_required' if runner.state.get('pending') or runner.state.get('model',{}).get('state')=='started' else 'inspected',
                'space_id':client.space_id,'tasks':report['status']['tasks'],'sources':report['status']['sources'],
                'run_id':runner.state.get('run_id'),'pending':runner.state.get('pending'),
                'model':runner.state.get('model'),'writes_c0':0}
        elif args.command=='dry-run':
            space,policy=runner.setup()
            result={'outcome':'dry_run','space_id':space['id'],'role':space['role'],
                'policy_revision':policy['revision'],'enabled':policy['data']['enabled'],
                'publication_mode':policy['data']['publication_mode'],'project_configured':runner.project is not None,
                'writes_c0':0,'model_calls':0}
        else:
            lease=json.loads(private_file(args.project_lease_file)) if args.project_lease_file else None
            result=runner.execute('manual' if args.command=='compile' else args.command,
                apply=True,tick=args.tick,project_lease=lease)
        print(encoded(result).decode(),flush=True)
        # Holds and incomplete work are observable failures for unattended hosts.
        return 0 if result['outcome'] in ('dry_run','inspected','not_due','completed_bounded') else 2
    except Exception:
        # No arbitrary exception/server/model/configuration text reaches stdout/stderr.
        print(json.dumps({'outcome':'blocked_or_uncertain','error_code':'inspect_private_state_and_c0_status'}),flush=True)
        return 1
    finally:
        if client:
            try: client.close()
            except Exception: pass
        logging.disable(prior_logging)
        if fd is not None: os.close(fd)
        if previous is None: os.environ.pop('C0_API_KEY',None)
        else: os.environ['C0_API_KEY']=previous


if __name__=='__main__':
    sys.exit(main())
