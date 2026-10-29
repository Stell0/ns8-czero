# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Own only crawler-created scans; never sweep a pre-existing private job."""
from pathlib import Path
import re
import shutil
from c0_ingest.errors import C0Error
from c0_ingest.state import atomic,read
from .model import now,sha


def remember_scan(state,directory,manifest):
    owned=read(state/'website-owned-scans.json',[])
    relative=directory.relative_to(state).as_posix()
    if relative not in owned and len(owned)>=2:raise C0Error('website_pending_scans_require_reconciliation')
    if relative not in owned:owned.append(relative)
    atomic(state/'website-owned-scans.json',owned)


def verified_scan(state,directory,manifest):
    owned=read(state/'website-owned-scans.json',[])
    current=directory.relative_to(state).as_posix()
    if current not in owned:return
    for relative in owned:
        if relative==current:continue
        old=state/relative
        if old.is_symlink() or old.parent!=state/'scans' or not old.name.isalnum():raise C0Error('unsafe_website_scan_cleanup')
        if not old.exists():continue
        previous=read(old/'manifest.json',{})
        if not previous or any(source.get('adapter')!='website' for source in previous['sources']):
            raise C0Error('website_scan_ownership_mismatch')
        atomic(state/'summaries'/(old.name+'.json'),{'verified_at':now(),'manifest_hash':sha(previous),
            'connectors':len(previous['sources']),'items':sum(len(source['items']) for source in previous['sources']),
            'status':'retired_payload'})
        shutil.rmtree(old)
    atomic(state/'website-owned-scans.json',[current])
    atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest),'verified':True})


def commit_frontier(root,connector,cursor):
    if type(connector) is not str or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',connector):raise C0Error('invalid_website_connector')
    cache=Path(root)/'data/c0-projects/website'/connector
    if any(path.is_symlink() for path in (cache,*cache.absolute().parents)):raise C0Error('unsafe_website_cache')
    before=cache/'frontier-before-batch.json'
    if before.is_symlink() or (cache/'frontier.json').is_symlink():raise C0Error('unsafe_website_cache')
    if before.exists() and sha(read(cache/'frontier.json',{}))==cursor.get('frontier_hash'):
        before.unlink()


def commit_scan_frontiers(root,manifest):
    for source in manifest['sources']:
        if source.get('adapter')=='website':commit_frontier(root,source['connector_id'],source['cursor'])


def scan_path(state,relative):
    path=state/relative
    if path.is_symlink() or path.parent!=state/'scans' or not path.name.isalnum():raise C0Error('unsafe_website_scan_binding')
    return path


def prepare_scan(state):
    from uuid import uuid4
    directory=state/'scans'/uuid4().hex
    directory.mkdir(parents=True,mode=0o700)
    atomic(directory/'website-owner.json',{'kind':'c0-website-scan','id':directory.name})
    try:remember_scan(state,directory,{})
    except BaseException:
        shutil.rmtree(directory);raise
    return directory


def prepared_scan(directory):
    if directory.is_symlink() or read(directory/'website-owner.json',{})!={'kind':'c0-website-scan','id':directory.name}:
        raise C0Error('website_scan_ownership_mismatch')


def recover_scan(state):
    # The ledger precedes payload writes. A completed scan can recover its lost
    # latest-pointer write; only a proven owned incomplete directory is removed.
    owned=read(state/'website-owned-scans.json',[]);latest=read(state/'latest.json',{})
    if not owned:return
    candidate=scan_path(state,owned[-1])
    if latest.get('directory')==str(candidate):return
    if not candidate.exists():
        atomic(state/'website-owned-scans.json',owned[:-1]);return
    if (candidate/'manifest.json').is_file():
        from .cli import load_scan
        manifest=load_scan(candidate)
        if not manifest['sources'] or any(source.get('adapter')!='website' for source in manifest['sources']):
            raise C0Error('website_scan_ownership_mismatch')
        atomic(state/'latest.json',{'directory':str(candidate),'manifest_hash':sha(manifest)})
    else:
        prepared_scan(candidate)
        shutil.rmtree(candidate)
        atomic(state/'website-owned-scans.json',owned[:-1])
