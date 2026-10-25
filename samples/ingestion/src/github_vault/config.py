# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration belongs to a private job, never the sample package."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import tomllib
from c0_ingest.config import connection_settings, dotenv
from c0_ingest.state import safe_path


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamps must include UTC offset')
    return result.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def load(path):
    if not path:
        raise ValueError('An explicit private --config path is required')
    path = Path(path).resolve()
    root = path.parent.parent
    config = tomllib.loads(path.read_text())
    c0 = connection_settings(root)
    config['c0'] = c0
    config['paths'] = {k: str(safe_path(root, v)) for k, v in config['paths'].items()}
    config['root'] = str(root)
    gh = config['github']
    if gh.get('concurrency', 1) != 1:
        raise ValueError('Only concurrency=1 is supported; page checkpoints are sequential')
    if not gh['organizations'] or any(not re.fullmatch('[A-Za-z0-9-]+', org) for org in gh['organizations']):
        raise ValueError('Configure valid GitHub organization names')
    for key in ('max_requests', 'max_wait_seconds', 'max_documents', 'max_file_bytes', 'max_review_prs'):
        if type(gh[key]) is not int or gh[key] <= 0:
            raise ValueError('GitHub bounds must be positive integers')
    if type(gh['max_retries']) is not int or not 0 <= gh['max_retries'] <= 10:
        raise ValueError('GitHub retries must be between zero and ten')
    for name in gh.get('pilot_repositories', []):
        if not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
            raise ValueError('Invalid pilot repository')
    if not isinstance(gh.get('priority_prefix', ''), str):
        raise ValueError('Repository priority prefix must be a string')
    return config


def parser(description, mode):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--config', required=True)
    p.add_argument('--resume', action='store_true')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--apply', action='store_true', help='Allow selected C0 mutations')
    p.add_argument('--limit-repos', type=positive)
    p.add_argument('--limit-people', type=positive)
    p.add_argument('--since')
    p.add_argument('--until')
    p.add_argument('--incremental', action='store_true')
    if mode in ('scrape', 'pipeline'):
        p.add_argument('--output')
        p.add_argument('--pilot', action='store_true')
        p.add_argument('--max-requests', type=positive)
        p.add_argument('--max-documents', type=positive)
    if mode == 'sync':
        p.add_argument('--input')
        p.add_argument('--space-name')
        p.add_argument('--validate-only', action='store_true')
    return p


def positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return n


def window(config, args):
    w = config['window']
    if type(w['rolling_days']) is not int or type(w['overlap_days']) is not int or w['rolling_days'] < 1 or w['overlap_days'] < 0:
        raise ValueError('Invalid rolling window/overlap')
    end = datetime.now(timezone.utc)
    since = (end - timedelta(days=w['rolling_days'] + w['overlap_days'])).isoformat() if args.incremental else w['since']
    until = end.isoformat() if args.incremental else w['until']
    result = {'since': timestamp(args.since or since), 'until': timestamp(args.until or until)}
    if result['since'] > result['until']:
        raise ValueError('since exceeds until')
    return result
