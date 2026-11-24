-- Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '3s';
SET LOCAL lock_timeout = '500ms';

WITH live_versions AS (
    SELECT v.state, v.error_code
    FROM c0_source_versions v JOIN c0_sources s ON s.id = v.source_id
    WHERE NOT s.deleted
), failure_groups AS (
    SELECT CASE
        WHEN error_code IN ('encrypted_pdf', 'pdf_password_required', 'pdf_password_incorrect',
            'pdf_extraction_approval_required', 'pdf_unlock_unavailable') THEN 'protected_pdf'
        WHEN error_code IN ('invalid_pdf', 'invalid_docx', 'invalid_text', 'invalid_file') THEN 'unreadable'
        WHEN error_code IN ('unsupported_scan', 'no_text', 'ocr_unavailable') THEN 'no_text'
        WHEN error_code IN ('too_large', 'pdf_too_many_pages', 'resource_limit', 'parser_timeout') THEN 'limits'
        ELSE 'other'
    END AS reason
    FROM live_versions WHERE state = 'failed'
)
SELECT json_build_object(
    'inventory', json_build_object(
        'sources', (SELECT count(*) FROM c0_sources WHERE NOT deleted),
        'documents', (SELECT count(*) FROM c0_documents),
        'wiki_pages', (SELECT count(*) FROM c0_wiki_pages WHERE NOT deleted),
        'entities', (SELECT count(*) FROM c0_entities WHERE NOT deleted),
        'browser_sessions', (SELECT count(*) FROM c0_sessions WHERE expires_at > now()),
        'assistant_connections', (SELECT count(*) FROM c0_oauth_grants
            WHERE CASE WHEN persistent THEN idle_until ELSE expires_at END > now()),
        'schedules', (SELECT count(*) FROM c0_scheduled_tasks WHERE enabled)
    ),
    'source_versions', (SELECT json_object_agg(key, value)
        FROM (SELECT state AS key, count(*) AS value FROM live_versions GROUP BY state) AS states),
    'source_failures', (SELECT json_object_agg(key, value)
        FROM (SELECT reason AS key, count(*) AS value FROM failure_groups GROUP BY reason) AS reasons),
    'jobs', (SELECT json_object_agg(key, value)
        FROM (SELECT state AS key, count(*) AS value FROM c0_jobs GROUP BY state) AS states),
    'extraction_runs', (SELECT json_object_agg(key, value)
        FROM (SELECT state AS key, count(*) AS value FROM c0_extraction_runs WHERE expires_at > now() GROUP BY state) AS runs)
);
ROLLBACK;
