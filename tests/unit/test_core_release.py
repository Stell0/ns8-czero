# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from pathlib import Path
import runpy

import pytest

verify=runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/check-core-release.py'))['verify']
SHA='a'*40


def evidence():
    return {'sha':SHA,'statuses':[
        {'context':'continuous-integration/qemu/debian13','state':'success'},
        {'context':'continuous-integration/qemu/rocky9','state':'success'}]},[
        {'headSha':SHA,'status':'completed','conclusion':'success'}]


def test_publication_accepts_only_matching_verified_source():
    native,runs=evidence()
    verify('0.24.1','core-v0.24.1',SHA,native,runs,SHA)


@pytest.mark.parametrize('state',['pending','failure','error'])
def test_pending_or_failed_native_job_blocks_publication(state):
    native,runs=evidence();native['statuses'][1]['state']=state
    with pytest.raises(ValueError,match='native_acceptance_not_verified'):
        verify('0.24.1','core-v0.24.1',SHA,native,runs,SHA)


@pytest.mark.parametrize('duplicate',[False,True])
def test_missing_distribution_or_duplicate_context_cannot_look_complete(duplicate):
    native,runs=evidence();native['statuses'].pop()
    if duplicate:native['statuses'].append(deepcopy(native['statuses'][0]))
    with pytest.raises(ValueError,match='native_acceptance_not_verified'):
        verify('0.24.1','core-v0.24.1',SHA,native,runs,SHA)


@pytest.mark.parametrize('source',['native','local'])
def test_success_from_another_commit_is_not_acceptance(source):
    native,runs=evidence()
    if source=='native':native['sha']='b'*40
    else:runs[0]['headSha']='b'*40
    with pytest.raises(ValueError,match='source_mismatch' if source=='native' else 'local_acceptance_not_verified'):
        verify('0.24.1','core-v0.24.1',SHA,native,runs,SHA)


@pytest.mark.parametrize('tag',['core-v0.24.2','0.24.1','core-v0.24.1-testing.1'])
def test_tag_must_match_the_python_package_version(tag):
    native,runs=evidence()
    with pytest.raises(ValueError,match='core_version_tag_mismatch'):
        verify('0.24.1',tag,SHA,native,runs,SHA)


def test_running_local_checks_cannot_authorize_publication():
    native,runs=evidence();runs[0]['status']='in_progress'
    with pytest.raises(ValueError,match='local_acceptance_not_verified'):
        verify('0.24.1','core-v0.24.1',SHA,native,runs,SHA)


def test_verified_commit_cannot_authorize_a_different_checkout():
    native,runs=evidence()
    with pytest.raises(ValueError,match='release_source_mismatch'):
        verify('0.24.1','core-v0.24.1',SHA,native,runs,'b'*40)
