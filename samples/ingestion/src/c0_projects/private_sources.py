# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit local publication consent; credentials stay in existing GitHub auth."""
from pathlib import Path
from c0_ingest.errors import C0Error
from .adapters import safe_read
from .formats import load_data


def load_authorization(path,config):
    if path is None:return {}
    path=Path(path)
    if path.is_symlink() or path.stat().st_mode&0o077:raise C0Error('private_source_authorization_requires_private_file')
    value=load_data(safe_read(path.parent,path.name,16384).decode(),path.suffix.lstrip('.'))
    allowed={source['repository'].casefold() for source in config['sources'] if source['adapter']=='github'}
    if (type(value) is not dict or set(value)!={'schema_version','project_space_id','repositories','authorization_ref'}
            or type(value['schema_version']) is not int or value['schema_version']!=1 or value['project_space_id']!=config['project_space_id']
            or type(value['authorization_ref']) is not str or not 1<=len(value['authorization_ref'].strip())<=512
            or type(value['repositories']) is not list or not 1<=len(value['repositories'])<=100
            or any(type(repo) is not str or repo.casefold() not in allowed for repo in value['repositories'])
            or len({repo.casefold() for repo in value['repositories']})!=len(value['repositories'])):
        raise C0Error('private_source_authorization_binding_mismatch')
    return {repo.casefold():value['authorization_ref'] for repo in value['repositories']}


def require_snapshot_permission(definition,items,authorizations,*,preflight=None):
    private=[item for item in items if item.get('provenance',{}).get('source_visibility')=='private']
    if not private:return
    repo=definition.get('repository','')
    if definition['adapter']!='github' or repo.casefold() not in authorizations or any(
            item['provenance'].get('repository','').casefold()!=repo.casefold() for item in private):
        raise C0Error('private_snapshot_publication_requires_current_explicit_consent')
    if preflight:
        metadata=preflight()
        if (metadata.get('full_name','').casefold()!=repo.casefold() or any(
                str(metadata.get('id'))!=str(item['provenance'].get('repository_id')) for item in private)):
            raise C0Error('private_snapshot_repository_identity_changed')
