# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import os

# The importable ASGI entry point uses the same per-instance value that NS8
# persists before starting the service.
os.environ.setdefault("CZERO_MODULE_ID", "czero99")

os.environ.setdefault("CZERO_DATABASE_URL", "postgresql+psycopg://czero@127.0.0.1:5432/czero")
