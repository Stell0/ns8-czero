# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded deterministic embedding context, separate from exact original evidence."""
from .extraction import Extracted, ExtractionError
from .structure import derive


def contextual_input(row):
    body = row['body']
    budget = min(256, 4096-len(body)-1)
    if budget <= 0:
        return body
    def label(value, limit):
        return ' '.join(value.split())[:limit] if isinstance(value, str) else ''
    metadata = row.get('metadata') or {}
    provenance = metadata.get('provenance') or {}
    if not isinstance(provenance, dict):
        provenance = {}
    labels = []
    for key, limit in (('product', 40), ('product_version', 24)):
        value = label(provenance.get(key), limit)
        if value:
            labels.append(key+': '+value)
    title = label(row.get('title'), 80)
    if title:
        labels.append('title: '+title)
    original = row.get('document_body', body)
    structure = row.get('structure')
    if structure is None and row.get('media_type') == 'text/markdown':
        try:
            structure = derive(Extracted(original, []), 'text/markdown')
        except ExtractionError:
            structure = None
    offset = row.get('start_offset', 0)
    headings = []
    for section in (structure or {}).get('sections', []):
        heading = section.get('heading')
        if heading and section['start'] <= offset < section['end']:
            headings.append(label(original[heading['start']:heading['end']], 80))
    if headings:
        labels.append('section: '+' > '.join(headings))
    prefix = '\n'.join(labels)[:budget]
    return prefix+'\n'+body if prefix else body
