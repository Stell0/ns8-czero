# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Private explicit bindings; secrets are files, never arguments or prompt fields."""
import json
import os
from pathlib import Path
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from c0_ingest.auth import destination
from c0_ingest.errors import C0Error
from c0_ingest.state import digest


def private_file(path, *, maximum=131072):
    path = Path(path)
    if (not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file()
            or path.stat().st_mode & 0o077 or path.stat().st_size > maximum
            or path.parent.stat().st_mode & 0o077):
        raise C0Error('private_file_required')
    return path.read_text()


def load(path):
    data = json.loads(private_file(path, maximum=16384))
    fields = {'adapter','schema_version','url','account_id','identity','space_id','space_name',
        'c0_key_file','model_key_file','model','protocol_file','state_dir','timezone',
        'daily_local_time','weekly_local_time','weekly_day','max_model_calls',
        'max_output_tokens','max_input_bytes','timeout_seconds'}
    if type(data) is not dict or set(data) != fields or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise C0Error('invalid_compiler_configuration')
    stable_data=dict(data)
    destination(data)
    for key in ('account_id','space_id'):
        if str(UUID(data[key])) != data[key]: raise C0Error('invalid_compiler_binding')
    for key in ('identity','space_name'):
        if type(data[key]) is not str or not 1 <= len(data[key]) <= 160:
            raise C0Error('invalid_compiler_binding')
    ZoneInfo(data['timezone'])
    for key in ('daily_local_time','weekly_local_time'):
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', data[key]):
            raise C0Error('invalid_schedule')
    if data['weekly_day'] not in ('monday','tuesday','wednesday','thursday','friday','saturday','sunday'):
        raise C0Error('invalid_schedule')
    # Explicit operator-selected snapshot; aliases may change between runs.
    if data['adapter'] not in ('responses','codex'): raise C0Error('unsupported_model_adapter')
    if data['adapter']=='codex' and data['model']!='gpt-6.1-sol': raise C0Error('unsupported_codex_model')
    if data['adapter']=='responses' and not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,90}-\d{4}-\d{2}-\d{2}', data['model']):
        raise C0Error('explicit_model_snapshot_required')
    for key, low, high in [('max_model_calls',1,4),('max_output_tokens',128,8192),
                          ('max_input_bytes',1024,262144),('timeout_seconds',1,60)]:
        if type(data[key]) is not int or not low <= data[key] <= high:
            raise C0Error('invalid_runner_limit')
    root = Path(data['state_dir'])
    if not root.is_absolute() or any(p.is_symlink() for p in (root,*root.parents)):
        raise C0Error('private_state_directory_required')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077: raise C0Error('private_state_directory_required')
    for key in ('c0_key_file','model_key_file'):
        if data[key].startswith('credential:'):
            name=data[key].removeprefix('credential:')
            if name not in ('c0-key','model-key') or not os.environ.get('CREDENTIALS_DIRECTORY'):
                raise C0Error('systemd_credential_unavailable')
            data[key]=str(Path(os.environ['CREDENTIALS_DIRECTORY'])/name)
    data['auth_mode'] = 'api_key'
    # Protocol is an installed trusted skill, not a source document or model output.
    data['protocol'] = private_file(data['protocol_file'])
    data['binding_hash'] = digest({**stable_data,'protocol_hash':digest(data['protocol'])})
    return data


def install_key(config):
    key = private_file(config['c0_key_file'], maximum=256).strip()
    if not re.fullmatch(r'c0k_[A-Za-z0-9_-]{43}', key): raise C0Error('invalid_c0_key_file')
    os.environ['C0_API_KEY'] = key  # Reuse the existing authenticated SDK transport.
