# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded page parsing from the immutable PDF original and exact assembly."""
from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
import signal
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory, TemporaryFile

from .extraction import (
    Extracted, ExtractionError, MAX_PDF_BYTES, MAX_PDF_PAGES, MAX_TEXT_BYTES,
    PYTHON_PDF_PAGES, _has_images, parser_output, valid_text,
)


@contextmanager
def _reader(path):
    from pypdf import PdfReader
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode): raise ExtractionError('invalid_file')
    if path.stat().st_size > MAX_PDF_BYTES: raise ExtractionError('too_large')
    logging.getLogger('pypdf').setLevel(logging.CRITICAL)
    with path.open('rb') as original:
        reader = PdfReader(original, strict=True)
        if reader.is_encrypted: raise ExtractionError('encrypted_pdf')
        if not 1 <= len(reader.pages) <= MAX_PDF_PAGES: raise ExtractionError('too_large')
        yield reader


def native_pages(path, page_count, *, page=None):
    """Extract the text layer in a single bounded pass, preserving page breaks."""
    limit = MAX_TEXT_BYTES + MAX_PDF_PAGES
    selection = [] if page is None else ['-f', str(page), '-l', str(page)]
    # prlimit execs the fixed tool. Limits precede opening the PDF; the
    # threaded web/worker process never runs a Python preexec callback.
    command = ['/usr/bin/prlimit', '--as=536870912', '--cpu=15:16', f'--fsize={limit + 1}',
               '--core=0', '--', '/usr/bin/pdftotext', '-enc', 'UTF-8', '-eol', 'unix',
               *selection, str(Path(path).resolve()), '-']
    try:
        with TemporaryDirectory(prefix='c0-pdf-text-') as directory, \
             TemporaryFile(dir=directory) as output, TemporaryFile(dir=directory) as errors:
            child = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                env={'LC_ALL':'C', 'HOME':directory, 'TMPDIR':directory},
                cwd=directory, timeout=18, check=False)
            if output.tell() > limit or child.returncode == -signal.SIGXFSZ:
                raise ExtractionError('too_large')
            if child.returncode < 0 or errors.tell() > 65536:
                raise ExtractionError('resource_limit')
            if child.returncode in (126, 127):
                raise ExtractionError('parser_failed')
            # Poppler sometimes reports a repair or incomplete output and still
            # exits successfully. Never publish it or expose private diagnostics.
            if child.returncode or errors.tell():
                raise ExtractionError('invalid_pdf')
            output.seek(0)
            pages = output.read(limit + 1).decode('utf-8').split('\f')
    except UnicodeDecodeError:
        raise ExtractionError('invalid_text') from None
    except subprocess.TimeoutExpired:
        raise ExtractionError('parser_timeout') from None
    except OSError:
        raise ExtractionError('parser_failed') from None
    expected = page_count if page is None else 1
    if len(pages) != expected + 1 or pages.pop() != '':
        raise ExtractionError('invalid_pdf')
    return pages


def _blank(page):
    if page.get('/Annots') or _has_images(page.get('/Resources',{})):
        raise ExtractionError('unsupported_scan')
    content=page.get_contents()
    if content is not None:
        # Empty extraction is not evidence of a blank graphical page. Permit
        # only known non-painting operators; inline images and Forms fail closed.
        allowed={b'q',b'Q',b'cm',b'w',b'J',b'j',b'M',b'd',b'ri',b'i',b'gs',
            b'm',b'l',b'c',b'v',b'y',b'h',b're',b'n',b'W',b'W*',
            b'CS',b'cs',b'SC',b'SCN',b'sc',b'scn',b'G',b'g',b'RG',b'rg',b'K',b'k',
            b'BT',b'ET',b'Tc',b'Tw',b'Tz',b'TL',b'Tf',b'Tr',b'Ts',b'Td',b'TD',
            b'Tm',b'T*',b'Tj',b'TJ',b"'",b'"',b'MP',b'DP',b'BMC',b'BDC',b'EMC'}
        operations=content.operations
        if len(operations)>100000 or any(operator not in allowed for _,operator in operations):
            raise ExtractionError('unsupported_scan')


def _parse(path,mode,page=None):
    with _reader(path) as reader:
        return _parse_reader(reader, path, mode, page)


def _parse_reader(reader, path, mode, page):
    if mode=='inventory':
        if len(reader.pages) > PYTHON_PDF_PAGES:
            # Page workers enforce native parser limits per unit. Do not inflate
            # every content stream just to determine a long document's extent.
            return {'pages':len(reader.pages)}
        total=0
        for value in reader.pages:
            content=value.get_contents()
            if content is not None: total+=len(content.get_data())
            if total>16*1024*1024: raise ExtractionError('too_large')
        return {'pages':len(reader.pages)}
    if mode!='page' or type(page) is not int or not 1<=page<=len(reader.pages):
        raise ExtractionError('invalid_pdf')
    value=reader.pages[page-1]
    if len(reader.pages) > PYTHON_PDF_PAGES:
        body = valid_text(native_pages(path, len(reader.pages), page=page)[0])
    else:
        content=value.get_contents()
        if content is not None and len(content.get_data())>16*1024*1024:
            raise ExtractionError('too_large')
        body=valid_text(value.extract_text().replace('\r\n','\n').replace('\r','\n'))
    if not body.strip():
        _blank(value)
        return {'text':'','locations':[]}
    return {'text':body,'locations':[{'kind':'page','index':page,'start':0,'end':len(body)}]}


def _isolated(path,mode,page=None):
    command=[sys.executable,'-m','czero_core.pdf_units',str(path),mode]
    if page is not None: command.append(str(page))
    output = parser_output(command)
    try:
        payload=json.loads(output)
        if 'error' in payload: raise ExtractionError(payload['error'])
        return payload
    except ExtractionError: raise
    except Exception: raise ExtractionError('parser_failed') from None


def inventory_isolated(path):
    value=_isolated(path,'inventory')
    if type(value) is not dict or set(value)!={'pages'} or type(value['pages']) is not int or not 1<=value['pages']<=MAX_PDF_PAGES:
        raise ExtractionError('parser_failed')
    return value['pages']


def validate_page(evidence,page):
    if not isinstance(evidence,Extracted) or type(evidence.text) is not str:
        raise ExtractionError('parser_failed')
    valid_text(evidence.text)
    expected=[{'kind':'page','index':page,'start':0,'end':len(evidence.text)}] if evidence.text else []
    if ('\r' in evidence.text or (evidence.text and not evidence.text.strip())
        or evidence.locations!=expected
        or any(type(loc.get(key)) is not int for loc in evidence.locations for key in ('index','start','end'))):
        raise ExtractionError('parser_failed')
    return evidence


def extract_page_isolated(path,page):
    if type(page) is not int or not 1<=page<=MAX_PDF_PAGES: raise ValueError('invalid_page')
    payload=_isolated(path,'page',page)
    if type(payload) is not dict or set(payload)!={'text','locations'}:
        raise ExtractionError('parser_failed')
    return validate_page(Extracted(payload['text'],payload['locations']),page)


def assemble_pdf(rows,pages):
    if type(pages) is not int or not 1<=pages<=MAX_PDF_PAGES or len(rows)!=pages:
        raise ExtractionError('parser_failed')
    texts=[]; locations=[]; cursor=0
    for page,row in enumerate(rows,1):
        locator={'kind':'page','first':page,'last':page}
        if (type(row['ordinal']) is not int or row['ordinal']!=page or row['state']!='succeeded'
            or row['locator']!=locator or any(type(row['locator'][key]) is not int for key in ('first','last'))):
            raise ExtractionError('parser_failed')
        evidence=validate_page(Extracted(row['body'],row['locations']),page)
        payload=json.dumps({'text':evidence.text,'locations':evidence.locations},sort_keys=True,
            separators=(',', ':'),ensure_ascii=False,allow_nan=False)
        if (evidence.text_hash!=row['text_sha256']
            or hashlib.sha256(payload.encode()).hexdigest()!=row['result_sha256']):
            raise ExtractionError('parser_failed')
        if not evidence.text: continue
        if texts: texts.append('\n\n'); cursor+=2
        start=cursor; texts.append(evidence.text); cursor+=len(evidence.text)
        locations.append({'kind':'page','index':page,'start':start,'end':cursor})
    body=valid_text(''.join(texts))
    if not body.strip(): raise ExtractionError('no_text')
    return Extracted(body,locations)


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(20,21))
    write_limit = MAX_TEXT_BYTES + MAX_PDF_PAGES + 1
    resource.setrlimit(resource.RLIMIT_FSIZE,(write_limit,write_limit))
    try:
        if len(sys.argv) not in (3,4): raise ExtractionError('invalid_file')
        result=_parse(sys.argv[1],sys.argv[2],int(sys.argv[3]) if len(sys.argv)==4 else None)
        print(json.dumps(result,ensure_ascii=False))
    except ExtractionError as error: print(json.dumps({'error':error.code}))
    except MemoryError: print(json.dumps({'error':'resource_limit'}))
    except Exception: print(json.dumps({'error':'invalid_pdf'}))


if __name__=='__main__': main()
