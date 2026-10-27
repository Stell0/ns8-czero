# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only package retrieval through the existing authenticated C0 client."""
import base64
import hashlib
import json
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile
import zipfile
from c0_ingest.errors import C0Error

REFERENCE_NAMES={'project-binding','project-workflows','project-daily','project-weekly','project-recovery','project-scheduler'}
MANIFEST_FIELDS=('schema_version','project_id','space_id','name','description','language','timezone',
    'purpose','scope','exclusions','research','monitoring','schedule','state')


def save_package(client,output,*,format='skill',connection=''):
    result=client.call('project_agent_package_get',format=format,chatgpt_app_id=connection)
    if (result['schema_version']!=1 or result['space_id']!=client.space_id or result['project_id']!=client.space_id
            or result['mcp_url']!=client.config['url'] or result['format']!=format
            or not re.fullmatch(r'c0-project-[0-9a-f]{32}-[0-9a-f]{8}',result['name'])):
        raise C0Error('generated_package_binding_mismatch')
    current=client.call('project_get')['data']
    if current['version']!=result['manifest_version']:
        raise C0Error('generated_package_configuration_changed')
    try:
        archive=base64.b64decode(result['archive_base64'],validate=True)
        if len(archive)>262144 or hashlib.sha256(archive).hexdigest()!=result['archive_sha256']:
            raise ValueError()
        root='' if format=='skill' else 'skills/'+result['name']+'/'
        expected={root+'references/'+name+'.md' for name in REFERENCE_NAMES}
        expected|={'SKILL.md','agents/openai.yaml','LICENSE'} if format=='skill' else {
            'plugin.json','.app.json','LICENSE','references/instance.md',root+'SKILL.md'}
        with zipfile.ZipFile(BytesIO(archive)) as package:
            entries=package.infolist()
            if len(entries)!=result['file_count'] or len(entries)>16 or {e.filename for e in entries}!=expected or len(entries)!=len(expected):raise ValueError()
            if sum(e.file_size for e in entries)>262144:raise ValueError()
            for entry in entries:
                if (entry.orig_filename!=entry.filename or entry.compress_type!=zipfile.ZIP_STORED or entry.file_size>131072
                        or entry.external_attr>>16!=0o100644):raise ValueError()
                package.read(entry) # Check actual CRC/size, not only its metadata.
            raw=package.read(root+'references/project-binding.md').decode('utf-8')
            match=re.search(r'```json\n(.*?)\n```',raw,re.S)
            if match is None:raise ValueError()
            binding=json.loads(match[1]);manifest=current['manifest']
            if set(binding)!=set(MANIFEST_FIELDS)|{'manifest_version','mcp_url','approved_primary_topics'}:raise ValueError()
            if any(binding[field]!=manifest[field] for field in MANIFEST_FIELDS):raise ValueError()
            if (binding['mcp_url']!=result['mcp_url'] or binding['manifest_version']!=result['manifest_version']
                    or binding['approved_primary_topics']!=sorted(manifest['primary_topic_ids'])):raise ValueError()
    except (ValueError,zipfile.BadZipFile,KeyError,RecursionError):
        raise C0Error('invalid_generated_project_archive') from None
    output=Path(output).absolute()
    if not output.parent.is_dir() or any(p.is_symlink() for p in output.parents):raise C0Error('unsafe_package_output')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.c0-project-',dir=output.parent,delete=False) as stream:
            temporary=Path(stream.name);stream.write(archive);stream.flush();os.fsync(stream.fileno())
        # Hard-link creation is exclusive: existing files and symlinks survive.
        os.link(temporary,output,follow_symlinks=False)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    if hashlib.sha256(output.read_bytes()).hexdigest()!=result['archive_sha256']:
        raise C0Error('generated_project_archive_readback_failed')
    return {'status':'SAVED','project_id':client.space_id,'manifest_version':result['manifest_version'],
        'archive_sha256':result['archive_sha256'],'file_count':result['file_count'],'output':str(output),'installed':False}
