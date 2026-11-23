# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic bounded evidence extraction, with no network or execution."""
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import zipfile

MAX_UPLOAD=10*1024*1024
MAX_PDF_BYTES=100*1024*1024
MAX_PDF_PAGES=2000
PYTHON_PDF_PAGES=200  # Existing short-document text layout and hashes.
MAX_TEXT_BYTES=2*1024*1024
MAX_CHARACTERS=1_000_000
MAX_LOCATIONS=4000
MAX_CHUNKS=4096
MEDIA_TYPES={'text/plain','text/markdown','application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
ERRORS={'unsupported_format','too_large','invalid_text','invalid_pdf','invalid_docx',
    'encrypted_pdf','no_text','unsupported_scan','archive_limit','unsupported_xml',
    'resource_limit','parser_timeout','pdf_too_many_pages','parser_failed','invalid_file','unsupported_docx','ocr_unavailable'}


class ExtractionError(ValueError):
    def __init__(self,code):
        self.code=code if code in ERRORS else 'parser_failed'
        super().__init__(self.code)


@dataclass(frozen=True)
class Extracted:
    text: str
    locations: list[dict]

    @property
    def text_hash(self):
        return hashlib.sha256(self.text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class TextLayer(Extracted):
    textless_pages: tuple[int, ...]


def upload_limit(media_type):
    return MAX_PDF_BYTES if media_type == 'application/pdf' else MAX_UPLOAD


def valid_text(text):
    try: size=len(text.encode('utf-8'))
    except UnicodeError:raise ExtractionError('invalid_text') from None
    if '\0' in text:raise ExtractionError('invalid_text')
    if len(text)>MAX_CHARACTERS or size>MAX_TEXT_BYTES:raise ExtractionError('too_large')
    return text


def _parts(parts,*,allow_empty=False):
    texts=[]; locations=[]; cursor=0
    for kind,index,text in parts:
        text=valid_text(text.replace('\r\n','\n').replace('\r','\n'))
        if not text.strip():continue
        if texts: texts.append('\n\n');cursor+=2
        start=cursor;texts.append(text);cursor+=len(text)
        if cursor>MAX_CHARACTERS or len(locations)>=MAX_LOCATIONS:raise ExtractionError('too_large')
        locations.append({'kind':kind,'index':index,'start':start,'end':cursor})
    result=valid_text(''.join(texts))
    if not result.strip() and not allow_empty:raise ExtractionError('no_text')
    return Extracted(result,locations)


def _docx(path,*,first=1,last=None,inventory=False,allow_empty=False,heading_levels=None):
    try:
        from lxml import etree
        namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        unsupported_tags = {'{' + namespace + '}' + tag for tag in
            ('sdt','ins','del','moveFrom','moveTo','txbxContent','altChunk',
             'customXml','smartTag','fldSimple','subDoc','object')}
        text_roots = {'{' + namespace + '}' + tag for tag in ('document','hdr','ftr')}
        def check_text_tree(root):
            if root.getroottree().docinfo.doctype:raise ExtractionError('unsupported_xml')
            if any(node.tag in unsupported_tags for node in root.iter()):raise ExtractionError('unsupported_docx')
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist()
            if len(entries)>1000 or sum(e.file_size for e in entries)>16*1024*1024:
                raise ExtractionError('archive_limit')
            for entry in entries:
                parts=Path(entry.filename).parts
                if entry.filename.startswith('/') or '..' in parts or entry.flag_bits & 1:
                    raise ExtractionError('invalid_docx')
                if entry.file_size>4*1024*1024 or entry.file_size>max(1024,entry.compress_size*100):
                    raise ExtractionError('archive_limit')
                if entry.filename.lower().endswith('vbaproject.bin'):raise ExtractionError('invalid_docx')
                if entry.filename in ('word/comments.xml','word/footnotes.xml','word/endnotes.xml'):
                    raise ExtractionError('invalid_docx')
                if entry.filename.lower().endswith(('.xml', '.rels')):
                    data=archive.read(entry)
                    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ExtractionError('unsupported_xml')
                    # Detect UTF-16 declarations too, without entity expansion
                    # or external fetching. Check actual roots, not filenames.
                    root=etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                    if root.getroottree().docinfo.doctype:raise ExtractionError('unsupported_xml')
                    if root.tag in text_roots:check_text_tree(root)
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        document=Document(path)
        # OPC relationships can give XML parts arbitrary names/extensions.
        check_text_tree(document.element)
        parts=[]; ordinal=0
        def paragraph(kind,item):
            nonlocal ordinal
            ordinal+=1
            if heading_levels is not None and kind=='paragraph':
                style=item.style.name if item.style is not None else ''
                match=re.fullmatch(r'Heading ([1-6])',style)
                if match: heading_levels[ordinal]=int(match[1])
            if inventory or (ordinal>=first and (last is None or ordinal<=last)):
                parts.append((kind,ordinal,item.text))
        def walk(container,kind):
            for item in container.iter_inner_content():
                if isinstance(item,Paragraph): paragraph(kind,item)
                elif isinstance(item,Table):
                    # Merged cells share XML; do not repeat their text.
                    seen=set()
                    for row in item.rows:
                        for cell in row.cells:
                            if cell._tc in seen:continue
                            seen.add(cell._tc);walk(cell,'table-cell')
        walk(document,'paragraph')
        headers=set()
        for section in document.sections:
            for kind in ('header','footer','first_page_header','first_page_footer','even_page_header','even_page_footer'):
                container=getattr(section,kind)
                # Accessing an undefined header creates an empty part: skip it.
                if not container._has_definition:continue
                check_text_tree(container.part.element)
                key=str(container.part.partname)
                if key in headers:continue
                headers.add(key);walk(container,kind)
        result=_parts(parts,allow_empty=allow_empty)
        if inventory:return {'blocks':ordinal,'characters':len(result.text),'text_sha256':result.text_hash}
        return result
    except ExtractionError:raise
    except MemoryError:raise ExtractionError('resource_limit') from None
    except Exception:raise ExtractionError('invalid_docx') from None


def _has_images(resources,seen=None,depth=0):
    seen=set() if seen is None else seen
    if depth>8 or len(seen)>1000:raise ExtractionError('too_large')
    if hasattr(resources,'get_object'):resources=resources.get_object()
    objects=resources.get('/XObject',{})
    if hasattr(objects,'get_object'):objects=objects.get_object()
    for reference in objects.values():
        obj=reference.get_object();key=id(obj)
        if key in seen:continue
        seen.add(key)
        if obj.get('/Subtype')=='/Image':return True
        if obj.get('/Subtype')=='/Form' and _has_images(obj.get('/Resources',{}),seen,depth+1):return True
    return False


def _pdf(path, *, allow_mixed_pdf=False):
    try:
        from pypdf import PdfReader
        logging.getLogger('pypdf').setLevel(logging.CRITICAL)
        # An open stream lets pypdf seek within the original without copying a
        # potentially 100 MiB file into BytesIO.
        with path.open('rb') as original:
            reader = PdfReader(original, strict=True)
            if reader.is_encrypted:
                raise ExtractionError('encrypted_pdf')
            page_count = len(reader.pages)
            if not 1 <= page_count <= MAX_PDF_PAGES:
                code = 'pdf_too_many_pages' if allow_mixed_pdf and page_count > MAX_PDF_PAGES else 'too_large'
                raise ExtractionError(code)
            if page_count > PYTHON_PDF_PAGES:
                # Short documents retain their historical extraction and hashes.
                # A single bounded native pass avoids a Python text-layout pass
                # on every page of a long document.
                from .pdf_units import native_pages
                pages = native_pages(path, page_count)
            else:
                pages = _short_pdf_pages(reader)
            textless = []
            parts = []
            scanned = False
            for index, text in enumerate(pages, 1):
                if not text.strip():
                    textless.append(index)
                    if _has_images(reader.pages[index - 1].get('/Resources', {})):
                        scanned = True
                        if not allow_mixed_pdf:
                            raise ExtractionError('unsupported_scan')
                parts.append(('page', index, text))
            if scanned and len(textless) == page_count:
                raise ExtractionError('unsupported_scan')
            document = _parts(parts)
            if allow_mixed_pdf:
                return TextLayer(document.text, document.locations, tuple(textless))
            return document
    except ExtractionError:raise
    except MemoryError:raise ExtractionError('resource_limit') from None
    except Exception:raise ExtractionError('invalid_pdf') from None


def _short_pdf_pages(reader):
    stream_bytes = 0
    for page in reader.pages:
        content = page.get_contents()
        if content is not None:
            stream_bytes += len(content.get_data())
            if stream_bytes > 16 * 1024 * 1024:
                raise ExtractionError('too_large')
        yield page.extract_text()


def extract_file(path: Path,media_type: str,*,allow_mixed_pdf=False):
    """Pure parser entry point; untrusted uploads call the isolated wrapper."""
    if media_type not in MEDIA_TYPES:raise ExtractionError('unsupported_format')
    path=Path(path)
    try: info=path.lstat()
    except OSError:raise ExtractionError('invalid_file') from None
    if not stat.S_ISREG(info.st_mode):raise ExtractionError('invalid_file')
    if info.st_size>upload_limit(media_type):raise ExtractionError('too_large')
    if media_type=='application/pdf':return _pdf(path,allow_mixed_pdf=allow_mixed_pdf)
    if media_type.endswith('wordprocessingml.document'):return _docx(path)
    try:text=valid_text(path.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))
    except UnicodeError:raise ExtractionError('invalid_text') from None
    if not text.strip():raise ExtractionError('no_text')
    if media_type=='text/plain':return Extracted(text,[{'kind':'body','index':1,'start':0,'end':len(text)}])
    headings=list(re.finditer(r'^#{1,6} [^\n]+',text,re.MULTILINE))
    starts=sorted(set([0]+[h.start() for h in headings]))
    if len(starts)>MAX_LOCATIONS:raise ExtractionError('too_large')
    locations=[{'kind':'section','index':i+1,'start':start,'end':starts[i+1] if i+1<len(starts) else len(text)} for i,start in enumerate(starts)]
    return Extracted(text,locations)


def chunks(document: Extracted,*,size=1200,overlap=150):
    if type(size) is not int or not 256<=size<=4096 or type(overlap) is not int or not 0<=overlap<=size//4:
        raise ValueError('invalid_chunk_limits')
    valid_text(document.text);result=[];start=0
    while start<len(document.text):
        end=min(start+size,len(document.text));text=document.text[start:end]
        locations=[location for location in document.locations if location['start']<end and location['end']>start]
        result.append({'index':len(result)+1,'start':start,'end':end,'text':text,
            'text_hash':hashlib.sha256(text.encode('utf-8')).hexdigest(),'locations':locations})
        if len(result)>MAX_CHUNKS:raise ExtractionError('too_large')
        if end==len(document.text):break
        start=end-overlap
    return result


def parser_output(command):
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          start_new_session=True) as parser:
        try:
            output, _ = parser.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            os.killpg(parser.pid, signal.SIGKILL)
            parser.communicate()
            raise ExtractionError('parser_timeout') from None
        finally:
            # The long-PDF parser runs Poppler as a child in the same group.
            try: os.killpg(parser.pid, signal.SIGKILL)
            except ProcessLookupError: pass
    if len(output)>16*1024*1024:raise ExtractionError('resource_limit')
    if parser.returncode!=0:raise ExtractionError('resource_limit' if parser.returncode<0 else 'parser_failed')
    return output


def extract_isolated(path: Path,media_type: str,*,allow_mixed_pdf=False):
    """Trusted fixed parser command, bounded by child rlimits and parent time."""
    if media_type not in MEDIA_TYPES:raise ExtractionError('unsupported_format')
    command = [sys.executable, '-m', 'czero_core.extraction', str(path), media_type]
    if allow_mixed_pdf:
        if media_type != 'application/pdf':
            raise ExtractionError('unsupported_format')
        command.append('text-layer')
    output = parser_output(command)
    try:
        payload=json.loads(output)
        if 'error' in payload:raise ExtractionError(payload['error'])
        document=Extracted(valid_text(payload['text']),payload['locations'])
        if not isinstance(document.locations,list) or len(document.locations)>MAX_LOCATIONS:raise ValueError()
        if any(type(loc) is not dict or set(loc)!={'kind','index','start','end'} or not 0<=loc['start']<=loc['end']<=len(document.text) for loc in document.locations):raise ValueError()
        if allow_mixed_pdf:
            pages = payload['textless_pages']
            if (type(pages) is not list or len(pages) > MAX_PDF_PAGES
                or any(type(page) is not int or not 1 <= page <= MAX_PDF_PAGES for page in pages)
                or pages != sorted(set(pages))):
                raise ValueError()
            return TextLayer(document.text, document.locations, tuple(pages))
        return document
    except ExtractionError:raise
    except Exception:raise ExtractionError('parser_failed') from None


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(20,21))
    # Native PDF extraction writes only to bounded, anonymous temporary files.
    pdf = len(sys.argv) >= 3 and sys.argv[2] == 'application/pdf'
    write_limit = MAX_TEXT_BYTES + MAX_PDF_PAGES + 1 if pdf else 0
    resource.setrlimit(resource.RLIMIT_FSIZE, (write_limit, write_limit))
    try:
        allow_mixed_pdf = pdf and sys.argv[3:] == ['text-layer']
        if len(sys.argv)!=3 and not allow_mixed_pdf:raise ExtractionError('invalid_file')
        result=extract_file(Path(sys.argv[1]),sys.argv[2],allow_mixed_pdf=allow_mixed_pdf)
        output = {'text':result.text,'locations':result.locations}
        if allow_mixed_pdf:
            output['textless_pages'] = result.textless_pages
        print(json.dumps(output, ensure_ascii=False))
    except ExtractionError as error:print(json.dumps({'error':error.code}))
    except MemoryError:print(json.dumps({'error':'resource_limit'}))
    except Exception:print(json.dumps({'error':'parser_failed'}))


if __name__=='__main__':
    # Helpers import the canonical ExtractionError class when run as a module.
    from czero_core.extraction import main as parser_main
    parser_main()
