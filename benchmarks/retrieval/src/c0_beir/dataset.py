# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Strict BEIR JSONL/TSV validation and bounded, atomic dataset caching."""
import csv
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import zipfile

from c0_ingest.http import open_url
from c0_ingest.state import digest

KNOWN = ('scifact', 'nfcorpus', 'fiqa')
BASE_URL = 'https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/'
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXTRACTED = 2 * 1024 * 1024 * 1024


def records(path, corpus=False):
    result = {}
    with Path(path).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
                key = row['_id']
                if not isinstance(key, str) or not key or key in result:
                    raise ValueError('empty/duplicate ID')
                for field in (('title', 'text') if corpus else ('text',)):
                    value = row[field]
                    if not isinstance(value, str) or '\0' in value:
                        raise ValueError('invalid text')
                    value.encode('utf-8')
                if not (row['title'] + row['text'] if corpus else row['text']).strip():
                    raise ValueError('empty document/query')
                result[key] = {k: row[k] for k in ('title', 'text')} if corpus else row['text']
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise ValueError(f'Invalid BEIR record at {path.name}:{number}') from None
    if not result:
        raise ValueError(f'Empty BEIR file: {path.name}')
    return result


@dataclass
class Dataset:
    name: str
    split: str
    corpus: dict
    queries: dict
    qrels: dict
    fingerprint: str

    def body(self, key):
        row = self.corpus[key]
        return row['title'] + '\n\n' + row['text'] if row['title'] else row['text']

    def validate_ingestion(self):
        # One corpus item = one source. Never split or truncate benchmark originals.
        for key in self.corpus:
            if not 1 <= len(self.body(key).encode()) <= 131072:
                raise ValueError(f'BEIR document {key!r} exceeds the 131072-byte text-ingestion limit; no writes performed')


def load(path, name='scifact', split='test'):
    if not split or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in split):
        raise ValueError('Invalid BEIR split name')
    path = Path(path)
    corpus = records(path / 'corpus.jsonl', True)
    queries = records(path / 'queries.jsonl')
    qrels = {}
    with (path / 'qrels' / (split + '.tsv')).open(encoding='utf-8', newline='') as stream:
        reader = csv.reader(stream, delimiter='\t')
        if next(reader, None) != ['query-id', 'corpus-id', 'score']:
            raise ValueError('Expected BEIR qrels header: query-id, corpus-id, score')
        for number, row in enumerate(reader, 2):
            try:
                qid, docid, score = row
                score = int(score)
                if qid not in queries or docid not in corpus or docid in qrels.get(qid, {}) or score < 0:
                    raise ValueError
                qrels.setdefault(qid, {})[docid] = score
            except (ValueError, TypeError):
                raise ValueError(f'Invalid or missing BEIR relevance reference at qrels line {number}') from None
    if not qrels or any(not any(v > 0 for v in labels.values()) for labels in qrels.values()):
        raise ValueError('Every evaluated query must have at least one positive relevance judgment')
    # Includes all original query records and graded judgments, independent of file order.
    fingerprint = digest({'format': 1, 'corpus': corpus, 'queries': queries, 'qrels': qrels, 'split': split})
    return Dataset(name, split, corpus, queries, qrels, fingerprint)


def extract(archive, destination, name):
    """Accept only a single BEIR dataset tree; reject links, duplicates and zip bombs."""
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        if len(members) > 10000 or sum(m.file_size for m in members) > MAX_EXTRACTED:
            raise ValueError('BEIR archive exceeds extraction budget')
        seen = set()
        for member in members:
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (not path.parts or path.parts[0] != name or path.is_absolute()
                    or '..' in path.parts or '\\' in member.filename or member.filename in seen
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise ValueError('Unsafe BEIR archive member')
            seen.add(member.filename)
        for member in members:
            target = Path(destination).joinpath(*PurePosixPath(member.filename).parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)


def cached(name, cache, split='test'):
    if name not in KNOWN:
        raise ValueError('Unknown dataset; use --dataset-path for a compatible BEIR directory')
    cache = Path(cache)
    target = cache / name
    if target.exists():
        load(target, name, split)  # Corrupt caches fail explicitly, never redownload silently.
        return target
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache, prefix='.download-') as temporary:
        work = Path(temporary)
        archive = work / 'dataset.zip'
        print(f'Downloading BEIR {name} into local cache', flush=True)
        with open_url(urllib.request.Request(BASE_URL + name + '.zip'), timeout=60) as response, archive.open('wb') as output:
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > MAX_ARCHIVE:
                    raise ValueError('BEIR download exceeds archive budget')
                output.write(block)
        extract(archive, work, name)
        load(work / name, name, split)
        (work / name).rename(target)
    return target
