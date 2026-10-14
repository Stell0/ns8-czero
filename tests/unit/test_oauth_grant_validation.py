# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from czero_core.oauth_grants import GrantRejected, OAuthGrantService, pkce_challenge


def test_pkce_uses_s256_rfc7636_test_vector():
    assert pkce_challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk') == 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'


@pytest.mark.parametrize('value', [None, '', 'x' * 42, 'x' * 129, 'é' * 43, 'a/b' * 20, ' ' * 43])
def test_invalid_pkce_is_rejected_without_value_echo(value):
    with pytest.raises(GrantRejected, match='^invalid_grant$'):
        pkce_challenge(value)


@pytest.mark.parametrize('resource', ['http://127.0.0.1/mcp', 'https://host.test/mcp?query=value',
                                    'https://host.test/mcp#fragment', 'https://user@host.test/mcp'])
def test_resource_is_an_exact_configured_https_uri(resource):
    with pytest.raises(ValueError):
        OAuthGrantService(None, 'czero900', resource)
