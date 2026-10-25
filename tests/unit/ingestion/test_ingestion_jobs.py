# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import subprocess
import pytest
from c0_ingest.jobs import init_job, check_job
from c0_ingest.cli import main
from c0_ingest.errors import C0Error
from github_vault.config import dotenv, load, parser
from github_vault.discover import seeds


def test_job_creates_private_runner_env_and_config_without_credentials(tmp_path):
    job = tmp_path / 'job'
    result = init_job(job)
    assert result['writes_c0'] == 0
    check_job(job)
    assert job.stat().st_mode & 0o777 == 0o700
    assert (job / '.env').stat().st_mode & 0o777 == 0o600
    assert 'C0_URL=https://c0.example.org/mcp' in (job / '.env').read_text()
    assert not (job / 'oauth.json').exists()
    config = load(job / 'config/source.toml')
    assert Path(config['paths']['state']).is_relative_to(job)
    assert config['c0']['credentials_file'] == str(job / 'oauth.json')
    with pytest.raises(C0Error):
        init_job(job)


def test_jobs_must_be_ignored_and_remain_untracked(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    with pytest.raises(C0Error, match='ignored'):
        init_job(tmp_path / 'job')
    (tmp_path / '.gitignore').write_text('job/\n')
    init_job(tmp_path / 'job')
    check_job(tmp_path / 'job')
    (tmp_path / '.gitignore').write_text('')
    with pytest.raises(C0Error, match='ignored'):
        check_job(tmp_path / 'job')


def test_literal_env_never_executes_or_interpolates(tmp_path):
    path = tmp_path / '.env'
    marker = tmp_path / 'must-not-exist'
    path.write_text('VALUE=$(touch ' + str(marker) + ')\nQUOTED="${HOME}"\n')
    assert dotenv(path)['QUOTED'] == '${HOME}'
    assert not marker.exists()
    for text in ('A=one\nA=two\n', 'export A=x\n', 'A="unclosed\n'):
        path.write_text(text)
        with pytest.raises(ValueError):
            dotenv(path)


def test_private_paths_cannot_escape_or_load_codex_credentials(tmp_path):
    init_job(tmp_path / 'job')
    config = tmp_path / 'job/config/source.toml'
    config.write_text(config.read_text().replace('data/state', '../../outside'))
    with pytest.raises(ValueError, match='unsafe'):
        load(config)


def test_seed_names_are_optional_and_configurable(tmp_path):
    empty = seeds(tmp_path, {})
    assert empty['people']['rows'] == []
    (tmp_path / 'people.csv').write_text('github_handle,github_url\nalice,https://github.com/alice\n')
    assert seeds(tmp_path, {'people_seed': 'people.csv'})['people']['rows'][0]['github_handle'] == 'alice'
    with pytest.raises(ValueError):
        seeds(tmp_path, {'people_seed': '../outside.csv'})


def test_apply_and_dry_run_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        parser('fixture', 'sync').parse_args(['--config', 'unused', '--apply', '--dry-run'])


def test_sync_without_apply_fails_before_network(tmp_path, monkeypatch, capsys):
    init_job(tmp_path / 'job')
    monkeypatch.setattr('c0_ingest.cli.execute', lambda *a: pytest.fail('must not reach operations'))
    with pytest.raises(SystemExit) as exc:
        main(['--job', str(tmp_path / 'job'), 'sync'])
    assert exc.value.code == 2
    assert '--apply' in capsys.readouterr().err


@pytest.mark.parametrize('command', ['init', 'login', 'bind-account', 'inspect', 'disconnect', 'bootstrap', 'scrape', 'sync', 'run'])
def test_each_command_help_needs_no_job_auth_or_writes(command, monkeypatch, capsys):
    monkeypatch.setattr('c0_ingest.cli.check_job', lambda *a: pytest.fail('help must be offline'))
    monkeypatch.setattr('c0_ingest.cli.init_job', lambda *a: pytest.fail('help must not create a job'))
    main([command, '--help'])
    assert 'usage:' in capsys.readouterr().out
