#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Normalize generated source-archive metadata without changing package content."""
import argparse
import copy
import gzip
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile


def normalize(path: Path, epoch: int) -> None:
    if not 0 <= epoch <= 0xFFFFFFFF or not re.fullmatch(r"czero_core-[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz", path.name):
        raise ValueError("Invalid Core archive identity or epoch")
    prefix = path.name.removesuffix(".tar.gz")
    descriptor, temporary = tempfile.mkstemp(prefix=".core-sdist-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output, tarfile.open(path, "r:gz") as source:
            members = sorted(source.getmembers(), key=lambda member: member.name)
            names = set()
            for member in members:
                parts = PurePosixPath(member.name).parts
                if (not parts or parts[0] != prefix or ".." in parts or member.name.startswith("/")
                        or member.name in names or not (member.isfile() or member.isdir())):
                    raise ValueError("Invalid generated Core archive member")
                names.add(member.name)
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as destination:
                    for member in members:
                        normalized = copy.copy(member)
                        normalized.uid = normalized.gid = 0
                        normalized.uname = normalized.gname = ""
                        normalized.mtime = epoch
                        normalized.pax_headers = {}
                        normalized.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                        stream = source.extractfile(member) if member.isfile() else None
                        try:
                            destination.addfile(normalized, stream)
                        finally:
                            if stream:
                                stream.close()
            output.flush()
            os.fchmod(output.fileno(), 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        normalize(args.archive, int(os.environ["SOURCE_DATE_EPOCH"]))
    except (ValueError, KeyError, OSError, tarfile.TarError):
        parser.exit(1, "Core source archive normalization failed.\n")
    print("Core source archive metadata normalized")
