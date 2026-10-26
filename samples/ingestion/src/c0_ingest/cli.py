# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""A local command runner, not a scheduler or arbitrary adapter loader."""
import argparse
from pathlib import Path
import sys
from types import SimpleNamespace

from .auth import disconnect, locked, login
from .client import C0, SDKTransport
from .errors import C0Error
from .jobs import check_job, init_job
from .state import atomic, encoded


def set_env(job, key, value):
    if '\n' in value or '\r' in value:
        raise C0Error('Invalid private setting')
    path = job / '.env'
    lines = path.read_text().splitlines()
    lines = [line for line in lines if not line.startswith(key + '=')]
    atomic(path, ('\n'.join([*lines, key + '=' + value]) + '\n').encode())


def bind_account(config, job):
    transport = SDKTransport(config)
    try:
        profile = C0.decode('get_profile', transport.call('get_profile', {}))
        if (profile['nickname'] != config['identity'] or
                (config.get('account_id') and profile['id'] != config['account_id'])):
            raise C0Error('Account differs from the configured expected identity; refusing to bind')
        set_env(job, 'C0_ACCOUNT_ID', profile['id'])
        return {'status': 'bound', 'account_id': profile['id'], 'nickname': profile['nickname'], 'writes_c0': 0}
    finally:
        transport.close()


def execute(command, config, args):
    from github_vault.scrape import scrape
    from github_vault.sync import sync
    from github_vault.c0_client import inspect
    if command == 'inspect':
        return inspect(config), 0
    if command == 'scrape':
        return scrape(config, args)
    if command == 'sync':
        return sync(config, args)
    scraped, scrape_code = scrape(config, args)
    if args.dry_run:
        return {'status': 'dry_run', 'scrape': scraped, 'writes_c0': 0}, 0
    if scrape_code == 1:
        return {'status': 'scrape_failed', 'sync': 'not attempted; resolve snapshot errors first'}, 1
    sync_args = SimpleNamespace(**{**vars(args), 'input': scraped['snapshot'],
                                  'space_name': config['c0']['space_name'], 'validate_only': False})
    synced, code = sync(config, sync_args)
    return {'status': synced['status'], 'scrape': scraped, 'sync': synced}, code


def script_main(command):
    """Compatibility for the four supplied standalone script entry points."""
    from github_vault.config import load, parser
    mode = 'pipeline' if command == 'run' else command
    if command == 'inspect':
        p = argparse.ArgumentParser(description='Verify C0 account and discovered capabilities')
        p.add_argument('--config', required=True)
        p.add_argument('--check-auth', action='store_true')
        p.add_argument('--check-capabilities', action='store_true')
    else:
        p = parser('GitHub ' + command, mode)
    args = p.parse_args()
    if command in ('run', 'sync') and not args.dry_run and not args.apply and not getattr(args, 'validate_only', False):
        p.error('Choose --dry-run, --validate-only or --apply before updating C0')
    try:
        check_job(Path(args.config).resolve().parent.parent)
        config = load(args.config)
        with locked(Path(config['root']) / 'job.lock'):
            result, code = execute(command, config, args)
        print(encoded(result).decode(), flush=True)
        raise SystemExit(code)
    except Exception as exc:
        message = str(exc) if isinstance(exc, C0Error) else 'Invalid configuration or input; inspect private job files'
        print(encoded({'status': 'failed', 'error': message}).decode(), flush=True)
        raise SystemExit(1) from None


def main(argv=None):
    from github_vault.config import load, parser
    p = argparse.ArgumentParser(description='C0 sample ingestion and private update jobs')
    p.add_argument('--job', type=Path)
    p.add_argument('command', choices=('init', 'login', 'disconnect', 'bind-account', 'inspect', 'bootstrap', 'scrape', 'sync', 'run'))
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    args = p.parse_args(argv)
    if '--help' in args.arguments or '-h' in args.arguments:
        if args.command in ('scrape', 'sync', 'run'):
            parser('GitHub ' + args.command, 'pipeline' if args.command == 'run' else args.command).print_help()
        else:
            help_parser = argparse.ArgumentParser(prog='c0-ingest ' + args.command)
            if args.command == 'init':
                help_parser.add_argument('directory', help='New private job directory')
            elif args.command == 'bootstrap':
                help_parser.add_argument('--apply', action='store_true', help='Explicit Admin bootstrap')
            help_parser.print_help()
        return
    try:
        if args.command == 'init':
            if len(args.arguments) != 1:
                p.error('init requires a new private job directory')
            result, code = init_job(args.arguments[0]), 0
        else:
            if not args.job:
                p.error('--job is required')
            job = args.job.absolute()
            check_job(job)
            # Lock includes crawl checkpoints, sync receipts and interactive auth.
            with locked(job / 'job.lock'):
                config = load(job / 'config/source.toml')
                if args.command in ('login', 'disconnect', 'bind-account', 'bootstrap'):
                    if args.command == 'bootstrap':
                        if args.arguments != ['--apply']:
                            p.error('bootstrap requires --apply')
                        from github_vault.bootstrap import bootstrap
                        result = bootstrap(config['c0'])
                        set_env(job, 'C0_SPACE_ID', result['space_id'])
                    elif args.arguments:
                        p.error('Unexpected arguments')
                    elif args.command == 'login':
                        result = login(config['c0'])
                    elif args.command == 'disconnect':
                        result = disconnect(config['c0'])
                    else:
                        result = bind_account(config['c0'], job)
                    code = 0
                else:
                    mode = 'pipeline' if args.command == 'run' else args.command
                    if mode == 'inspect':
                        if args.arguments:
                            p.error('inspect takes no additional arguments')
                        selected = None
                    else:
                        selected = parser('GitHub ' + args.command, mode).parse_args(
                            ['--config', str(job / 'config/source.toml'), *args.arguments])
                        if args.command in ('run', 'sync') and not selected.dry_run and not selected.apply and not getattr(selected, 'validate_only', False):
                            p.error('Choose --dry-run, --validate-only or --apply before updating C0')
                    result, code = execute(args.command, config, selected)
        print(encoded(result).decode(), flush=True)
        raise SystemExit(code)
    except Exception as exc:
        # Only explicit C0Error messages are safe public diagnostics.
        message = str(exc) if isinstance(exc, C0Error) else 'Invalid configuration or input; inspect private job files'
        print(encoded({'status': 'failed', 'error': message}).decode(), flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
