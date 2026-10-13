# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaged migrations, invoked by native NS8 units or an application harness."""
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .database import Database


def migrate_database(database: Database) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    # One transaction and lock cover schema changes, identity and version stamp.
    with database.engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(49371)"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def main() -> int:
    database = None
    try:
        database = Database()
        migrate_database(database)
        return 0
    except Exception as error:
        print(f"C0 database migration failed ({type(error).__name__})", file=sys.stderr)
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == "__main__":
    sys.exit(main())
