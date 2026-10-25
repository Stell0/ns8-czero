#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Offline checks for maintained Markdown and retained historical anchors."""
from collections import Counter
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ('installation-candidate', 'index', 'user-guide', 'administration', 'chatgpt', 'plugin',
          'development', 'reference', 'workspace-access', 'release-readiness', 'ci-policy',
          'tool-evaluations', 'retrieval-benchmark', 'c0-agent-memory-baseline',
          'm14-readiness', 'm14-release-notes')
MAINTAINED = ('README.md', 'AGENTS.md', 'PLAN.md',
               'samples/ingestion/README.md',
               *('docs/' + name + '.md' for name in GUIDES),
               'docs/history/README.md', 'docs/history/AGENTS.md', 'docs/history/PLAN.md',
               *('.agents/skills/' + name + '/SKILL.md' for name in (
                   'c0-create-feature', 'c0-develop-core', 'c0-contribute-upstream',
                   'c0-upgrade-from-upstream', 'c0-evaluate-tools', 'c0-ingest-sources')))


def prose(text):
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return '\n'.join(lines)


def headings(text):
    used = Counter()
    result = []
    for line in prose(text).splitlines():
        match = re.match(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$', line)
        if not match:
            continue
        label = match[1]
        plain = html.unescape(re.sub(r'<[^>]*>', '', label))
        plain = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', plain).replace('`', '')
        slug = ''.join(c for c in plain.lower() if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ', '-')
        original = slug
        while used[slug]:
            used[original] += 1
            slug = original + '-' + str(used[original] - 1)
        used[slug] += 1
        result.append((slug, label))
    return result


class Attributes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs)
        if value.get('id'):
            self.ids.append(value['id'])
        if tag == 'a' and 'href' in value:
            self.links.append(value['href'])


def anchors(text):
    parser = Attributes()
    parser.feed(prose(text))
    return [slug for slug, _ in headings(text)] + parser.ids


def links(text):
    value = prose(text)
    # Preserve code spans inside headings for slugs, but do not interpret
    # literal Markdown examples in inline code as navigation.
    value = re.sub(r'`+[^`]*`+', '', value)
    parser = Attributes()
    parser.feed(value)
    found = re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^)]*)?\)', value)
    found += re.findall(r'^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|[^\s]+)', value, re.M)
    return [html.unescape(item.strip('<>')) for item in found] + parser.links


def check(paths=MAINTAINED, root=ROOT):
    root = Path(root).resolve()
    checked = 0
    errors = []
    for relative in paths:
        source = root / relative
        if not source.is_file() or source.is_symlink():
            errors.append(str(relative) + ': missing or unsafe document')
            continue
        try:
            text = source.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append(str(relative) + ': invalid UTF-8')
            continue
        if '\0' in text or re.search(r'^(?:<<<<<<<|=======|>>>>>>>)\s', text, re.M):
            errors.append(str(relative) + ': invalid text or conflict marker')
        ids = anchors(text)
        if len(ids) != len(set(ids)):
            errors.append(str(relative) + ': duplicate document anchor')
        for target in links(text):
            parsed = urlsplit(target)
            if parsed.scheme in ('http', 'https', 'mailto') or target.startswith('//'):
                continue
            if parsed.scheme or parsed.netloc or target.startswith('/'):
                errors.append(str(relative) + ': unsupported local link ' + target)
                continue
            path = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not path.is_relative_to(root) or not path.is_file():
                errors.append(str(relative) + ': missing local link ' + target)
            elif parsed.fragment and path.suffix == '.md' and unquote(parsed.fragment) not in anchors(path.read_text(encoding='utf-8')):
                errors.append(str(relative) + ': missing anchor ' + target)
            checked += 1
    if errors:
        raise ValueError('\n'.join(errors))
    return checked


if __name__ == '__main__':
    print('Maintained documentation and historical links pass: ' + str(check()) + ' local links')
