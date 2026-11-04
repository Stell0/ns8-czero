# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Execute the publisher's source selection with real Git and a remote stub."""
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[2]
WORKFLOW=yaml.safe_load((ROOT/'.github/workflows/publish-core.yml').read_text())


@pytest.mark.parametrize('tag,remote,accepted',[
    ('core-v0.37.0','checkout',True),
    ('core-v0.37.0','other',False),
    ('main','checkout',False),
    ('core-v0.37.0-testing.1','checkout',False),
    ('core-v0.37.0;exit 0','checkout',False),
])
def test_selected_tag_must_resolve_to_actual_checkout(tmp_path,tag,remote,accepted):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.test',
        '-c','commit.gpgsign=false','commit','--allow-empty','-qm','Fixture'],cwd=tmp_path,check=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=tmp_path,text=True).strip()
    executable=tmp_path/'bin';executable.mkdir()
    stub=executable/'gh';stub.write_text('#!/bin/sh\nprintf "%s\\n" "$MOCK_REMOTE_SOURCE"\n');stub.chmod(0o700)
    output=tmp_path/'output'
    step=next(s for s in WORKFLOW['jobs']['verify']['steps'] if s.get('id')=='source')
    environment={**os.environ,'PATH':str(executable)+os.pathsep+os.environ['PATH'],
        'CORE_TAG':tag,'GITHUB_REPOSITORY':'example/czero','GITHUB_OUTPUT':str(output),
        # Dispatch's workflow commit is deliberately different from Core source.
        'GITHUB_SHA':'b'*40,'MOCK_REMOTE_SOURCE':source if remote=='checkout' else 'c'*40}
    result=subprocess.run(['bash','-c',step['run']],cwd=tmp_path,env=environment,capture_output=True,text=True)
    assert (result.returncode==0) is accepted
    assert (output.read_text() if output.exists() else '')==(
        f'source={source}\ntag={tag}\n' if accepted else '')


def test_dispatch_preserves_native_checks_and_frozen_source_binding():
    verify=WORKFLOW['jobs']['verify'];steps=verify['steps']
    check=next(s for s in steps if s.get('name')=='Require verified source and matching version')
    assert '--source "$CORE_SOURCE" --full' in check['run']
    assert 'GITHUB_SHA="$CORE_SOURCE" GITHUB_REF_NAME="$CORE_TAG"' in check['run']
    runtime=next(i for i,s in enumerate(steps) if s.get('name')=='Install acceptance parser runtime')
    packaging=next(i for i,s in enumerate(steps) if s.get('name')=='Verify exact artifacts and packaged migrations')
    assert runtime<packaging
    assert all(package in steps[runtime]['run'] for package in (
        'poppler-utils','tesseract-ocr-eng','tesseract-ocr-ita','fonts-dejavu-core'))
    publish=next(s for s in WORKFLOW['jobs']['publish']['steps'] if s.get('name')=='Publish immutable Core artifacts')
    assert publish['env']['CORE_SOURCE']=='${{ needs.verify.outputs.source }}'
    assert publish['env']['CORE_TAG']=='${{ needs.verify.outputs.tag }}'
    assert 'test "$tag_commit" = "$CORE_SOURCE"' in publish['run']
    assert '--clobber' not in publish['run']
    assert 'cmp SHA256SUMS ../published/SHA256SUMS' in publish['run']
