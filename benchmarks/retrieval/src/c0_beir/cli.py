# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Local command entry point. Configuration contains selectors, never credentials."""
import argparse
import json
import os
import re
from uuid import UUID
from pathlib import Path
import sys
import tomllib
import urllib.request

from c0_ingest.auth import credentials, destination, locked
from c0_ingest.client import C0
from c0_ingest.errors import C0Error
from c0_ingest.http import open_url
from .corpus import ingest, load_manifest
from .dataset import cached, load
from .evaluate import evaluate


def settings(args):
    path = args.config.resolve()
    with path.open('rb') as stream:
        config = tomllib.load(stream)
    unknown = set(config) - {'connection', 'benchmark'}
    if unknown:
        raise ValueError('Unknown configuration table')
    connection = config['connection']
    if not isinstance(connection, dict) or set(connection) != {'url', 'account_id', 'identity', 'space_id'} or not all(isinstance(v, str) and v for v in connection.values()):
        raise ValueError('Configure explicit C0 URL, account ID/name and protected space ID')
    connection = {**connection, 'auth_mode': 'api_key'}
    destination(connection)
    options = {'dataset': 'scifact', 'split': 'test', 'modes': ['text', 'semantic', 'hybrid'],
               'rerank': 'off', 'limit': 50, 'repetitions': 1, 'data_dir': 'data', 'state_dir': 'manifests',
               'results_dir': 'results', 'poll_attempts': 20, 'poll_seconds': 3, 'index_attempts': 20, 'excluded_wiki_pages': []}
    custom = config.get('benchmark', {})
    if not isinstance(custom, dict) or set(custom) - set(options) - {'dataset_path'}:
        raise ValueError('Unknown benchmark setting')
    options.update(custom)
    for name in ('dataset', 'split', 'rerank', 'limit', 'repetitions'):
        if getattr(args, name) is not None:
            options[name] = getattr(args, name)
    if args.mode:
        options['modes'] = args.mode
    if args.dataset_path:
        options['dataset_path'] = str(args.dataset_path.resolve())
    for name in ('data_dir', 'state_dir', 'results_dir', 'dataset_path'):
        if name in options:
            options[name] = (path.parent / options[name]).resolve()
    if (not isinstance(options['dataset'], str) or not options['dataset']
            or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in options['dataset'])):
        raise ValueError('Dataset name must be a simple directory label')
    if (not isinstance(options['modes'], list) or not options['modes'] or len(set(options['modes'])) != len(options['modes'])
            or any(mode not in ('text', 'semantic', 'hybrid') for mode in options['modes'])
            or options['rerank'] not in ('off', 'rerank', 'filter')
            or type(options['limit']) is not int or not 10 <= options['limit'] <= 50
            or type(options['repetitions']) is not int or not 1 <= options['repetitions'] <= 5
            or any(type(options[key]) is not int or not 1 <= options[key] <= 100 for key in ('poll_attempts', 'index_attempts'))
            or not isinstance(options['poll_seconds'], (int, float)) or not 0 <= options['poll_seconds'] <= 30):
        raise ValueError('Invalid retrieval configuration or bounded polling budget')
    exclusions=options['excluded_wiki_pages']
    if not isinstance(exclusions,list) or len(exclusions)>100:
        raise ValueError('Invalid excluded Wiki reports')
    seen=set()
    for page in exclusions:
        if (not isinstance(page,dict) or set(page)!={'page_id','revision','content_hash'}
                or type(page['revision']) is not int or page['revision']<1
                or not isinstance(page['content_hash'],str)
                or not re.fullmatch('[0-9a-f]{64}',page['content_hash'])):
            raise ValueError('Invalid excluded Wiki reports')
        try: key=str(UUID(page['page_id']))
        except (ValueError,TypeError,AttributeError): raise ValueError('Invalid excluded Wiki reports') from None
        if key!=page['page_id'] or key in seen:
            raise ValueError('Invalid excluded Wiki reports')
        seen.add(key)
    return connection, options


def instance_version(config):
    """Best-effort public health metadata; no authorization headers or mutations."""
    origin, _ = destination(config)
    try:
        with open_url(urllib.request.Request(origin + '/api/v1/health'), timeout=10) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError
        value = json.loads(raw)
        return {key: value[key] for key in ('app_version', 'version', 'schema_version', 'status') if key in value}
    except (OSError, ValueError, TypeError):
        return {'status': 'version_metadata_unavailable'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Reproducible BEIR retrieval over C0 public APIs; local development only')
    parser.add_argument('command', choices=('ingest', 'evaluate'))
    parser.add_argument('--config', type=Path, default=Path('.local/benchmark/config.toml'))
    parser.add_argument('--dataset')
    parser.add_argument('--dataset-path', type=Path)
    parser.add_argument('--split')
    parser.add_argument('--mode', choices=('text', 'semantic', 'hybrid'), action='append')
    parser.add_argument('--rerank', choices=('off', 'rerank', 'filter'))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--repetitions', type=int)
    args = parser.parse_args(argv)
    os.umask(0o077)
    client = None
    try:
        connection, config = settings(args)
        credentials(connection)  # Environment only; no OAuth refresh or credential writes.
        with locked(config['state_dir'] / 'benchmark.lock'):
            path = config.get('dataset_path') or cached(config['dataset'], config['data_dir'], config['split'])
            dataset = load(path, config['dataset'], config['split'])
            print(f'Validated {dataset.name}: {len(dataset.corpus)} documents, {len(dataset.qrels)} eligible queries; {dataset.fingerprint}', flush=True)
            client = C0(connection)
            client.excluded_wiki_pages = config['excluded_wiki_pages']
            space = client.select_space(connection['space_id'], writable=args.command == 'ingest')
            if space['shared']:
                raise C0Error('Benchmark requires an explicitly selected protected space, never Shared')
            if args.command == 'ingest':
                operation = client.operations.get('sources_ingest_text', {})
                if not operation or operation.get('read_only'):
                    raise C0Error('Source ingestion unavailable under current scopes')
            manifest_path = config['state_dir'] / (dataset.name + '-' + dataset.split + '.json')
            if args.command == 'ingest':
                ingest(client, dataset, manifest_path, attempts=config['poll_attempts'], seconds=config['poll_seconds'],
                       index_attempts=config['index_attempts'])
            else:
                client.benchmark_version = instance_version(connection)
                summary = evaluate(client, dataset, load_manifest(manifest_path, client, dataset), config['results_dir'],
                    modes=config['modes'], rerank=config['rerank'], limit=config['limit'], repetitions=config['repetitions'])
                return 0 if summary['comparison_valid'] else 2
    except (C0Error, ValueError, OSError, KeyError, TypeError):
        # Unexpected parser/transport text can contain private server payloads or credentials.
        # Expected diagnostics are printed separately only for our value-free C0Error.
        exc = sys.exception()
        message = str(exc) if isinstance(exc, (C0Error, ValueError)) and not isinstance(exc, tomllib.TOMLDecodeError) else 'Check private configuration, dataset files and local permissions'
        print('benchmark: ' + message, file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()
    return 0
