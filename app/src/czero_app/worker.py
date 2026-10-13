# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import sys

from czero_core.worker import main
from czero_app.job_handlers import build_registry

if __name__ == "__main__":
    sys.exit(main(build_registry()))
