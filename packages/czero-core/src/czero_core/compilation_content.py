# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Pure original-passage and readback identities, also usable by external clients."""
import hashlib
from datetime import datetime, timezone
from .compilation_schema import digest
from .receipts import snapshot


def passage(citation, quote, *, start_offset=None, end_offset=None):
    body = citation['body']
    if (type(quote) is not str or not quote or len(quote.encode()) > 8192
            or hashlib.sha256(body.encode()).hexdigest() != citation['content_hash']):
        raise ValueError('unsupported_compilation_passage')
    if start_offset is None:
        start_offset = citation['start_offset'] + body.find(quote)
        end_offset = start_offset + len(quote)
    if (type(start_offset) is not int or type(end_offset) is not int
            or not citation['start_offset'] <= start_offset < end_offset <= citation['end_offset']
            or body[start_offset-citation['start_offset']:end_offset-citation['start_offset']] != quote):
        raise ValueError('unsupported_compilation_passage')
    return {'chunk_id': str(citation['chunk_id']), 'start_offset': start_offset,
        'end_offset': end_offset, 'quote': quote}


def record_binding(kind, value):
    """Hash documented stable fields of a genuine current target read, never its receipt."""
    value = snapshot(value)
    if kind == 'page':
        fields = {k: value[k] for k in ('id','slug','title','revision','deleted')}
        fields['content'] = {k: value['content'][k] for k in ('id','number','content_hash','metadata')}
        content_id, content_hash = value['content']['id'], value['content']['content_hash']
    elif kind == 'entity':
        fields = {k: value[k] for k in ('id','kind','label','metadata','revision','deleted')}
        fields['aliases'] = sorted(value['aliases'], key=lambda a: a['normalized'])
        content_id, content_hash = None, None
    elif kind == 'claim':
        fields = {k: value[k] for k in ('id','entity_id','page_id','predicate','value','metadata',
            'revision','deleted','valid_from','valid_to','evidence_stale')}
        for key in ('valid_from','valid_to'):
            if fields[key] is not None:
                fields[key] = datetime.fromisoformat(fields[key].replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
        fields['evidence'] = sorted([{'chunk_id': e['chunk_id'],
            'unavailable': e.get('status') == 'superseded'} for e in value['evidence']], key=lambda e: e['chunk_id'])
        content_id, content_hash = None, None
    elif kind == 'relation':
        fields = {k: value[k] for k in ('id','source_id','target_id','kind','metadata','revision','deleted')}
        content_id, content_hash = None, None
    elif kind == 'link':
        fields = {k: value[k] for k in ('id','entity_id','target_kind','target_id')}
        if value.get('missing'):
            raise ValueError('compilation_target_unavailable')
        content_id, content_hash = None, None
    elif kind == 'annotation':
        fields = {k: value[k] for k in ('id','target','namespace','revision','value','status',
            'target_current','target_archived','current_content_revision')}
        content_id, content_hash = None, None
    else:
        raise ValueError('invalid_compilation_target_kind')
    return {'kind': kind, 'id': value['id'], 'revision': value.get('revision', 1),
        'content_id': content_id, 'content_hash': content_hash, 'record_hash': digest(fields)}


def navigation_body(synthesis, evidence, classification):
    """Shared rendering for production and the existing extractive experiment."""
    body = 'Derived navigation; unverified '+classification+'.\n\n'+synthesis+'\n\nOriginal evidence:\n'
    for support in evidence:
        body += '\n> '+support['quote'].replace('\n','\n> ')+'\n\nOriginal chunk: '+support['chunk_id']+'\n'
    return body
