# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Exact bounded source context; planning and synthesis stay with the caller."""
from contextlib import contextmanager
import hashlib
import json
import re
from uuid import UUID
from sqlalchemy import text

from .current_content import ContentSuperseded
from .extraction import Extracted,ExtractionError
from .structure import derive
from .sources import SourceConflict,SourceNotFound
from .local_ocr import validate_profile,validate_provenance

MAX_REPLY=65536


def _encoded(value):
    return json.dumps(value,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()


def _hash(body):
    return hashlib.sha256(body.encode()).hexdigest()


def _limits(max_bytes,max_tokens):
    if type(max_bytes) is not int or not 4096<=max_bytes<=MAX_REPLY or type(max_tokens) is not int or not 256<=max_tokens<=16384:
        raise ValueError('invalid_context_limits')


def _finish(value,max_bytes,max_tokens):
    value.update(response_bytes=0,estimated_tokens=0)
    for _ in range(5):
        size=len(_encoded(value)); estimate=(size+2)//3
        if (size,estimate)==(value['response_bytes'],value['estimated_tokens']): break
        value.update(response_bytes=size,estimated_tokens=estimate)
    if len(_encoded(value))>max_bytes or value['estimated_tokens']>max_tokens:
        raise ExtractionError('too_large')
    return value


def _ids(values,prefix,*,empty=False):
    if type(values) is not list or not (0 if empty else 1)<=len(values)<=20 or len(set(map(str,values)))!=len(values):
        raise ValueError('invalid_context_selection')
    if any(type(value) is not str or re.fullmatch(prefix+r'[0-9]{1,4}',value) is None for value in values):
        raise ValueError('invalid_context_selection')
    return values


@contextmanager
def _reader(service,actor):
    with service.database.engine.begin() as connection:
        connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        service._authorize(connection,actor)
        yield connection


def _structure(value,body):
    try:
        if (type(value) is not dict or type(value['revision']) is not int or value['revision']!=1 or value['text_sha256']!=_hash(body)
            or set(value)-{'revision','text_sha256','sections','blocks','references','pages','ocr'}
            or any(type(value[key]) is not list or len(value[key])>(4001 if key=='sections' else 4000) for key in ('sections','blocks','references','pages'))
            or not value['sections']): raise ValueError()
        sections={}
        for index,section in enumerate(value['sections']):
            if (set(section)!={'id','parent','level','start','end','heading','anchor'}
                or (section['anchor'] is not None and (type(section['anchor']) is not str or len(section['anchor'])>256))
                or section['id']!='s'+str(index) or type(section['level']) is not int or not 0<=section['level']<=6
                or any(type(section[key]) is not int for key in ('start','end'))
                or not 0<=section['start']<=section['end']<=len(body)): raise ValueError()
            if index==0:
                if (section['parent'],section['level'],section['start'],section['end'],section['heading'])!=(None,0,0,len(body),None): raise ValueError()
            else:
                parent=sections[section['parent']]
                if not parent['level']<section['level'] or not parent['start']<=section['start']<section['end']<=parent['end']: raise ValueError()
                heading=section['heading']
                if (set(heading)!={'kind','start','end'} or heading['kind']!='heading'
                    or not section['start']<=heading['start']<heading['end']<=section['end']): raise ValueError()
            sections[section['id']]=section
        for key,prefix in (('blocks','b'),('references','r')):
            for index,item in enumerate(value[key]):
                fields={'kind','start','end','id','section'} | ({'target'} if key=='references' else set())
                if (set(item)!=fields or item['id']!=prefix+str(index) or any(type(item[k]) is not int for k in ('start','end'))
                    or not 0<=item['start']<item['end']<=len(body)): raise ValueError()
                if item.get('section') is not None and item['section'] not in sections: raise ValueError()
                if key=='blocks' and item['kind'] not in ('paragraph','heading','table','list','code','warning','page'): raise ValueError()
                if key=='references' and (item['kind']!='link' or type(item['target']) is not str or re.fullmatch('[A-Za-z0-9_.:%-]{1,256}',item['target']) is None): raise ValueError()
        pages=set()
        for page in value['pages']:
            if (set(page)!={'kind','index','start','end'} or page['kind']!='page'
                or any(type(page[key]) is not int for key in ('index','start','end'))
                or not 1<=page['index']<=200 or page['index'] in pages
                or not 0<=page['start']<page['end']<=len(body)): raise ValueError()
            pages.add(page['index'])
        if 'ocr' in value:
            ocr=value['ocr']
            if set(ocr)!={'profile','pages'} or type(ocr['pages']) is not list or not 1<=len(ocr['pages'])<=200: raise ValueError()
            validate_profile(ocr['profile']); seen=set()
            for page in ocr['pages']:
                if page['page'] not in pages or page['page'] in seen: raise ValueError()
                validate_provenance(page,ocr['profile'],page['page']); seen.add(page['page'])
        return value
    except (ValueError,KeyError,TypeError,IndexError): raise SourceConflict() from None


def _load(service,connection,identifier,revision=None):
    full=service._read(connection,identifier,revision_id=revision)
    if full['state']!='ready' or full['body'] is None: raise SourceConflict()
    if revision is not None and UUID(str(revision))!=full['revision_id']: raise ContentSuperseded()
    if len(full['body'])>1000000 or len(full['body'].encode())>2097152: raise ExtractionError('too_large')
    saved=None; locations=[]
    # Markdown structure follows the verified logical body, not each receipt's
    # independent heading numbering or possibly large derivative JSON.
    parts=[] if full['multipart'] and full['media_type']=='text/markdown' else full['parts']
    for part in parts:
        row=connection.execute(text('SELECT locations,structure FROM c0_documents WHERE space_id=:space AND id=:id'),
            {'space':service._space(connection),'id':part['document_id']}).mappings().one_or_none()
        if row is None: raise SourceConflict()
        locations.extend({**loc,'start':loc['start']+part['start_offset'],'end':loc['end']+part['start_offset']} for loc in row['locations'])
        if not full['multipart']: saved=row['structure']
    origin='persisted' if saved is not None else 'derived_current_body'
    if saved is None:
        # Bound a legacy/multipart derivation before allocating line metadata.
        saved=derive(Extracted(full['body'],locations),full['media_type'],bounded=True)
    structure=_structure(saved,full['body'])
    identity={'logical_document_id':str(full['id']),'revision_id':str(full['revision_id']),
        'text_sha256':full['text_hash'],'structure_revision':1,'structure_origin':origin}
    return full,structure,identity


def _section_summary(section,body):
    heading=section['heading']; label=body[heading['start']:heading['end']] if heading else None
    return {key:section[key] for key in ('id','parent','level','start','end','anchor')} | {
        'heading':label[:256] if label is not None else None,'heading_complete':label is None or len(label)<=256}


def outline(service,actor,identifier,*,revision_id=None,limit=50,offset=0,view='sections',max_bytes=32768,max_tokens=8192):
    _limits(max_bytes,max_tokens)
    if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=4000:
        raise ValueError('invalid_context_page')
    if view not in ('sections','blocks'): raise ValueError('invalid_outline_view')
    with _reader(service,actor) as c:
        full,structure,identity=_load(service,c,identifier,revision_id)
        result={'space_id':str(service._space(c)),**identity,'sections':[],'blocks':[],'view':view,'has_ocr':'ocr' in structure,
            'total_sections':len(structure['sections']),'total_blocks':len(structure['blocks']),
            'total_references':len(structure['references']),'next_offset':None,'complete_document':False}
        for node in structure[view][offset:offset+limit]:
            result[view].append(_section_summary(node,full['body']) if view=='sections' else dict(node))
            try: _finish(result,max_bytes-32,max_tokens-16)
            except ExtractionError:
                result[view].pop(); break
        if not result[view] and offset<len(structure[view]): raise ExtractionError('too_large')
        following=offset+len(result[view])
        if following<len(structure[view]): result['next_offset']=following
        return _finish(result,max_bytes,max_tokens)


def _citations(service,c,full,start,end):
    result=[]
    for part in full['parts']:
        if part['start_offset']>=end or part['end_offset']<=start: continue
        rows=c.execute(text('''SELECT id,document_id,start_offset,end_offset,content_hash FROM c0_chunks
            WHERE space_id=:space AND document_id=:id AND start_offset<:last AND end_offset>:first
            ORDER BY ordinal LIMIT 129'''),{'space':service._space(c),'id':part['document_id'],
            'first':max(0,start-part['start_offset']),'last':end-part['start_offset']}).mappings()
        for row in rows:
            first=row['start_offset']+part['start_offset']; last=row['end_offset']+part['start_offset']
            result.append({'source_id':str(part['source_id']),'version_id':str(part['version_id']),
                'document_id':str(row['document_id']),'chunk_id':str(row['id']),'content_hash':row['content_hash'],
                'start_offset':row['start_offset'],'end_offset':row['end_offset'],
                'document_start_offset':first,'document_end_offset':last,'selected_start':max(start,first),'selected_end':min(end,last)})
            if len(result)>128: raise ExtractionError('too_large')
    covered=start
    for row in sorted(result,key=lambda item:item['document_start_offset']):
        if row['document_start_offset']>covered: raise SourceConflict()
        covered=max(covered,row['document_end_offset'])
    if covered<end: raise SourceConflict()
    return result


def _selection(service,c,full,structure,identity,section_id):
    nodes=structure['sections'] if section_id.startswith('s') else structure['blocks']
    selected=next((row for row in nodes if row['id']==section_id),None)
    if selected is None: raise SourceNotFound()
    first,last=selected['start'],selected['end']; body=full['body'][first:last]
    if len(body.encode())>MAX_REPLY: raise ExtractionError('too_large')
    extraction={}
    if 'ocr' in structure:
        pages={row['index'] for row in structure['pages'] if row['start']<last and row['end']>first}
        observed=[row for row in structure['ocr']['pages'] if row['page'] in pages]
        if observed: extraction={'ocr_profile':structure['ocr']['profile'],'ocr_pages':observed}
    return {**identity,'selection_id':section_id,'section_id':selected['id'] if section_id.startswith('s') else selected['section'],
        'kind':'section' if section_id.startswith('s') else selected['kind'],'start_offset':first,'end_offset':last,
        'body':body,'content_hash':_hash(body),'citations':_citations(service,c,full,first,last),'extraction':extraction,
        'blocks':[row for row in structure['blocks'] if first<=row['start'] and row['end']<=last],
        'references':[row for row in structure['references'] if first<=row['start'] and row['end']<=last]}


def _plan(value):
    if type(value) is not list or not 1<=len(value)<=5: raise ValueError('invalid_context_plan')
    total=0; seen=set()
    for item in value:
        if type(item) is not dict or set(item)!={'logical_document_id','revision_id','selection_ids','reference_ids'}: raise ValueError('invalid_context_plan')
        identifier=UUID(str(item['logical_document_id'])); revision=UUID(str(item['revision_id']))
        if identifier in seen: raise ValueError('invalid_context_plan')
        seen.add(identifier)
        _ids(item['selection_ids'],'[sb]',empty=True); _ids(item['reference_ids'],'r',empty=True)
        total+=len(item['selection_ids'])+len(item['reference_ids'])
        if total>20: raise ValueError('invalid_context_plan')
    if total==0: raise ValueError('invalid_context_plan')
    return value


def bundle(service,actor,plan,*,max_bytes=32768,max_tokens=8192):
    _limits(max_bytes,max_tokens); _plan(plan)
    with _reader(service,actor) as c:
        result={'space_id':str(service._space(c)),'documents':[],'sections':[],'references':[],
            'omitted':[],'complete_document':False,'no_fallback':True}
        for item in plan:
            full,structure,identity=_load(service,c,item['logical_document_id'],item['revision_id'])
            result['documents'].append(identity); ids=list(item['selection_ids'])
            for key in item['reference_ids']:
                reference=next((row for row in structure['references'] if row['id']==key),None)
                if reference is None: raise SourceNotFound()
                result['references'].append({**identity,**reference,'resolved':reference['section'] is not None,
                    'citations':_citations(service,c,full,reference['start'],reference['end'])})
                if reference['section'] is not None and reference['section'] not in ids: ids.append(reference['section'])
            for key in ids:
                try:
                    selected=_selection(service,c,full,structure,identity,key)
                    result['sections'].append(selected)
                    try: _finish(result,max_bytes,max_tokens)
                    except ExtractionError:
                        result['sections'].pop(); raise
                except ExtractionError:
                    result['omitted'].append({**identity,'selection_id':key,'reason':'too_large'})
        return _finish(result,max_bytes,max_tokens)


def sections(service,actor,identifier,*,revision_id,selection_ids,max_bytes=32768,max_tokens=8192):
    _ids(selection_ids,'[sb]')
    return bundle(service,actor,[{'logical_document_id':str(identifier),'revision_id':str(revision_id),
        'selection_ids':selection_ids,'reference_ids':[]}],max_bytes=max_bytes,max_tokens=max_tokens)


def references(service,actor,identifier,*,revision_id,reference_ids,max_bytes=32768,max_tokens=8192):
    _ids(reference_ids,'r'); _limits(max_bytes,max_tokens)
    with _reader(service,actor) as c:
        full,structure,identity=_load(service,c,identifier,revision_id)
        result={'space_id':str(service._space(c)),**identity,'references':[],'complete_document':False}
        for key in reference_ids:
            row=next((item for item in structure['references'] if item['id']==key),None)
            if row is None: raise SourceNotFound()
            result['references'].append({**identity,**row,'resolved':row['section'] is not None,
                'citations':_citations(service,c,full,row['start'],row['end'])})
        return _finish(result,max_bytes,max_tokens)
