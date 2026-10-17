# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated values and fixed SQL predicates for opt-in content retrieval."""
from dataclasses import dataclass
from datetime import datetime

from .annotations import KINDS, _literal, _utc


@dataclass(frozen=True)
class StructuredFilters:
    categories: tuple[str, ...] = ('source', 'wiki')
    products: tuple[str, ...] | None = None
    components: tuple[str, ...] | None = None
    version_tags: tuple[str, ...] | None = None
    statuses: tuple[str, ...] | None = None
    verification_statuses: tuple[str, ...] | None = None
    archive: str = 'active'
    created_from: datetime | None = None
    created_to: datetime | None = None
    observed_from: datetime | None = None
    observed_to: datetime | None = None
    verified_from: datetime | None = None
    verified_to: datetime | None = None

    def __post_init__(self):
        for field in ('categories', 'products', 'components', 'version_tags', 'statuses', 'verification_statuses'):
            value = getattr(self, field)
            if value is None and field != 'categories':
                continue
            if type(value) not in (list, tuple) or not 1 <= len(value) <= (5 if field == 'categories' else 32):
                raise ValueError('invalid_structured_filter')
            values = tuple(dict.fromkeys(_literal(item) for item in value))
            if field == 'categories' and set(values) - {'source', 'wiki', 'entity', 'object', 'claim'}:
                raise ValueError('invalid_structured_category')
            object.__setattr__(self, field, values)
        if self.archive not in ('active', 'archived', 'all'):
            raise ValueError('invalid_archive_filter')
        for base in ('created', 'observed', 'verified'):
            for suffix in ('from', 'to'):
                key = base + '_' + suffix
                value = getattr(self, key)
                if value is not None:
                    object.__setattr__(self, key, datetime.fromisoformat(_utc(value)))
            lower, upper = getattr(self, base + '_from'), getattr(self, base + '_to')
            if lower is not None and upper is not None and lower > upper:
                raise ValueError('invalid_structured_interval')

    def _parameters(self):
        return {'filter_' + field: (list(value) if isinstance(value, tuple) else value)
                for field in ('products', 'components', 'version_tags', 'statuses', 'verification_statuses',
                              'created_from', 'created_to', 'observed_from', 'observed_to', 'verified_from', 'verified_to')
                if (value := getattr(self, field)) is not None}

    @staticmethod
    def _joins(kind, identifier, revision):
        # Expressions come only from the fixed domain query builders below.
        if kind not in KINDS:
            raise ValueError('invalid_annotation_target')
        return ''' LEFT JOIN c0_annotation_targets ft ON ft.space_id=:space AND ft.kind=''' + "'" + kind + "'" + '''
            AND ft.target_id=''' + identifier + ' AND ft.content_revision=' + revision + '''
            LEFT JOIN c0_annotations fa ON fa.space_id=ft.space_id AND fa.anchor_id=ft.id AND fa.namespace='applicability'
            LEFT JOIN c0_annotation_revisions far ON far.space_id=fa.space_id AND far.annotation_id=fa.id AND far.number=fa.revision
            LEFT JOIN c0_annotations fv ON fv.space_id=ft.space_id AND fv.anchor_id=ft.id AND fv.namespace='verification'
            LEFT JOIN c0_annotation_revisions fvr ON fvr.space_id=fv.space_id AND fvr.annotation_id=fv.id AND fvr.number=fv.revision '''

    def _predicate(self, created, archived):
        clauses = ['NOT (' + archived + ')' if self.archive == 'active' else '(' + archived + ')' if self.archive == 'archived' else 'TRUE']
        for field in ('products', 'components', 'version_tags'):
            if getattr(self, field) is not None:
                clauses.append("far.value->'" + field + "' ?| CAST(:filter_" + field + ' AS text[])')
        for field, alias in (('statuses', 'far'), ('verification_statuses', 'fvr')):
            if getattr(self, field) is not None:
                clauses.append("coalesce(" + alias + ".value->>'status','unknown')=ANY(CAST(:filter_" + field + ' AS text[]))')
        for base, expression in (('created', created), ('observed', "CAST(far.value->>'observed_at' AS timestamptz)"),
                                 ('verified', "CAST(fvr.value->>'verified_at' AS timestamptz)")):
            for suffix, operator in (('from', '>='), ('to', '<=')):
                key = base + '_' + suffix
                if getattr(self, key) is not None:
                    clauses.append(expression + operator + ':filter_' + key)
        return '(' + ') AND ('.join(clauses) + ')'

    @staticmethod
    def _columns():
        return '''coalesce(fa.revision,0) AS applicability_revision,far.value AS applicability_value,
            coalesce(fv.revision,0) AS verification_revision,fvr.value AS verification_value'''

    @staticmethod
    def _summaries(row):
        def summary(namespace):
            value = row[namespace + '_value']
            return {'revision': row[namespace + '_revision'], 'value': value,
                    'status': value.get('status', 'unknown') if value is not None else 'unknown'}
        return {'applicability': summary('applicability'), 'verification': summary('verification')}
