#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Copy to an authorized private documentation job; keep configuration private."""
from pathlib import Path
import sys
from c0_freshdesk import main

if __name__=='__main__':
    job=Path(__file__).resolve().parent
    raise SystemExit(main([*sys.argv[1:],'--job',str(job),
        '--config',str(job/'config/freshdesk-project.json')]))
