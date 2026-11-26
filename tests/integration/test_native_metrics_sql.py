# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url


METRICS_SQL = Path(__file__).resolve().parents[2] / 'imageroot/etc/metrics/czero.sql'
pytestmark = pytest.mark.skipif(not os.getenv('CZERO_TEST_DATABASE_URL'), reason='isolated PostgreSQL required')


def test_metrics_sql_excludes_expired_leases_and_unexchanged_grants():
    url = make_url(os.environ['CZERO_TEST_DATABASE_URL']).set(drivername='postgresql')
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
        with conn.cursor() as cur:
            # Use temp views to isolate a small aggregate fixture from the shared schema.
            cur.execute("""
                CREATE TEMP VIEW c0_sources AS SELECT * FROM
                    (VALUES (1,false,1), (2,true,2)) AS sources(id,deleted,current_version_id);
                CREATE TEMP VIEW c0_source_versions AS SELECT 1 AS source_id, 'failed' AS state,
                    'encrypted_pdf' AS error_code;
                CREATE TEMP VIEW c0_documents AS SELECT 1 AS version_id UNION ALL SELECT 2;
                CREATE TEMP VIEW c0_wiki_pages AS SELECT false AS deleted;
                CREATE TEMP VIEW c0_entities AS SELECT false AS deleted;
                CREATE TEMP VIEW c0_sessions AS SELECT *,
                    now()+interval '1 hour' AS expires_at FROM
                    (VALUES (now()-interval '1 minute'), (NULL), (now()+interval '1 minute'))
                    AS leases(browser_idle_until);
                CREATE TEMP VIEW c0_oauth_clients AS SELECT * FROM
                    (VALUES (1,true,1), (2,false,1)) AS clients(id,enabled,revision);
                CREATE TEMP VIEW c0_oauth_grants AS SELECT *, false AS persistent, NULL::timestamptz AS idle_until,
                    now()+interval '1 hour' AS expires_at FROM
                    (VALUES (1,1,1), (2,1,1), (3,1,2), (4,2,1)) AS grants(id,client_id,client_revision);
                CREATE TEMP VIEW c0_oauth_tokens AS SELECT grant_id FROM
                    (VALUES (1), (3), (4)) AS tokens(grant_id);
                CREATE TEMP VIEW c0_scheduled_tasks AS SELECT true AS enabled;
                CREATE TEMP VIEW c0_jobs AS SELECT 'queued' AS state;
                CREATE TEMP VIEW c0_extraction_runs AS SELECT 'extracting' AS state,
                    now()+interval '1 hour' AS expires_at;
            """)
            cur.execute(METRICS_SQL.read_text())
            while cur.description is None:
                assert cur.nextset()
            (output,) = cur.fetchone()
            assert output['inventory']['browser_sessions'] == 2
            assert output['inventory']['assistant_connections'] == 1
            assert output['inventory']['documents'] == 1
            assert output['source_failures'] == {'protected_pdf': 1}
            assert output['jobs'] == {'queued': 1}
            assert output['extraction_runs'] == {'extracting': 1}
