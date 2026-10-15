import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

SPEC = importlib.util.spec_from_file_location("core_sdist", Path(__file__).parents[2] / "scripts/normalize-core-sdist.py")
SDIST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SDIST)
PREFIX = "czero_core-0.24.1"


def archive(path, *, uid, timestamp, invalid=None):
    with tarfile.open(path, "w:gz") as output:
        for name, content, mode in [(PREFIX, None, 0o775), (PREFIX + "/LICENSE", b"license\n", 0o664),
                                    (PREFIX + "/run", b"#!/bin/sh\n", 0o775)]:
            item = tarfile.TarInfo(name)
            item.uid = item.gid = uid
            item.uname = item.gname = "builder" + str(uid)
            item.mtime = timestamp
            item.pax_headers = {"mtime": str(timestamp), "atime": str(timestamp)}
            item.mode = mode
            item.type = tarfile.DIRTYPE if content is None else tarfile.REGTYPE
            item.size = len(content or b"")
            output.addfile(item, io.BytesIO(content) if content is not None else None)
        if invalid:
            item = tarfile.TarInfo(invalid)
            item.type = tarfile.SYMTYPE
            item.linkname = "/outside"
            output.addfile(item)


def test_normalization_preserves_all_content_and_execution_with_stable_bytes(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    paths = [first / (PREFIX + ".tar.gz"), second / (PREFIX + ".tar.gz")]
    for index, path in enumerate(paths):
        archive(path, uid=1000 + index, timestamp=1700000000.123 + index)
        SDIST.normalize(path, 1600000000)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    with tarfile.open(paths[0]) as result:
        assert result.extractfile(PREFIX + "/LICENSE").read() == b"license\n"
        assert result.extractfile(PREFIX + "/run").read() == b"#!/bin/sh\n"
        assert result.getmember(PREFIX + "/run").mode == 0o755
        assert result.getmember(PREFIX + "/LICENSE").mode == 0o644
        assert all(m.uid == m.gid == 0 and m.mtime == 1600000000 for m in result)
    before = hashlib.sha256(paths[0].read_bytes()).digest()
    SDIST.normalize(paths[0], 1600000000)
    assert hashlib.sha256(paths[0].read_bytes()).digest() == before


@pytest.mark.parametrize("invalid", [PREFIX + "/link", "../outside", "/absolute"])
def test_invalid_generated_archive_preserves_original_on_failure(tmp_path, invalid):
    path = tmp_path / (PREFIX + ".tar.gz")
    archive(path, uid=1000, timestamp=1700000000, invalid=invalid)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        SDIST.normalize(path, 1600000000)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".core-sdist-*"))
