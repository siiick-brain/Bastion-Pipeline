"""Fetches GitHub's real OIDC discovery document and JWKS.

Run: pytest tests/integration -m network
"""

from __future__ import annotations

import pytest

from scripts.oidc import verifier as v

pytestmark = pytest.mark.network


def test_real_github_jwks_loads_and_unknown_kid_is_rejected() -> None:
    cache = v.JwksCache()
    with pytest.raises(v.VerificationError, match="unknown signing key"):
        cache.key_for("definitely-not-a-github-kid")
    assert cache._keys, "GitHub JWKS returned no RSA signing keys"
