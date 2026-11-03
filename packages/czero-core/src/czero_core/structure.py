# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded source spans; metadata never supplies replacement citation text."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from .document_units import DOCX,text_blocks,_path
from .extraction import Extracted,ExtractionError,MAX_LOCATIONS,MAX_CHUNKS,_docx,chunks,valid_text

PROFILES=('fixed-v1','sections-v1')
MAX_STRUCTURE_BYTES=2097152


def _span(kind,start,end,**extra):
    return {'kind':kind,'start':start,'end':end,**extra}


def derive(evidence,media,*,heading_levels=None):
    body=valid_text(evidence.text); headings=[]; blocks=[]; references=[]
    if media=='text/markdown':
        boundaries,raw_headings=text_blocks(body,True)
        headings=[(start,level,body.find('\n',start) if '\n' in body[start:] else len(body)) for start,level in raw_headings]
        # Fences form one block, even when the source contains blank lines.
        for start,end in zip(boundaries,boundaries[1:]):
            value=body[start:end]
            stripped=value.lstrip()
            if not stripped: continue
            kind=('code' if re.match(r'(`{3,}|~{3,})',stripped) else
                'heading' if any(start==h[0] for h in headings) else
                'warning' if re.match(r'>\s*\[!(?:WARNING|CAUTION|IMPORTANT)\]',stripped,re.I) else
                'list' if re.match(r'(?:[-+*]|[0-9]+[.)])\s',stripped) else
                'table' if re.search(r'^\s*\|?.*\|.*\n\s*\|?\s*:?-{3,}',value,re.M) else 'paragraph')
            blocks.append(_span(kind,start,end))
        for match in re.finditer(r'(?<!\\)\[[^\]\n]{1,256}\]\((#[A-Za-z0-9_.:%-]{1,256})\)',body):
            if any(b['kind']=='code' and b['start']<=match.start()<b['end'] for b in blocks): continue
            line_start=body.rfind('\n',0,match.start())+1
            line_end=body.find('\n',match.end())
            # Conservative grammar: inline-code lines require a richer parser
            # before their apparent links can be treated as references.
            if '`' in body[line_start:line_end if line_end>=0 else len(body)]: continue
            references.append(_span('link',match.start(),match.end(),target=match[1][1:]))
    else:
        for location in evidence.locations:
            if location['start']==location['end']: continue
            kind=location['kind']
            kind='table' if kind=='table-cell' else 'page' if kind=='page' else 'paragraph'
            blocks.append(_span(kind,location['start'],location['end']))
            level=(heading_levels or {}).get(location['index']) if media==DOCX else None
            if level:
                headings.append((location['start'],level,location['end']))
                blocks[-1]['kind']='heading'
    if len(blocks)>MAX_LOCATIONS or len(headings)>MAX_LOCATIONS or len(references)>MAX_LOCATIONS:
        raise ExtractionError('too_large')
    sections=[{'id':'s0','parent':None,'level':0,'start':0,'end':len(body),'heading':None,'anchor':None}]
    stack=[sections[0]]; anchors={}
    for start,level,end in headings:
        while len(stack)>1 and stack[-1]['level']>=level: stack.pop()['end']=start
        heading=_span('heading',start,end)
        label=body[start:end]
        if media=='text/markdown': label=re.sub(r'^ {0,3}#{1,6}[ \t]+','',label); label=re.sub(r'[ \t]+#+[ \t]*$','',label)
        anchor=re.sub(r'[^\w\- ]','',label.lower()).strip().replace(' ','-')[:256]
        item={'id':'s'+str(len(sections)),'parent':stack[-1]['id'],'level':level,'start':start,'end':len(body),'heading':heading,'anchor':anchor or None}
        if anchor: anchors.setdefault(anchor,[]).append(item['id'])
        sections.append(item); stack.append(item)
    for ordinal,block in enumerate(blocks):
        block['id']='b'+str(ordinal)
        block['section']=next((s['id'] for s in reversed(sections) if s['start']<=block['start']<s['end']),'s0')
    for ordinal,reference in enumerate(references):
        reference['id']='r'+str(ordinal)
        matches=anchors.get(reference['target'],[])
        reference['section']=matches[0] if len(matches)==1 else None
    result={'revision':1,'text_sha256':evidence.text_hash,'sections':sections,'blocks':blocks,'references':references,
        'pages':[dict(location) for location in evidence.locations if location['kind']=='page']}
    if len(json.dumps(result,ensure_ascii=False).encode())>MAX_STRUCTURE_BYTES: raise ExtractionError('too_large')
    return result


def build(evidence,media,original):
    if media!=DOCX: return derive(evidence,media)
    try: child=subprocess.run([sys.executable,'-m','czero_core.structure',str(original)],capture_output=True,timeout=25)
    except subprocess.TimeoutExpired: raise ExtractionError('parser_timeout') from None
    if child.returncode or len(child.stdout)>MAX_STRUCTURE_BYTES: raise ExtractionError('parser_failed')
    try:
        value=json.loads(child.stdout)
        if set(value)!={'text_sha256','headings'} or value['text_sha256']!=evidence.text_hash or type(value['headings']) is not dict:
            raise ValueError()
        levels={int(key):level for key,level in value['headings'].items()}
        if len(levels)>MAX_LOCATIONS or any(not 1<=key<=4194304 or type(level) is not int or not 1<=level<=6 for key,level in levels.items()): raise ValueError()
    except (ValueError,TypeError,KeyError): raise ExtractionError('parser_failed') from None
    return derive(evidence,media,heading_levels=levels)


def section_chunks(evidence,structure,*,profile='sections-v1',size=1200,overlap=150):
    if profile not in PROFILES: raise ValueError('invalid_chunking_profile')
    if profile=='fixed-v1': return chunks(evidence,size=size,overlap=overlap)
    if type(size) is not int or not 256<=size<=4096 or type(overlap) is not int or not 0<=overlap<=size//4:
        raise ValueError('invalid_chunk_limits')
    if structure['text_sha256']!=evidence.text_hash: raise ExtractionError('parser_failed')
    # Leaf intervals include each ancestor's introductory text exactly once.
    boundaries=sorted({0,len(evidence.text),*[s['start'] for s in structure['sections']]})
    result=[]
    for first,last in zip(boundaries,boundaries[1:]):
        if first==last: continue
        start=first
        while start<last:
            end=min(start+size,last)
            if end<last:
                candidates=[b['end'] for b in structure['blocks'] if start+size//2<=b['end']<=end]
                if candidates: end=max(candidates)
            body=evidence.text[start:end]
            section=next(s for s in reversed(structure['sections']) if s['start']<=start<s['end'])
            ancestors=[]; parent=section
            while parent['parent'] is not None:
                ancestors.append(parent['id']); parent=structure['sections'][int(parent['parent'][1:])]
            result.append({'index':len(result)+1,'start':start,'end':end,'text':body,
                'text_hash':hashlib.sha256(body.encode()).hexdigest(),
                'locations':[loc for loc in evidence.locations if loc['start']<end and loc['end']>start],
                'context':list(reversed(ancestors))})
            if len(result)>MAX_CHUNKS: raise ExtractionError('too_large')
            if end==last: break
            start=end-overlap
    return result


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(20,21)); resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    try:
        levels={}; evidence=_docx(_path(Path(sys.argv[1])),heading_levels=levels)
        print(json.dumps({'text_sha256':evidence.text_hash,'headings':levels}))
    except Exception: sys.exit(1)


if __name__=='__main__': main()
