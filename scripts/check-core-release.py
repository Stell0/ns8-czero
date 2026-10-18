#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject package publication without exact-source local and native acceptance."""
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import tomllib


def verify(version, tag, sha, native, local_runs, checkout_sha):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version) or tag != 'core-v'+version:
        raise ValueError('core_version_tag_mismatch')
    if not re.fullmatch(r'[0-9a-f]{40}',sha) or native.get('sha') != sha or checkout_sha != sha:
        raise ValueError('release_source_mismatch')
    contexts={'continuous-integration/qemu/debian13','continuous-integration/qemu/rocky9'}
    selected=[entry for entry in native.get('statuses',[]) if entry.get('context') in contexts]
    if (len(selected)!=2 or {entry['context'] for entry in selected}!=contexts
            or any(entry.get('state')!='success' for entry in selected)):
        raise ValueError('native_acceptance_not_verified')
    if not any(run.get('headSha')==sha and run.get('status')=='completed'
               and run.get('conclusion')=='success' and run.get('full_validation') is True for run in local_runs):
        raise ValueError('local_acceptance_not_verified')


def main():
    try:
        version=tomllib.loads(Path('packages/czero-core/pyproject.toml').read_text())['project']['version']
        verify(version,os.environ['GITHUB_REF_NAME'],os.environ['GITHUB_SHA'],
               json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text()),
               subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OSError,subprocess.CalledProcessError) as error:
        reason=str(error) if isinstance(error,ValueError) and str(error) in {
            'core_version_tag_mismatch','release_source_mismatch',
            'native_acceptance_not_verified','local_acceptance_not_verified'} else 'invalid_release_input'
        raise SystemExit('Core publication blocked: '+reason) from None
    print('Core package version and exact-source local/native acceptance verified')


if __name__=='__main__':main()
