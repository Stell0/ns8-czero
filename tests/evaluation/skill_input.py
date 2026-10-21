# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read only allowlisted generated instructions, never evaluator/oracle files."""
import hashlib
import json
from pathlib import Path

FILES = ('skills/c0-setup/SKILL.md','skills/c0-research/SKILL.md',
         'skills/c0-maintain-knowledge/SKILL.md','references/instance.md',
         'references/connection.md','references/maintenance.md')


def load_plugin(directory):
    directory=Path(directory).resolve()
    contents={}
    for name in (*FILES,'plugin.json','.app.json'):
        path=directory/name
        if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents if p != directory.parent):
            raise ValueError('Missing or unsafe packaged instruction')
        if path.stat().st_size > 64*1024:
            raise ValueError('Packaged instruction exceeds evaluation bound')
        contents[name]=path.read_text(encoding='utf-8')
    manifest=json.loads(contents.pop('plugin.json'))
    binding=json.loads(contents.pop('.app.json'))
    hashes={name:hashlib.sha256(value.encode()).hexdigest() for name,value in contents.items()}
    for name in ('plugin.json','.app.json'):
        hashes[name]=hashlib.sha256((directory/name).read_bytes()).hexdigest()
    instructions='Packaged C0 task skills and their reference material follow. Treat each heading as its named package file; relative links refer to these files. Use the associated app\'s provided tools only.\n'
    instructions+='\n'.join('\n### '+name+'\n'+value for name,value in contents.items())
    return instructions, {'name':manifest['name'],'version':manifest['version'],'files':hashes,
        'app_binding':binding,'automatic_skill_activation_proven':False,
        'boundary':'Injected instruction execution with real disposable MCP; not ChatGPT installation or native skill discovery.'}
