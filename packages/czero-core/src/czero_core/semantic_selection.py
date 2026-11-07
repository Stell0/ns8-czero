# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Shared project/ordinary-space bounded rotation with risk-prioritized slots."""
from sqlalchemy import text


def select_wiki_review(connection, space_id, after, limit, now):
    params={'space':space_id,'limit':limit,'after':after}
    count=connection.execute(text('SELECT count(*) FROM c0_wiki_pages WHERE space_id=:space AND NOT deleted'),params).scalar_one()
    base='''SELECT p.id AS page_id,p.revision,r.id AS wiki_revision_id,r.content_hash FROM c0_wiki_pages p
        JOIN c0_wiki_revisions r ON r.page_id=p.id AND r.space_id=p.space_id AND r.number=p.revision
        WHERE p.space_id=:space AND NOT p.deleted'''
    ordered=' ORDER BY p.id LIMIT :limit'
    rows=list(connection.execute(text(base+(' AND p.id>CAST(:after AS uuid)' if after else '')+ordered),{**params,'limit':1}).mappings())
    if not rows and after:rows=list(connection.execute(text(base+ordered),{**params,'limit':1}).mappings())
    rotating=str(rows[0]['page_id']) if rows else after
    if rows and limit>1:
        ranked=base+''' AND p.id<>CAST(:rotate AS uuid) ORDER BY CASE WHEN EXISTS(SELECT 1 FROM c0_claims c
            WHERE c.space_id=p.space_id AND c.page_id=p.id AND NOT c.deleted AND
            (c.metadata->>'status' IN ('disputed','contradicted','outdated') OR c.metadata->>'consequential'='true'
            OR c.valid_to<:now OR EXISTS(SELECT 1 FROM c0_annotation_targets t JOIN c0_annotations a
                ON a.space_id=t.space_id AND a.anchor_id=t.id JOIN c0_annotation_revisions ar
                ON ar.space_id=a.space_id AND ar.annotation_id=a.id AND ar.number=a.revision
                WHERE t.space_id=c.space_id AND t.claim_id=c.id AND t.content_revision=c.revision
                AND ar.value->>'status' IN ('disputed','contradicted','outdated','not_applicable','superseded'))))
            THEN 1 ELSE 0 END DESC,p.updated_at DESC,p.id LIMIT :limit'''
        rows+=list(connection.execute(text(ranked),{**params,'rotate':rotating,'limit':limit-1,'now':now}).mappings())
    return count,rows,rotating
