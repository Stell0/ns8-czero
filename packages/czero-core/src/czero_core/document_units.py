# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic rich/text units with canonical whole-document readback."""
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

from .extraction import Extracted,ExtractionError,MAX_UPLOAD,MAX_LOCATIONS,_docx,valid_text

DOCX='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
KINDS={'paragraph','table-cell','header','footer','first_page_header','first_page_footer','even_page_header','even_page_footer'}


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _path(path):
    path=Path(path)
    try: info=path.lstat()
    except OSError: raise ExtractionError('invalid_file') from None
    if not stat.S_ISREG(info.st_mode): raise ExtractionError('invalid_file')
    if info.st_size>MAX_UPLOAD: raise ExtractionError('too_large')
    return path


def _text(path):
    try: body=valid_text(path.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))
    except UnicodeError: raise ExtractionError('invalid_text') from None
    if not body.strip(): raise ExtractionError('no_text')
    return body


def text_blocks(body,markdown,*,max_boundaries=None):
    """C0's bounded ATX/fence grammar; only LF separates source lines."""
    boundaries={0,len(body)}; headings=[]; fence=None
    def add(value):
        boundaries.add(value)
        if max_boundaries is not None and len(boundaries)>max_boundaries: raise ExtractionError('too_large')
    for match in re.finditer(r'[^\n]*(?:\n|$)',body):
        if match.start()==match.end(): continue
        line=match.group()
        if fence is not None:
            if re.fullmatch(r' {0,3}'+re.escape(fence[0])+r'{'+str(fence[1])+r',}[ \t]*\n?',line):
                fence=None; add(match.end())
            continue
        opening=re.match(r' {0,3}(`{3,}|~{3,})([^\n]*)',line) if markdown else None
        if opening and not (opening[1][0]=='`' and '`' in opening[2]):
            fence=(opening[1][0],len(opening[1])); add(match.start()); continue
        heading=re.match(r' {0,3}(#{1,6})[ \t]+[^\n]*',line) if markdown else None
        if heading:
            add(match.start()); headings.append((match.start(),len(heading[1])))
        if not line.strip(): add(match.end())
    return sorted(boundaries),headings


def validate_spec(media,spec):
    expected={'blocks','characters','text_sha256'} if media==DOCX else {'ranges','characters','text_sha256'}
    if type(spec) is not dict or set(spec)!=expected: raise ValueError('invalid_manifest')
    if type(spec['characters']) is not int or not 1<=spec['characters']<=1000000: raise ValueError('invalid_manifest')
    if not isinstance(spec['text_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',spec['text_sha256']): raise ValueError('invalid_manifest')
    if media==DOCX:
        if type(spec['blocks']) is not int or not 1<=spec['blocks']<=4194304: raise ValueError('invalid_manifest')
    else:
        if media not in ('text/plain','text/markdown') or type(spec['ranges']) is not list or not 1<=len(spec['ranges'])<=200:
            raise ValueError('invalid_manifest')
        end=0
        for span in spec['ranges']:
            if (type(span) is not list or len(span)!=2 or any(type(x) is not int for x in span)
                or span[0]!=end or not span[0]<span[1]<=spec['characters']): raise ValueError('invalid_manifest')
            end=span[1]
        if end!=spec['characters']: raise ValueError('invalid_manifest')
    return spec


def locators(media,spec):
    validate_spec(media,spec)
    if media==DOCX:
        count=spec['blocks']; group=count if count<=64 else max(32,(count+199)//200)
        return [{'kind':'blocks','first':first,'last':min(count,first+group-1)} for first in range(1,count+1,group)]
    return [{'kind':'characters','start':start,'end':end} for start,end in spec['ranges']]


def _inventory(path,media):
    if media==DOCX: return _docx(path,inventory=True)
    body=_text(path); boundaries,_=text_blocks(body,media=='text/markdown')
    spans=[]; start=0
    for end in boundaries[1:]:
        if end-start>=32768:
            spans.append([start,end]); start=end
    if start<len(body): spans.append([start,len(body)])
    return {'ranges':spans,'characters':len(body),'text_sha256':hashlib.sha256(body.encode()).hexdigest()}


def validate_fragment(evidence,locator):
    if not isinstance(evidence,Extracted) or type(evidence.text) is not str: raise ExtractionError('parser_failed')
    valid_text(evidence.text)
    if '\r' in evidence.text or type(evidence.locations) is not list or len(evidence.locations)>MAX_LOCATIONS:
        raise ExtractionError('parser_failed')
    if locator['kind']=='characters':
        expected=[{'kind':'body','index':1,'start':0,'end':len(evidence.text)}]
        if len(evidence.text)!=locator['end']-locator['start'] or evidence.locations!=expected:
            raise ExtractionError('parser_failed')
    else:
        cursor=0; previous=locator['first']-1
        for index,location in enumerate(evidence.locations):
            if (type(location) is not dict or set(location)!={'kind','index','start','end'}
                or any(type(location[k]) is not int for k in ('index','start','end'))
                or location['kind'] not in KINDS or not previous<location['index']<=locator['last']
                or location['start']!=cursor+(2 if index else 0)
                or not location['start']<location['end']<=len(evidence.text)
                or (index and evidence.text[cursor:location['start']]!='\n\n')
                or not evidence.text[location['start']:location['end']].strip()):
                raise ExtractionError('parser_failed')
            previous=location['index']; cursor=location['end']
        if cursor!=len(evidence.text): raise ExtractionError('parser_failed')
    return evidence


def _parse(path,media,locator):
    if type(locator) is not dict: raise ExtractionError('parser_failed')
    if media==DOCX:
        if (set(locator)!={'kind','first','last'} or locator['kind']!='blocks'
            or any(type(locator[k]) is not int for k in ('first','last'))
            or not 1<=locator['first']<=locator['last']<=4194304): raise ExtractionError('parser_failed')
        evidence=_docx(path,first=locator['first'],last=locator['last'],allow_empty=True)
    else:
        if (set(locator)!={'kind','start','end'} or locator['kind']!='characters'
            or any(type(locator[k]) is not int for k in ('start','end'))): raise ExtractionError('parser_failed')
        body=_text(path)
        if not 0<=locator['start']<locator['end']<=len(body): raise ExtractionError('parser_failed')
        body=body[locator['start']:locator['end']]
        evidence=Extracted(body,[{'kind':'body','index':1,'start':0,'end':len(body)}])
    return validate_fragment(evidence,locator)


def _isolated(path,media,mode,locator=None):
    if media not in ('text/plain','text/markdown',DOCX): raise ExtractionError('unsupported_format')
    command=[sys.executable,'-m','czero_core.document_units',str(path),media,mode]
    if locator is not None: command.append(json.dumps(locator,separators=(',', ':')))
    try: result=subprocess.run(command,capture_output=True,timeout=25,check=False)
    except subprocess.TimeoutExpired: raise ExtractionError('parser_timeout') from None
    if len(result.stdout)>16*1024*1024: raise ExtractionError('resource_limit')
    if result.returncode: raise ExtractionError('resource_limit' if result.returncode<0 else 'parser_failed')
    try:
        payload=json.loads(result.stdout)
        if 'error' in payload: raise ExtractionError(payload['error'])
        return payload
    except ExtractionError: raise
    except Exception: raise ExtractionError('parser_failed') from None


def inventory_isolated(path,media):
    try: return validate_spec(media,_isolated(path,media,'inventory'))
    except ExtractionError: raise
    except (ValueError,TypeError,KeyError): raise ExtractionError('parser_failed') from None


def extract_unit_isolated(path,media,locator):
    value=_isolated(path,media,'unit',locator)
    if type(value) is not dict or set(value)!={'text','locations'}: raise ExtractionError('parser_failed')
    return validate_fragment(Extracted(value['text'],value['locations']),locator)


def assemble(rows,media,spec):
    expected=locators(media,spec)
    if len(rows)!=len(expected): raise ExtractionError('parser_failed')
    texts=[]; locations=[]; cursor=0
    for ordinal,(row,locator) in enumerate(zip(rows,expected),1):
        if type(row['ordinal']) is not int or row['ordinal']!=ordinal or row['state']!='succeeded' or _hash(row['locator'])!=_hash(locator):
            raise ExtractionError('parser_failed')
        evidence=validate_fragment(Extracted(row['body'],row['locations']),locator)
        if row['text_sha256']!=evidence.text_hash or row['result_sha256']!=_hash({'text':evidence.text,'locations':evidence.locations}):
            raise ExtractionError('parser_failed')
        if media==DOCX and not evidence.text: continue
        if media==DOCX and texts: texts.append('\n\n'); cursor+=2
        locations.extend({**entry,'start':entry['start']+cursor,'end':entry['end']+cursor} for entry in evidence.locations)
        texts.append(evidence.text); cursor+=len(evidence.text)
    body=valid_text(''.join(texts))
    if not body.strip(): raise ExtractionError('no_text')
    if len(body)!=spec['characters'] or hashlib.sha256(body.encode()).hexdigest()!=spec['text_sha256']:
        raise ExtractionError('parser_failed')
    if media=='text/plain': locations=[{'kind':'body','index':1,'start':0,'end':len(body)}]
    elif media=='text/markdown':
        _,headings=text_blocks(body,True); starts=sorted({0,*[start for start,_ in headings]})
        locations=[{'kind':'section','index':i+1,'start':start,'end':starts[i+1] if i+1<len(starts) else len(body)} for i,start in enumerate(starts)]
    if len(locations)>MAX_LOCATIONS: raise ExtractionError('too_large')
    return Extracted(body,locations)


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(20,21)); resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    try:
        if len(sys.argv) not in (4,5): raise ExtractionError('invalid_file')
        path=_path(sys.argv[1]); media=sys.argv[2]; mode=sys.argv[3]
        if media not in ('text/plain','text/markdown',DOCX): raise ExtractionError('unsupported_format')
        if mode=='inventory' and len(sys.argv)==4: result=_inventory(path,media)
        elif mode=='unit' and len(sys.argv)==5:
            evidence=_parse(path,media,json.loads(sys.argv[4])); result={'text':evidence.text,'locations':evidence.locations}
        else: raise ExtractionError('parser_failed')
        print(json.dumps(result,ensure_ascii=False))
    except ExtractionError as error: print(json.dumps({'error':error.code}))
    except MemoryError: print(json.dumps({'error':'resource_limit'}))
    except Exception: print(json.dumps({'error':'parser_failed'}))


if __name__=='__main__': main()
