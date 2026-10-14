# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""PostgreSQL connections and bounded readiness for reusable Core services."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

SCHEMA_REVISION = "0009_retrieval_text"


class Database:
    def __init__(self, url: str | None = None):
        url = url if url is not None else os.getenv("CZERO_DATABASE_URL", "")
        try:
            parsed = make_url(url)
        except Exception:
            raise ValueError("A valid CZERO_DATABASE_URL is required") from None
        if parsed.drivername != "postgresql+psycopg":
            raise ValueError("C0 requires PostgreSQL with the psycopg driver")
        self.engine = create_engine(parsed, pool_pre_ping=True, pool_size=5,
            max_overflow=2, pool_timeout=2, hide_parameters=True,
            connect_args={"connect_timeout": 2, "options": "-c statement_timeout=5000"})

    def health(self) -> dict[str, str]:
        try:
            with self.engine.connect() as connection:
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                vector_version = connection.execute(text(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )).scalar_one_or_none()
            if revision != SCHEMA_REVISION or not vector_version:
                return {"status": "unavailable", "reason": "schema_incompatible"}
            return {"status": "ok", "schema_revision": revision, "vector_version": vector_version}
        except SQLAlchemyError:
            # Do not return connection URLs, credentials or driver messages.
            return {"status": "unavailable", "reason": "database_unavailable"}

    def close(self) -> None:
        self.engine.dispose()
