# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Navigation must survive the split; examples and skills stay instance-neutral."""
from pathlib import Path
import json
import runpy
import subprocess

import pytest

ROOT=Path(__file__).parents[2]
DOCS=runpy.run_path(str(ROOT/'scripts/documentation.py'))


def test_all_maintained_navigation_and_skill_references():
    paths=list(DOCS['MAINTAINED'])+['.agents/references/development.md']
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/'plugins/c0-knowledge').rglob('*.md')]
    assert DOCS['check'](paths) > 200
    for path in paths:
        text=(ROOT/path).read_text()
        assert 'makako.sf.nethserver.net' not in text and '/home/tux/' not in text
    # Developer and end-user skill discovery names do not collide.
    names=[]
    for p in [*ROOT.glob('.agents/skills/*/SKILL.md'),*ROOT.glob('plugins/c0-knowledge/skills/*/SKILL.md')]:
        metadata=dict(line.split(': ',1) for line in p.read_text().split('---',2)[1].strip().splitlines())
        assert metadata['name']==p.parent.name
        assert metadata['description'] and len(metadata['description']) <= 1024
        names.append(metadata['name'])
    assert len(names)==len(set(names))==11


def test_fences_and_duplicate_heading_anchors_match_navigation(tmp_path):
    doc=tmp_path/'read.md'
    doc.write_text('# Read `this`\n# Read this\n~~~md\n[ignored](missing.md)\n# Hidden\n~~~\n[ok](#read-this-1)\n')
    assert DOCS['anchors'](doc.read_text())==['read-this','read-this-1']
    assert DOCS['check'](['read.md'],root=tmp_path)==1


@pytest.mark.parametrize('target',['gone.md','other.md#missing','../outside.md','/private/path','javascript:alert'])
def test_missing_or_unsafe_navigation_fails(tmp_path,target):
    (tmp_path/'read.md').write_text('[broken]('+target+')\n')
    (tmp_path/'other.md').write_text('# Existing\n')
    with pytest.raises(ValueError):DOCS['check'](['read.md'],root=tmp_path)


def test_archived_anchors_remain_reachable_from_legacy_root_links():
    for name in ('README.md','AGENTS.md','PLAN.md'):
        archived=DOCS['headings']((ROOT/'docs/history'/name).read_text())
        current=set(DOCS['anchors']((ROOT/name).read_text()))
        assert all(slug in current for slug,_ in archived)


def test_standalone_fork_includes_all_developer_reference_dependencies(tmp_path):
    # This is an independent consumer tree, not merely a check of manifest text.
    destination=tmp_path/'fork'
    subprocess.run(['python3',str(ROOT/'examples/fork/create.py'),str(destination)],check=True,capture_output=True)
    paths=[str(p.relative_to(destination)) for p in (destination/'.agents').rglob('*.md')]
    assert DOCS['check'](paths,root=destination)>0
    assert not (destination/'plugins').exists()
    assert (destination/'.agents/skills/c0-project-workflows/SKILL.md').is_file()
    manifest=json.loads((destination/'c0-upstream.json').read_text())
    assert all('private' not in f['path'] for f in manifest['files'])
