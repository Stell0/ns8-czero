#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Copy into a private initialized job; uses its existing OAuth and target binding."""
from pathlib import Path
import sys
from c0_projects.cli import main

job=Path(__file__).resolve().parent
if len(sys.argv)<2:raise SystemExit('Choose scan, sync, resume, status, verify, login, bind-account or disconnect')
operation=sys.argv[1]
group='auth' if operation in ('login','bind-account','disconnect') else 'sources'
raise SystemExit(main([group,operation,'--config',str(job/'config/website.json'),'--job',str(job),*sys.argv[2:]]))
