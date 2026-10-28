# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""The installed OAuth dependency must retain the CVE-2026-96760 correction."""
import pytest

from authlib.jose import JsonWebSignature
from authlib.jose.errors import JoseError


def test_signed_json_requires_a_real_signature():
    jws = JsonWebSignature(algorithms=['HS256'])
    key = b'synthetic-fixture-signing-key-at-least-32-bytes'
    signed = jws.serialize_json({'protected': {'alg': 'HS256'}}, b'fixture', key)
    assert jws.deserialize_json(signed, key)['payload'] == b'fixture'
    with pytest.raises(JoseError):
        jws.deserialize_json({'payload': signed['payload'], 'signatures': []}, key)
