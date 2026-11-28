# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare public, source-bound question labels for the web/KB experiment."""
import argparse
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler

def public_selection():
    filename = os.environ.get("WEB_KB_PUBLIC_SELECTION")
    if not filename:
        raise ValueError("Set WEB_KB_PUBLIC_SELECTION to the private public-source selection JSON")
    selected = read(filename)
    definitions = {str(UUID(key)): (row["repository"].lower(), set(row["kinds"]))
                   for key, row in selected["definitions"].items()}
    if not definitions or any(not kinds or kinds - {"documentation", "issue"} or
                              not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", repo)
                              for repo, kinds in definitions.values()):
        raise ValueError("Invalid public collection selection")
    return str(UUID(selected["space_id"])), definitions


def read(path):
    return json.loads(Path(path).read_text())


def digest(data):
    return sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, staged = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.link(staged, path)
    finally:
        os.unlink(staged)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('public original redirected; review the canonical URL')


class IssuePage(HTMLParser):
    """Read the public issue body, excluding discussion replies and page chrome."""
    def __init__(self):
        super().__init__()
        self.script = False
        self.post = None

    def handle_starttag(self, tag, attributes):
        if tag == 'script':
            self.script = dict(attributes).get('type') == 'application/ld+json'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.script = False

    def handle_data(self, data):
        if self.script:
            obj = json.loads(data)
            if isinstance(obj, dict) and obj.get('@type') == 'DiscussionForumPosting':
                self.post = obj


def public_target(source):
    """Check metadata before reading either original."""
    space, definitions = public_selection()
    if source['definition_id'] not in definitions:
        raise ValueError('unexpected public source provenance')
    repo, kinds = definitions[source['definition_id']]
    kind = source['source_type']
    url = urlsplit(source['url'])
    parts = url.path.lstrip('/').split('/')
    if (source['space_id'] != space or kind not in kinds or url.scheme != 'https'
            or url.netloc != 'github.com' or url.query or url.fragment
            or '/'.join(parts[:2]).lower() != repo or len(parts) < 4
            or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) or p in ('.', '..') for p in parts)):
        raise ValueError('unexpected public source provenance')
    target = source['url']
    if kind == 'documentation':
        if (parts[2] != 'blob' or len(parts) < 5 or not re.fullmatch('[a-f0-9]{40}', parts[3])
                or not parts[-1].lower().endswith(('.md', '.rst')) or 'faq' in url.path.lower()):
            raise ValueError('expected pinned public documentation')
        target = 'https://raw.githubusercontent.com/' + '/'.join(parts[:2] + parts[3:])
    elif parts[2] != 'issues' or len(parts) != 4 or not parts[3].isdigit():
        raise ValueError('expected public issue')
    return target


def public_source(source):
    target = public_target(source)
    if not source['revision'] or sha256(source['body'].encode()).hexdigest() != source['sha256']:
        raise ValueError('missing or changed C0 original')
    with build_opener(NoRedirect()).open(target, timeout=30) as response:
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024 or response.status != 200:
            raise ValueError('public original unreadable')
    body = data.decode()
    if source['source_type'] == 'issue':
        page = IssuePage()
        page.feed(body)
        if not page.post or page.post['url'].lower() != source['url'].lower():
            raise ValueError('public issue identity mismatch')
        body = page.post['headline'] + '\n\n' + page.post['articleBody']
    return dict(source, public_body=body, public_checked_at=datetime.now(timezone.utc).isoformat())


def validate(questions):
    if not isinstance(questions, list) or len(questions) != 100:
        raise ValueError('expected 100 questions')
    if Counter((q['language'], q['source_type']) for q in questions) != {
            (lang, kind): 25 for lang in ('en', 'it') for kind in ('documentation', 'issue')}:
        raise ValueError('expected 25 questions in each language/source stratum')
    if Counter(q['disposition'] for q in questions) != {'answer': 90, 'clarify': 10}:
        raise ValueError('expected 90 answerable and 10 clarification questions')
    for key in ('id', 'question'):
        if len({q[key].strip().casefold() for q in questions}) != len(questions):
            raise ValueError('duplicate ' + key)
    for q in questions:
        if (not all(isinstance(q[key], str) and q[key].strip()
                    for key in ('id', 'question', 'expected_answer', 'product', 'version'))
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', q['id'])
                or '://' in q['question']
                or not isinstance(q['required_facts'], list) or not q['required_facts']
                or not all(isinstance(f, str) and f.strip() for f in q['required_facts'])
                or not isinstance(q['evidence'], list) or not q['evidence']):
            raise ValueError('incomplete question or label: ' + str(q.get('id')))
    return questions


def freeze(proposal, sources, audit):
    questions = validate(proposal['questions'])
    approvals = set(audit['approved_ids'])
    if (audit['proposal_sha256'] != digest(proposal) or audit['sources_sha256'] != digest(sources)
            or approvals != {q['id'] for q in questions} or not audit['reviewer'].strip()
            or not proposal['generator'].strip() or audit['reviewer'] == proposal['generator']):
        raise ValueError('independent source-bound review required for every question')
    originals = {s['url']: s for s in sources}
    if len(originals) != len(sources):
        raise ValueError('duplicate source URL')
    for question in questions:
        for e in question['evidence']:
            s = originals[e['url']]
            quote = e['quote']
            if (not isinstance(quote, str) or not quote.strip()
                    or quote not in s['body'] or quote not in s['public_body']):
                raise ValueError('passage missing in C0 or anonymous public original: ' + question['id'])
        if originals[question['evidence'][0]['url']]['source_type'] != question['source_type']:
            raise ValueError('primary source type mismatch')
    result = {'schema': 1, 'questions': questions, 'source_manifest': [
        {key: s[key] for key in ('id', 'url', 'revision', 'sha256', 'public_checked_at', 'source_type')}
        for s in sources], 'audit': audit, 'generator': proposal['generator']}
    return dict(result, pack_sha256=digest(result))


def load_pack(path):
    obj = read(path)
    checksum = obj.pop('pack_sha256')
    if obj.get('schema') != 1 or digest(obj) != checksum:
        raise ValueError('invalid or modified frozen pack')
    return validate(obj['questions'])


async def capture_sources(limit_per_kind=65):
    """Read a bounded sample through the real broker; select metadata before bodies."""
    from web_kb_episode import Blocked, server, start_thread

    space, definitions = public_selection()
    if not 1 <= limit_per_kind <= 65:
        raise ValueError('capture limit must be between 1 and 65')
    async with asyncio.timeout(1800), server(True) as broker:
        thread = await start_thread(broker)

        async def call(name, **args):
            result = await broker.request('mcpServer/tool/call', {
                'threadId': thread, 'server': 'codex_apps', 'tool': 'kbnethesis.' + name,
                'arguments': args})
            if result.get('isError'):
                raise Blocked('Connector capture failed at ' + name)
            structured = result.get('structuredContent')
            if isinstance(structured, dict):
                return structured
            return json.loads(next(item['text'] for item in result['content'] if item['type'] == 'text'))

        selected = await call('spaces_get', space_id=space)
        if selected.get('id') != space:
            raise Blocked('Nethesis Documentation unavailable')
        candidates = []
        for definition, (_, kinds) in definitions.items():
            if 'documentation' not in kinds:
                continue
            rows = (await call('automatic_source_documents_list', space_id=space,
                               identifier=definition, limit=100))['documents']
            for row in rows:
                path = row['title'].lower()
                if row['deleted'] or 'faq' in path or not path.endswith(('.md', '.rst')):
                    continue
                candidates.append((row['id'], definition, 'documentation'))
        issues = 0
        for offset in range(0, 500, 100):
            docs = (await call('source_documents_list', space_id=space,
                               limit=100, offset=offset))['documents']
            for row in docs:
                meta = row['metadata']
                definition = meta.get('automatic_source_id')
                if ('issue' not in definitions.get(definition, ('', set()))[1]
                        or not re.fullmatch(r'https://github.com/[^/]+/[^/]+/issues/\d+', meta.get('original_url', ''))
                        or re.search(r'faq|exploit|vulnerab|privilege escalation|CVE-', row['title'], re.I)
                        or row['state'] != 'ready'):
                    continue
                candidates.append((row['id'], definition, 'issue'))
                issues += 1
                if issues == max(5, limit_per_kind):
                    break
            if issues == max(5, limit_per_kind) or len(docs) < 100:
                break
        originals = []
        counts = Counter()
        for ident, definition, kind in candidates:
            if counts[kind] >= limit_per_kind:
                continue
            summary = await call('sources_get', space_id=space, source_id=ident)
            metadata = summary['metadata']
            if (summary['id'] != ident or summary['deleted']
                    or metadata.get('automatic_source_id') != definition):
                raise ValueError('KB source identity changed after selection')
            source = dict(id=ident, url=metadata['original_url'], title=summary['title'],
                          space_id=space, source_type=kind, definition_id=definition)
            public_target(source)
            doc = await call('source_documents_get', space_id=space, logical_document_id=ident)
            meta = doc['metadata']
            if (doc['id'] != ident or meta.get('automatic_source_id') != definition
                    or meta['original_url'] != source['url'] or doc.get('deleted') or doc['state'] != 'ready'):
                raise ValueError('KB source identity changed during capture')
            if isinstance(doc.get('body'), str) and 700 <= len(doc['body']) <= 100000:
                originals.append(dict(source, body=doc['body'], revision=doc['revision_id'], sha256=doc['text_hash']))
                counts[kind] += 1
        if not counts['documentation'] or not counts['issue']:
            raise ValueError('public-source capture requires both documentation and issues')
    return originals


def verify_public(capture):
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(public_source, capture))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    check = sub.add_parser('verify-public', help='verify selected connector reads against anonymous originals')
    check.add_argument('--capture', required=True)
    check.add_argument('--output', required=True)
    capture = sub.add_parser('capture', help='select scoped KB originals and verify them anonymously')
    capture.add_argument('--output', required=True)
    capture.add_argument('--limit-per-kind', type=int, default=65, help='1 for a two-original capture smoke')
    pack = sub.add_parser('freeze')
    for key in ('proposal', 'sources', 'audit', 'output'):
        pack.add_argument('--' + key, required=True)
    hash_cmd = sub.add_parser('digest', help='print canonical JSON digest for an independent review')
    hash_cmd.add_argument('file')
    args = parser.parse_args()
    if args.action == 'verify-public':
        save(args.output, verify_public(read(args.capture)))
    elif args.action == 'capture':
        save(args.output, verify_public(asyncio.run(capture_sources(args.limit_per_kind))))
    elif args.action == 'digest':
        print(digest(read(args.file)))
    else:
        save(args.output, freeze(read(args.proposal), read(args.sources), read(args.audit)))


if __name__ == '__main__':
    main()
