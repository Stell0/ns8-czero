# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Offline selected Markdown for a future publisher; never deploy or fetch."""
import posixpath,re
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from uuid import UUID
from c0_ingest.errors import C0Error
from .adapters import safe_read
from .exporting import Artifacts,canonical,verify_export
from .formats import load_data
from .legacy import envelope
from .model import public_url,sha


def export_static(snapshot,selection,output):
    verify_export(snapshot);root=Path(snapshot).absolute();output=Path(output).absolute()
    if output.resolve().is_relative_to(root.resolve()):raise C0Error('static_output_must_be_separate')
    if (type(selection) is not dict or set(selection)!={'schema_version','project_id','wiki_revisions','report_references'}
            or type(selection['schema_version']) is not int or selection['schema_version']!=1 or type(selection['wiki_revisions']) is not list
            or type(selection['report_references']) is not list or not 1<=len(selection['wiki_revisions'])+len(selection['report_references'])<=1000):
        raise C0Error('explicit_static_selection_required')
    manifest=load_data(safe_read(root,'manifest.json',16*1024*1024).decode(),'json',maximum=16*1024*1024,max_nodes=2000000)
    if selection['project_id']!=manifest['project_id']:raise C0Error('static_project_binding_mismatch')
    instance=urlsplit(public_url(manifest['instance_url']));prefix=instance.path.rsplit('/',1)[0]
    pages={};revisions={};reports={};bodies={}
    for entry in manifest['files']:
        if entry['kind'] in ('wiki_pages','wiki_revisions','objects'):
            value=load_data(safe_read(root,entry['path'],4*1024*1024).decode(),'json',maximum=4*1024*1024,max_nodes=200000)
            if entry['kind']=='wiki_pages':pages[value['id']]=value
            elif entry['kind']=='wiki_revisions':revisions[value['id']]=value
            elif value['type_name']=='c0_project_report_v1' and value['data']['saved_status']=='saved':reports[value['id']]=value
        elif entry['kind']=='wiki_text':bodies[entry['resource_id']]=entry
    selected={str(UUID(value)) for value in selection['wiki_revisions']}
    report_mapping={}
    for reference in selection['report_references']:
        reference=str(UUID(reference))
        if reference not in reports:raise C0Error('selected_report_not_saved')
        revision=reports[reference]['data']['wiki_revision_id'];selected.add(revision);report_mapping[reference]=revision
    selected_pages={};paths={};slugs={}
    def public(row):return type(row.get('metadata',{}).get('static_publish')) is dict and row['metadata']['static_publish'].get('public') is True
    for reference in selected:
        row=revisions.get(reference)
        if not row or row['page_id'] not in pages:raise C0Error('selected_wiki_revision_missing')
        page=pages[row['page_id']]
        latest=next((value for value in revisions.values() if value['page_id']==page['id'] and value['number']==page['revision']),None)
        if page['deleted'] or not public(row) or not latest or not public(latest):raise C0Error('static_page_not_explicitly_public')
        if page['id'] in selected_pages:raise C0Error('static_requires_one_selected_revision_per_page')
        selected_pages[page['id']]=row;slugs[page['slug']]=page['id']
        paths[page['id']]='content/'+str(UUID(page['id']))+'.md'
    archive=Artifacts(output,100*1024*1024);mapping=[];notices=[]
    try:
        for page_id,row in sorted(selected_pages.items()):
            entry=bodies.get(row['id'])
            if not entry:raise C0Error('static_body_missing')
            body=safe_read(root,entry['path'],2*1024*1024).decode()
            if sha(body.encode())!=row['content_hash'] or envelope(body):raise C0Error('static_body_integrity_or_envelope_error')
            current_path=paths[page_id];fence='';lines=[];omitted=0
            def target(identifier,number=None):
                if identifier not in selected_pages or number is not None and selected_pages[identifier]['number']!=number:
                    raise C0Error('static_link_target_not_selected_public')
                return posixpath.relpath(paths[identifier],posixpath.dirname(current_path))
            def link(match):
                nonlocal omitted
                label,url=match[1],match[2];parsed=urlsplit(url);path=parsed.path
                if parsed.scheme:
                    public_url(url)
                    if parsed.hostname!=instance.hostname:return '['+label+']('+url+')'
                    if prefix and path.startswith(prefix+'/'):path=path[len(prefix):]
                elif parsed.netloc:raise C0Error('static_protocol_relative_link_denied')
                if not path:return '['+label+']('+url+')'
                route=path.strip('./');query=parse_qs(parsed.query)
                if query.get('space_id',[selection['project_id']])!=[selection['project_id']]:raise C0Error('static_cross_space_link_denied')
                if route=='sources':omitted+=1;return label+' (evidence retained in C0)'
                if route=='wiki':
                    identifier=query.get('page_id',[None])[0] or slugs.get(query.get('slug',[''])[0])
                    revision=int(query['revision'][0]) if query.get('revision') else None
                    return '['+label+']('+target(identifier,revision)+('#'+parsed.fragment if parsed.fragment else '')+')'
                raise C0Error('static_local_link_requires_explicit_mapping')
            for line in body.splitlines(keepends=True):
                marker=re.match(r'^ {0,3}(`{3,}|~{3,})',line)
                if marker:
                    mark=marker[1]
                    suffix=line[marker.end():].strip()
                    if not fence:
                        if mark[0]=='`' and '`' in suffix:raise C0Error('static_ambiguous_code_fence')
                        fence=mark
                    elif mark[0]==fence[0] and len(mark)>=len(fence) and not suffix:fence=''
                    lines.append(line.replace('<','&lt;').replace('>','&gt;'));continue
                if fence:lines.append(line.replace('<','&lt;').replace('>','&gt;'));continue
                if re.match(r'^ {0,3}\[[^\]]+\]:',line):raise C0Error('static_reference_links_require_review')
                line=re.sub(r'!\[\[[^\]]+\]\]','[Image omitted]',line)
                line=re.sub(r'!\[([^\]]*)\]\([^\n)]*\)',lambda match:'[Image omitted: '+match[1]+']',line)
                if re.search(r'!\[[^\]\n]*\]\(',line):raise C0Error('static_ambiguous_image_requires_review')
                openings=len(re.findall(r'\[[^\]\n]+\]\(',line))
                if openings!=len(re.findall(r'\[([^\]\n]+)\]\(([^\s)]+)\)',line)):
                    raise C0Error('static_ambiguous_link_requires_review')
                line=re.sub(r'\[([^\]\n]+)\]\(([^\s)]+)\)',link,line)
                line=re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]',lambda match:'['+(match[2] or match[1])+']('+target(slugs.get(match[1],match[1]))+')',line)
                lines.append(line.replace('<','&lt;').replace('>','&gt;'))
            rendered=''.join(lines)
            rendered=rendered.lstrip('\ufeff')
            rendered=re.sub(r'^---[ \t]*\r?\n',lambda _:'\\-\\-\\-\n',rendered,count=1)
            artifact=archive.add(current_path,rendered.encode(),kind='public_markdown',resource_id=row['id'])
            metadata={'page_id':page_id,'wiki_revision_id':row['id'],'revision':row['number'],'title':row['title'],
                'slug':pages[page_id]['slug'],'source_content_hash':row['content_hash'],'exported_content_hash':artifact['sha256']}
            archive.add('metadata/'+str(UUID(page_id))+'.json',canonical(metadata),kind='public_metadata',resource_id=row['id'])
            mapping.append(metadata)
            if omitted:notices.append({'wiki_revision_id':row['id'],'protected_evidence_links_omitted':omitted})
        archive.readback()
        result={'kind':'c0-static-selection','schema_version':1,'project_id':selection['project_id'],'pages':mapping,
            'reports':report_mapping,'files':sorted(archive.files,key=lambda value:value['path']),'notices':notices,
            'transformations':['Raw angle brackets, including examples, are escaped; images are inactive. Reference-link definitions require review.',
                'Internal links resolve only to explicitly selected public pages; protected source links lose their destination.',
                'Leading YAML frontmatter is disarmed. Original hashes are retained separately.'],
            'publication_performed':False,'writes_c0':0}
        saved=archive.add('static-manifest.json',canonical(result),kind='static_manifest',resource_id=selection['project_id'])
        return {'status':'VALIDATED','directory':str(archive.root),'manifest_hash':saved['sha256'],'pages':len(mapping),'writes_c0':0,'publication_performed':False}
    except (C0Error,ValueError,KeyError,TypeError,OSError):
        archive.add('partial.json',canonical({'status':'PARTIAL','error':'static_selection_or_content_requires_review','writes_c0':0}),kind='partial',resource_id=selection['project_id'])
        raise C0Error('static_selection_or_content_requires_review') from None
