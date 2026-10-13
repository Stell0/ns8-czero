# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from alembic import context

# Core supplies a live transactional connection; no secret URL in config files.
context.configure(connection=context.config.attributes["connection"], target_metadata=None)
with context.begin_transaction():
    context.run_migrations()
