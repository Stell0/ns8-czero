# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import nullcontext
import hashlib
import runpy
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def test_database_secrets_are_private_stable_and_not_exported(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('AGENT_STATE_DIR',str(tmp_path))
    # Core supplies atomic rename/lock; this fixture checks the helper's
    # permissions, payload and idempotence without requiring a live agent.
    monkeypatch.setitem(sys.modules,'agent',SimpleNamespace(
        exclusive_file_lock=lambda path: nullcontext(), safe_open=lambda path: open(path,'w'),
        set_env=lambda *args: (_ for _ in ()).throw(AssertionError('secret exported'))))
    script = str(ROOT / 'imageroot/bin/czero-create-db-secrets')
    runpy.run_path(script)
    secret_file = tmp_path / 'passwords.env'
    assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
    data = dict(line.split('=',1) for line in secret_file.read_text().splitlines())
    assert set(data) == {'POSTGRES_PASSWORD','CZERO_DATABASE_URL'}
    assert len(data['POSTGRES_PASSWORD']) >= 40
    assert bool(data['POSTGRES_PASSWORD'] in data['CZERO_DATABASE_URL'])
    original = hashlib.sha256(secret_file.read_bytes()).digest()
    secret_file.chmod(0o644)
    runpy.run_path(script)
    assert original == hashlib.sha256(secret_file.read_bytes()).digest()
    assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
    assert capsys.readouterr().out == ''
