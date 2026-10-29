# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Own only crawler-created scans; never sweep a pre-existing private job."""
from pathlib import Path
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
        previous=read(old/'manifest.json',{})
        if not previous or any(source.get('adapter')!='website' for source in previous['sources']):
            raise C0Error('website_scan_ownership_mismatch')
        atomic(state/'summaries'/(old.name+'.json'),{'verified_at':now(),'manifest_hash':sha(previous),
            'connectors':len(previous['sources']),'items':sum(len(source['items']) for source in previous['sources']),
            'status':'retired_payload'})
        shutil.rmtree(old)
    atomic(state/'website-owned-scans.json',[current])
    atomic(state/'latest.json',{'directory':str(directory),'manifest_hash':sha(manifest),'verified':True})
