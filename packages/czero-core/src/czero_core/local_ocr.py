# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""One registered local adapter; never a request-selected command or provider."""
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

from .extraction import Extracted,ExtractionError,valid_text
from .pdf_units import _reader,validate_page

LANGUAGES=('eng','ita','eng+ita')
ENGINE=Path('/usr/bin/tesseract')
RENDERER=Path('/usr/bin/pdftoppm')
DATA=Path('/usr/share/tesseract-ocr/5/tessdata')
HASH=re.compile('[0-9a-f]{64}')
PARENT_SECONDS=25


def validate_profile(value):
    if (type(value) is not dict or set(value)!={'adapter','revision','engine_sha256','renderer_sha256','engine_build_sha256','renderer_build_sha256','models','language','dpi','scale'}
        or value['adapter']!='local-tesseract' or type(value['revision']) is not int or value['revision']!=1
        or value['language'] not in LANGUAGES or type(value['dpi']) is not int or value['dpi']!=150
        or type(value['scale']) is not int or value['scale']!=2400
        or type(value['models']) is not dict or set(value['models'])!=set(value['language'].split('+'))
        or any(type(item) is not str or HASH.fullmatch(item) is None for item in
            [value['engine_sha256'],value['renderer_sha256'],value['engine_build_sha256'],value['renderer_build_sha256'],*value['models'].values()])):
        raise ValueError('invalid_ocr_profile')
    return value


def _digest(path):
    if not path.is_file() or path.stat().st_size>33554432: raise ExtractionError('ocr_unavailable')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_digest(path,option):
    value=subprocess.run([str(path),option],capture_output=True,timeout=5,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','OMP_THREAD_LIMIT':'1'})
    output=value.stdout+value.stderr
    if value.returncode or not output or len(output)>4096: raise ExtractionError('ocr_unavailable')
    return hashlib.sha256(output).hexdigest()


def preflight(language='eng'):
    if language not in LANGUAGES: raise ValueError('invalid_ocr_language')
    try:
        return validate_profile({'adapter':'local-tesseract','revision':1,'engine_sha256':_digest(ENGINE),
            'renderer_sha256':_digest(RENDERER),'engine_build_sha256':_build_digest(ENGINE,'--version'),
            'renderer_build_sha256':_build_digest(RENDERER,'-v'),
            'models':{name:_digest(DATA/(name+'.traineddata')) for name in language.split('+')},
            'language':language,'dpi':150,'scale':2400})
    except (OSError,subprocess.TimeoutExpired): raise ExtractionError('ocr_unavailable') from None


def validate_provenance(value,profile,page):
    validate_profile(profile)
    if (type(value) is not dict or set(value)!={'adapter','page','language','confidence','words','profile_sha256'}
        or value['adapter']!='local-tesseract' or type(value['page']) is not int or value['page']!=page
        or value['language']!=profile['language'] or type(value['words']) is not int or not 1<=value['words']<=1000000
        or type(value['confidence']) not in (int,float) or not math.isfinite(value['confidence']) or not 0<=value['confidence']<=100
        or value['profile_sha256']!=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',', ':')).encode()).hexdigest()):
        raise ExtractionError('parser_failed')
    return value


def _tsv(raw):
    if len(raw)>16*1024*1024: raise ExtractionError('resource_limit')
    rows=csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter='\t')
    expected=['level','page_num','block_num','par_num','line_num','word_num','left','top','width','height','conf','text']
    if rows.fieldnames!=expected: raise ExtractionError('parser_failed')
    lines=[]; words=[]; confidences=[]; previous=None
    for row in rows:
        if set(row)!=set(expected): raise ExtractionError('parser_failed')
        if row['level']!='5': continue
        value=row['text'].strip()
        if not value: continue
        confidence=float(row['conf'])
        if not math.isfinite(confidence) or not 0<=confidence<=100: raise ExtractionError('parser_failed')
        key=tuple(int(row[name]) for name in ('page_num','block_num','par_num','line_num'))
        if previous is not None and key!=previous:
            lines.append(' '.join(words)); words=[]
        words.append(value); confidences.append(confidence); previous=key
        if len(confidences)>1000000: raise ExtractionError('too_large')
    if words: lines.append(' '.join(words))
    body=valid_text('\n'.join(lines))
    if not body.strip(): raise ExtractionError('no_text')
    return body,round(sum(confidences)/len(confidences),4),len(confidences)


def _parse(path,page,profile):
    validate_profile(profile)
    if profile!=preflight(profile['language']): raise ExtractionError('ocr_unavailable')
    reader=_reader(path)
    if type(page) is not int or not 1<=page<=len(reader.pages): raise ExtractionError('invalid_pdf')
    with TemporaryDirectory(prefix='c0-ocr-') as directory:
        environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','OMP_THREAD_LIMIT':'1','HOME':directory,'TMPDIR':directory}
        prefix=str(Path(directory)/'page')
        rendered=subprocess.run([str(RENDERER),'-f',str(page),'-l',str(page),'-singlefile','-gray','-png',
            '-r','150','-scale-to','2400',str(path),prefix],env=environment,capture_output=True,timeout=10)
        image=Path(prefix+'.png')
        if rendered.returncode or not image.is_file() or image.stat().st_size>16777216: raise ExtractionError('parser_failed')
        parsed=subprocess.run([str(ENGINE),str(image),'stdout','--tessdata-dir',str(DATA),'-l',profile['language'],'--psm','3','tsv'],
            env=environment,capture_output=True,timeout=15)
        if parsed.returncode: raise ExtractionError('parser_failed')
        body,confidence,words=_tsv(parsed.stdout)
        if profile!=preflight(profile['language']): raise ExtractionError('ocr_unavailable')
    provenance={'adapter':'local-tesseract','page':page,'language':profile['language'],'confidence':confidence,'words':words,
        'profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',', ':')).encode()).hexdigest()}
    return {'text':body,'locations':[{'kind':'page','index':page,'start':0,'end':len(body)}],'provenance':provenance}


@dataclass(frozen=True)
class ParsedPage:
    evidence: Extracted
    provenance: dict


def extract_unit(path,page,profile):
    """Fixed adapter call; kill descendants as well as their coordinator."""
    validate_profile(profile)
    if type(page) is not int or not 1<=page<=200: raise ValueError('invalid_page')
    environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','OMP_THREAD_LIMIT':'1'}
    if 'PYTHONPATH' in os.environ: environment['PYTHONPATH']=os.environ['PYTHONPATH']
    child=subprocess.Popen([sys.executable,'-m','czero_core.local_ocr',str(path),str(page),json.dumps(profile)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env=environment)
    try: output,_=child.communicate(timeout=PARENT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL); child.communicate()
        raise ExtractionError('parser_timeout') from None
    finally:
        # A failed coordinator must not leave a rasterizer/OCR process running.
        try: os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    if child.returncode or len(output)>16*1024*1024: raise ExtractionError('resource_limit')
    try:
        value=json.loads(output)
        if 'error' in value: raise ExtractionError(value['error'])
        if set(value)!={'text','locations','provenance'}: raise ValueError()
        return ParsedPage(validate_page(Extracted(value['text'],value['locations']),page),
            validate_provenance(value['provenance'],profile,page))
    except ExtractionError: raise
    except (ValueError,TypeError,KeyError): raise ExtractionError('parser_failed') from None


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(20,21)); resource.setrlimit(resource.RLIMIT_FSIZE,(16777216,16777216))
    try: print(json.dumps(_parse(Path(sys.argv[1]),int(sys.argv[2]),json.loads(sys.argv[3])),ensure_ascii=False))
    except ExtractionError as error: print(json.dumps({'error':error.code}))
    except subprocess.TimeoutExpired: print(json.dumps({'error':'parser_timeout'}))
    except MemoryError: print(json.dumps({'error':'resource_limit'}))
    except Exception: print(json.dumps({'error':'parser_failed'}))


if __name__=='__main__': main()
