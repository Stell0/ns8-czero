# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated encryption inspection and anonymous working copies of approved PDFs."""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import io
import json
import logging
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryFile
from threading import BoundedSemaphore

from .extraction import ExtractionError, MAX_PDF_BYTES, MAX_PDF_PAGES, parser_output

MAX_PASSWORD_BYTES = 1024
MAX_WORKING_PDF_BYTES = 128 * 1024 * 1024
_INSPECTION_SLOT = BoundedSemaphore(1)


@dataclass(frozen=True)
class PDFProtection:
    encrypted: bool
    restricted: bool
    password_required: bool


@dataclass(frozen=True)
class WorkingPDF:
    """The owning context keeps the anonymous file open across parser subprocesses."""
    descriptor: int

    def __str__(self):
        return f'/proc/self/fd/{self.descriptor}'

    def lstat(self):
        return os.fstat(self.descriptor)

    def open(self, mode):
        return Path(str(self)).open(mode)


def parser_input(path):
    """Encode a trusted working file descriptor separately from ordinary paths."""
    if isinstance(path, WorkingPDF):
        return f'fd:{path.descriptor}', (path.descriptor,)
    return os.path.abspath(path), ()


def receive_parser_input(value):
    if value.startswith('fd:'):
        return WorkingPDF(int(value[3:]))
    return Path(value)


def native_input(path):
    if isinstance(path, WorkingPDF):
        return str(path), (path.descriptor,)
    return str(Path(path).resolve()), ()


def _check_source(descriptor):
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise ExtractionError('invalid_file')
    if info.st_size > MAX_PDF_BYTES:
        raise ExtractionError('too_large')


@contextmanager
def _inspection_descriptor(stream):
    try:
        stream.flush()
        descriptor = stream.fileno()
    except (AttributeError, io.UnsupportedOperation):
        # Core callers can provide in-memory streams. Allow the parser only a
        # bounded anonymous copy and restore the caller's read position.
        position = stream.tell()
        try:
            stream.seek(0)
            with TemporaryFile() as source:
                size = 0
                while block := stream.read(65536):
                    size += len(block)
                    if size > MAX_PDF_BYTES:
                        raise ExtractionError('too_large')
                    source.write(block)
                source.flush()
                yield source.fileno()
        finally:
            stream.seek(position)
    else:
        yield descriptor


def _run(source, password, *, output=None, restricted_approved=False):
    if password is not None:
        try:
            if not isinstance(password, str) or len(password.encode()) > MAX_PASSWORD_BYTES:
                raise ExtractionError('pdf_password_incorrect')
        except UnicodeError:
            raise ExtractionError('pdf_password_incorrect') from None
    _check_source(source)
    descriptors = (source,) if output is None else (source, output)
    command = [sys.executable, '-m', 'czero_core.protected_pdf', *map(str, descriptors)]
    if restricted_approved:
        command.append('approved')
    environment = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    if 'PYTHONPATH' in os.environ:
        environment['PYTHONPATH'] = os.environ['PYTHONPATH']
    result = parser_output(command, pass_fds=descriptors, input_data=json.dumps(password).encode(),
        timeout=5 if output is None else 20, env=environment)
    try:
        data = json.loads(result)
        if 'error' in data:
            raise ExtractionError(data['error'])
        fields = ('encrypted', 'restricted', 'password_required')
        if set(data) != set(fields) or any(type(data[key]) is not bool for key in fields):
            raise ValueError()
        return PDFProtection(*(data[key] for key in fields))
    except ExtractionError:
        raise
    except (TypeError, ValueError, KeyError):
        raise ExtractionError('parser_failed') from None


def inspect_pdf(stream, password: str | None = None) -> PDFProtection:
    """Read the encryption dictionary without queuing, extracting, or moving the stream."""
    if not _INSPECTION_SLOT.acquire(blocking=False):
        raise ExtractionError('resource_limit')
    try:
        with _inspection_descriptor(stream) as source:
            return _run(source, password)
    finally:
        _INSPECTION_SLOT.release()


@contextmanager
def working_pdf(path, password: str | None, *, restricted_approved: bool):
    """Revalidate protection and provide a bounded, unnamed file for extraction."""
    if type(restricted_approved) is not bool:
        raise ExtractionError('pdf_extraction_approval_required')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        raise ExtractionError('invalid_file') from None
    with os.fdopen(descriptor, 'rb') as source, TemporaryFile() as output:
        result = _run(source.fileno(), password, output=output.fileno(),
            restricted_approved=restricted_approved)
        if not result.encrypted:
            yield WorkingPDF(source.fileno())
        else:
            size = os.fstat(output.fileno()).st_size
            if not 0 < size <= MAX_WORKING_PDF_BYTES:
                raise ExtractionError('too_large')
            yield WorkingPDF(output.fileno())


def _unlock(original, password):
    from pypdf import PasswordType, PdfReader
    from pypdf.constants import UserAccessPermissions

    reader = PdfReader(original, strict=True)
    if not reader.is_encrypted:
        return reader, PDFProtection(False, False, False)
    needs_password = reader.decrypt('') is PasswordType.NOT_DECRYPTED
    if needs_password:
        if not password:
            raise ExtractionError('pdf_password_required')
        if reader.decrypt(password) is PasswordType.NOT_DECRYPTED:
            raise ExtractionError('pdf_password_incorrect')
    permissions = reader.user_access_permissions
    if reader.are_permissions_valid is not True or permissions is None:
        raise ExtractionError('invalid_pdf')
    return reader, PDFProtection(True, not bool(permissions & UserAccessPermissions.EXTRACT),
        needs_password)


def _main():
    import resource

    sys.dont_write_bytecode = True
    arguments = sys.argv[1:]
    normalize = len(arguments) > 1
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (15, 16) if normalize else (4, 5))
    output_limit = MAX_WORKING_PDF_BYTES if normalize else 0
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))
    logging.getLogger('pypdf').setLevel(logging.CRITICAL)
    try:
        password = json.loads(sys.stdin.buffer.read(8193))
        source = int(arguments[0])
        _check_source(source)
        with WorkingPDF(source).open('rb') as original:
            reader, result = _unlock(original, password)
            if normalize and result.encrypted:
                if result.restricted and arguments[2:] != ['approved']:
                    raise ExtractionError('pdf_extraction_approval_required')
                if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
                    raise ExtractionError('too_large')
                # The parent owns the anonymous output. A child crash leaves
                # neither a named decrypted copy nor a partial parser input.
                from pypdf import PdfWriter

                with os.fdopen(int(arguments[1]), 'wb') as output:
                    PdfWriter(clone_from=reader).write(output)
        print(json.dumps(vars(result)))
    except ExtractionError as error:
        print(json.dumps({'error': error.code}))
    except MemoryError:
        print(json.dumps({'error': 'resource_limit'}))
    except OSError as error:
        code = 'too_large' if error.errno == errno.EFBIG else 'parser_failed'
        print(json.dumps({'error': code}))
    except Exception:
        print(json.dumps({'error': 'invalid_pdf'}))


if __name__ == '__main__':
    from czero_core.protected_pdf import _main as parser_main
    parser_main()
