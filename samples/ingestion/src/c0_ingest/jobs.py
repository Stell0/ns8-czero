# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private jobs contain configuration and state, not copied shared logic."""
from pathlib import Path
import os
import subprocess
from .errors import C0Error

ENV = '''# Private literal instance configuration; never source this as shell code.
C0_URL=https://c0.example.org/mcp
C0_ACCOUNT_NAME=alice
C0_ACCOUNT_ID=
C0_SPACE_NAME=GitHub projects
C0_SPACE_ID=
C0_CLIENT_ID=REPLACE_WITH_APPROVED_INGESTION_CLIENT_ID
C0_REDIRECT_URI=http://127.0.0.1:43220/callback/c0-ingestion
C0_SCOPES=c0:read c0:write
'''

SOURCE = '''[github]
organizations = ["acme"]
pilot_repositories = ["acme/example-project"]
priority_prefix = ""
people_seed = ""
repository_seed = ""
max_requests = 300
max_retries = 3
max_wait_seconds = 60
concurrency = 1
max_documents = 5
max_file_bytes = 131072
extensions = [".md", ".markdown", ".rst", ".txt"]
max_review_prs = 50
external_discovery = true

[window]
since = "2024-01-01T00:00:00Z"
until = "2025-12-31T23:59:59Z"
rolling_days = 730
overlap_days = 7

[sync]
publish_wiki = false

[paths]
snapshots = "data/snapshots"
state = "data/state"
reports = "data/reports"
'''

RUNNER = '''#!/usr/bin/env python3
"""This instance's update entry point; configuration and state stay here."""
from pathlib import Path
import sys
from c0_ingest.cli import main
if __name__ == "__main__":
    main(["--job", str(Path(__file__).resolve().parent), *sys.argv[1:]])
'''


def init_job(path):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise C0Error('Choose a new job directory whose parent exists')
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise C0Error('Private jobs cannot use symlinked directories')
    repo = subprocess.run(['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if repo.returncode == 0:
        check = subprocess.run(['git', '-C', repo.stdout.strip(), 'check-ignore', '--quiet', str(path / 'run.py')])
        if check.returncode:
            raise C0Error('Private job directory must be git ignored before initialization')
    path.mkdir(mode=0o700)
    (path / 'config').mkdir(mode=0o700)
    for name, text in [('.env', ENV), ('config/source.toml', SOURCE), ('run.py', RUNNER),
                       ('NOTES.md', '# Private ingestion notes\n\nRecord target mappings, recovery and actual run evidence here.\n')]:
        fd = os.open(path / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
    return {'status': 'initialized', 'job': str(path), 'writes_c0': 0}


def check_job(path):
    path = Path(path).absolute()
    if (any(parent.is_symlink() for parent in (path, *path.parents))
            or (path / '.env').is_symlink() or (path / 'config').is_symlink()
            or (path / 'config/source.toml').is_symlink()
            or path.stat().st_mode & 0o077 or (path / '.env').stat().st_mode & 0o077):
        raise C0Error('Job directory and .env must be private (0700/0600), without symlinks')
    repo = subprocess.run(['git', '-C', str(path), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    if repo.returncode == 0:
        tracked = subprocess.check_output(['git', '-C', repo.stdout.strip(), 'ls-files', '--', str(path)])
        ignored = subprocess.run(['git', '-C', repo.stdout.strip(), 'check-ignore', '--quiet', str(path / 'run.py')])
        if tracked or ignored.returncode:
            raise C0Error('Private job is tracked or not git ignored; stop before running')
