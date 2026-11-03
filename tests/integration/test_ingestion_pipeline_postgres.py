# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""M0 controls measure actual whole-document retries and lock interference."""
import hashlib
import json
import os
from pathlib import Path
import time

import pytest
from sqlalchemy import text

from czero_core.current_content import CONTENT_LOCK, ContentSuperseded
from czero_core.documents import DocumentService
from czero_core.extraction import ExtractionError
from czero_core.jobs import default_registry
from czero_core.worker import Worker, WORKER_LOCK
from test_access import access
from test_sources import sources, upload
from test_job_services import service as job_service

pytestmark = pytest.mark.skipif(not os.getenv("CZERO_TEST_DATABASE_URL"),
                                reason="disposable PostgreSQL required")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/evidence/pipeline"


def test_whole_document_retry_locks_and_atomic_replacement(sources, job_service, monkeypatch, record_property):
    import czero_core.sources as module
    service, owner, registry, _ = sources
    reader = DocumentService(service.database, service.access)
    previous = upload(sources, b"Previous complete evidence.", retain_original=True)
    worker = Worker(service.database, registry)
    worker.tick()
    previous_document = service.document(owner, previous["id"])
    previous_chunk = service.chunks(owner, previous_document["id"])[0]
    original = (FIXTURES / "readable-100.pdf").read_bytes()
    replacement = upload(sources, original, source_id=previous["source_id"],
                         expected_revision=1, media_type="application/pdf", retain_original=True)
    queue, queue_owner = job_service
    assert queue_owner == owner
    health = queue.enqueue(owner, "health", {}, "m0-health")
    parser = module.extract_isolated
    attempts = []

    def measured_parser(path, media_type):
        # Independent connection proves the production parser currently holds
        # both locks and a transaction; M1's opt-in path must reverse this control.
        with service.database.engine.begin() as observer:
            assert not observer.execute(text("SELECT pg_try_advisory_xact_lock(:key)"),
                                        {"key": CONTENT_LOCK}).scalar_one()
            assert not observer.execute(text("SELECT pg_try_advisory_xact_lock(:key)"),
                                        {"key": WORKER_LOCK}).scalar_one()
            assert observer.execute(text("SELECT count(*) FROM c0_documents WHERE version_id=:id"),
                                    {"id": replacement["id"]}).scalar_one() == 0
        assert Worker(service.database, default_registry()).tick() == 0
        assert reader.read_document(owner, previous["source_id"])["body"] == "Previous complete evidence."
        start = time.perf_counter()
        result = parser(path, media_type)
        attempts.append(time.perf_counter() - start)
        assert [location["index"] for location in result.locations] == list(range(1, 101))
        if len(attempts) == 1:
            # Deterministic lost-result failure after a real isolated full parse.
            raise ExtractionError("parser_timeout")
        return result

    monkeypatch.setattr(module, "extract_isolated", measured_parser)
    assert worker.tick(max_jobs=1) == 1
    assert queue.get_job(owner, health["id"])["state"] == "queued"
    assert service.versions(owner, replacement["source_id"])[0]["state"] == "failed"
    assert reader.read_document(owner, previous["source_id"])["revision_id"] == previous["id"]
    assert service.citation(owner, previous_chunk["id"])["source_hash"] == previous["content_hash"]
    assert not service.search(owner, "synthetic")
    # Safe parser errors are handled results in today's generic queue. They
    # require explicit source.retry, rather than automatic generic job retry.
    assert queue.get_job(owner, replacement["job_id"])["state"] == "succeeded"
    service.retry(owner, replacement["id"], expected_generation=1)
    started = time.perf_counter()
    worker.tick()
    publication_seconds = time.perf_counter() - started
    assert len(attempts) == 2
    assert queue.get_job(owner, health["id"])["state"] == "succeeded"
    started = time.perf_counter()
    full = reader.read_document(owner, replacement["source_id"])
    read_seconds = time.perf_counter() - started
    expected = "\n\n".join(f"Page {i:03d}: synthetic evidence {i:03d}." for i in range(1, 101))
    assert full["body"] == expected
    assert full["text_hash"] == hashlib.sha256(expected.encode()).hexdigest()
    assert service.search(owner, "synthetic")[0]["source_id"] == replacement["source_id"]
    with pytest.raises(ContentSuperseded):
        service.citation(owner, previous_chunk["id"])
    assert service.originals.path(replacement["id"]).read_bytes() == original
    record_property("m0_timings", json.dumps({"isolated_parse_seconds": attempts,
                    "retry_tick_seconds": publication_seconds, "full_read_seconds": read_seconds}))


def test_existing_writer_protocol_rejects_legacy_writes(sources):
    service, _, _, _ = sources
    # Trigger checks execute even for a no-op value update. A separate
    # transaction rolls back the test-local setting after rejection.
    version = upload(sources)
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError, match="writer protocol changed"):
        with service.database.engine.begin() as connection:
            connection.execute(text("SET LOCAL c0.content_protocol='0'"))
            connection.execute(text("UPDATE c0_source_versions SET state=state WHERE id=:id"),
                               {"id": version["id"]})
    with service.database.engine.begin() as connection:
        assert connection.execute(text("SHOW c0.content_protocol")).scalar_one() == "1"
        connection.execute(text("UPDATE c0_source_versions SET state=state WHERE id=:id"),
                           {"id": version["id"]})
