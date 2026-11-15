"""OIDC verifier tests with generated RSA keys and a fake JWKS endpoint.

These tokens are generated locally and are never real GitHub tokens. The hosted run in
.github/workflows/oidc-demo.yml verifies a real GitHub-issued token separately.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import RSAAlgorithm

from scripts.oidc import verifier as v

ISS = v.GITHUB_ISSUER
WORKFLOW = "siiick-brain/Bastion-Pipeline/.github/workflows/"
POLICY = v.Policy(
    audience="bastion-pipeline-demo",
    repository="siiick-brain/Bastion-Pipeline",
    repository_owner="siiick-brain",
    refs=("refs/heads/main",),
    environments=("oidc-demo",),
    event_names=("push", "workflow_dispatch"),
    job_workflow_ref_prefix="siiick-brain/Bastion-Pipeline/.github/workflows/oidc-demo.yml@",
)


def _rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY_A, KEY_B, ATTACKER = _rsa(), _rsa(), _rsa()


def _jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


class FakeIssuer:
    def __init__(self, keys: dict[str, rsa.RSAPrivateKey]) -> None:
        self.keys = keys
        self.calls: list[str] = []
        self.discovery: dict[str, Any] = {"issuer": ISS, "jwks_uri": f"{ISS}/.well-known/jwks"}

    def __call__(self, url: str) -> dict[str, Any]:
        self.calls.append(url)
        if url.endswith("openid-configuration"):
            return self.discovery
        return {"keys": [_jwk(k, kid) for kid, k in self.keys.items()]}


def _claims(**over: Any) -> dict[str, Any]:
    now = int(time.time())
    base = {
        "iss": ISS,
        "aud": "bastion-pipeline-demo",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "sub": "repo:siiick-brain/Bastion-Pipeline:environment:oidc-demo",
        "repository": "siiick-brain/Bastion-Pipeline",
        "repository_owner": "siiick-brain",
        "repository_id": "123456789",
        "ref": "refs/heads/main",
        "environment": "oidc-demo",
        "event_name": "push",
        "job_workflow_ref": WORKFLOW + "oidc-demo.yml@refs/heads/main",
        "jti": "abcdef-0123",
    }
    base.update(over)
    return {k: val for k, val in base.items() if val is not None}


def _token(
    claims: dict[str, Any], key: Any = KEY_A, kid: str | None = "kid-a", alg: str = "RS256"
) -> str:
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


@pytest.fixture
def issuer() -> FakeIssuer:
    return FakeIssuer({"kid-a": KEY_A})


@pytest.fixture
def cache(issuer: FakeIssuer) -> v.JwksCache:
    return v.JwksCache(fetch=issuer)


def test_valid_token_is_accepted(cache: v.JwksCache) -> None:
    claims = v.verify_token(_token(_claims()), POLICY, cache)
    assert claims["repository"] == "siiick-brain/Bastion-Pipeline"


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"aud": "sts.amazonaws.com"}, "audience"),
        ({"aud": ["bastion-pipeline-demo", "other"]}, "audience"),
        ({"iss": "https://evil.example"}, "issuer"),
        # Time claims are offsets from the moment the test runs, never from collection time.
        ({"exp": -120, "iat": -400, "nbf": -400, "_relative": True}, "expired"),
        ({"nbf": 600, "_relative": True}, "not yet valid"),
        (
            {"iat": 600, "exp": 900, "_relative": True},
            "issued in the future|not yet valid|ImmatureSignature",
        ),
        ({"exp": 7200, "_relative": True}, "lifetime"),
        ({"repository": "attacker/Bastion-Pipeline"}, "repository"),
        ({"repository_owner": "attacker"}, "owner"),
        ({"ref": "refs/heads/feature"}, "ref"),
        ({"ref": "refs/pull/1/merge"}, "ref"),
        ({"environment": "production"}, "environment"),
        ({"environment": None}, "environment"),
        ({"event_name": "pull_request"}, "event"),
        (
            {"job_workflow_ref": WORKFLOW + "ci.yml@refs/heads/main"},
            "job workflow",
        ),
        ({"repository": None}, "missing mandatory"),
        ({"job_workflow_ref": None}, "missing mandatory"),
        ({"exp": None}, "invalid token"),
        ({"sub": None}, "invalid token"),
    ],
)
def test_bad_claims_are_rejected(cache: v.JwksCache, over: dict[str, Any], message: str) -> None:
    if over.pop("_relative", False):
        now = int(time.time())
        over = {k: now + val for k, val in over.items()}
    with pytest.raises(v.VerificationError, match=message):
        v.verify_token(_token(_claims(**over)), POLICY, cache)


def test_bad_signature_is_rejected(cache: v.JwksCache) -> None:
    forged = _token(_claims(), key=ATTACKER, kid="kid-a")
    with pytest.raises(v.VerificationError, match="bad signature"):
        v.verify_token(forged, POLICY, cache)


def test_modified_payload_breaks_signature(cache: v.JwksCache) -> None:
    head, _, sig = _token(_claims()).split(".")
    evil = base64.urlsafe_b64encode(json.dumps(_claims(ref="refs/heads/evil")).encode()).rstrip(
        b"="
    )
    with pytest.raises(v.VerificationError, match="bad signature"):
        v.verify_token(f"{head}.{evil.decode()}.{sig}", POLICY, cache)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: _token(_claims(), key="shared-secret-shared-secret-32by", alg="HS256"),
        lambda: jwt.encode(_claims(), None, algorithm="none", headers={"kid": "kid-a"}),  # type: ignore[arg-type]
        lambda: _token(_claims(), key=ec.generate_private_key(ec.SECP256R1()), alg="ES256"),
        lambda: _token(_claims(), alg="RS512"),
    ],
    ids=["hs256-confusion", "alg-none", "es256", "rs512"],
)
def test_disallowed_algorithms_are_rejected(cache: v.JwksCache, token_factory: Any) -> None:
    with pytest.raises(v.VerificationError, match="not allowed"):
        v.verify_token(token_factory(), POLICY, cache)


@pytest.mark.parametrize(
    "token", ["", "abc", "a.b", "a.b.c.d", "x" * 20000 + ".a.b", "###.###.###"]
)
def test_malformed_tokens_are_rejected(cache: v.JwksCache, token: str) -> None:
    with pytest.raises(v.VerificationError, match="malformed"):
        v.verify_token(token, POLICY, cache)


def test_missing_kid_is_rejected(cache: v.JwksCache) -> None:
    with pytest.raises(v.VerificationError, match="no kid"):
        v.verify_token(_token(_claims(), kid=None), POLICY, cache)


def test_unknown_kid_is_rejected_after_one_refresh(issuer: FakeIssuer, cache: v.JwksCache) -> None:
    with pytest.raises(v.VerificationError, match="unknown signing key"):
        v.verify_token(_token(_claims(), key=ATTACKER, kid="kid-evil"), POLICY, cache)
    calls = len(issuer.calls)
    with pytest.raises(v.VerificationError, match="unknown signing key"):
        v.verify_token(_token(_claims(), key=ATTACKER, kid="kid-evil"), POLICY, cache)
    assert len(issuer.calls) == calls  # rate limited: no second fetch within the window


def test_key_rotation_is_picked_up(issuer: FakeIssuer) -> None:
    clock = [1000.0]
    cache = v.JwksCache(fetch=issuer, clock=lambda: clock[0])
    v.verify_token(_token(_claims()), POLICY, cache)
    issuer.keys = {"kid-b": KEY_B}  # GitHub rotates keys
    clock[0] += v.JWKS_MIN_REFRESH_SECONDS + 1
    assert v.verify_token(_token(_claims(), key=KEY_B, kid="kid-b"), POLICY, cache)
    with pytest.raises(v.VerificationError):
        v.verify_token(_token(_claims()), POLICY, cache)  # retired kid-a now fails after refresh


@pytest.mark.parametrize(
    ("discovery", "message"),
    [
        (
            {"issuer": "https://evil.example", "jwks_uri": f"{ISS}/.well-known/jwks"},
            "issuer mismatch",
        ),
        ({"issuer": ISS, "jwks_uri": "https://evil.example/jwks"}, "not hosted by the issuer"),
    ],
)
def test_discovery_document_is_validated(
    issuer: FakeIssuer, discovery: dict[str, Any], message: str
) -> None:
    issuer.discovery = discovery
    with pytest.raises(v.VerificationError, match=message):
        v.verify_token(_token(_claims()), POLICY, v.JwksCache(fetch=issuer))


def test_empty_jwks_is_rejected() -> None:
    with pytest.raises(v.VerificationError, match="no usable"):
        v.verify_token(_token(_claims()), POLICY, v.JwksCache(fetch=FakeIssuer({})))


def test_masking_hides_identifiers_and_never_includes_token() -> None:
    claims = _claims()
    out = json.dumps(v.masked_claims(claims))
    assert "123456789" not in out
    assert "12*****89" in out
    assert "abcdef-0123" not in out
    assert _token(claims) not in out
    assert "lifetime 300s" in v.lifetime(claims)


def test_policy_file_loads_and_matches_repository() -> None:
    p = v.Policy.load(Path(__file__).with_name("policy.toml"))
    assert p.refs == ("refs/heads/main",)
    assert p.repository == "siiick-brain/Bastion-Pipeline"


def test_incomplete_policy_is_rejected(tmp_path: Path) -> None:
    f = tmp_path / "p.toml"
    f.write_text('audience = "x"\n')
    with pytest.raises(v.VerificationError, match="missing"):
        v.Policy.load(f)


def test_https_only(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(v.VerificationError, match="non-HTTPS"):
        v.https_json("http://token.actions.githubusercontent.com/x")


def test_cli_rejects_without_runtime(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("OIDC_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    policy = Path(__file__).with_name("policy.toml")
    assert v.main(["--policy", str(policy)]) == 1
    assert "REJECTED: not running in GitHub Actions" in capsys.readouterr().out


def test_cli_accepts_and_masks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    issuer = FakeIssuer({"kid-a": KEY_A})
    real_cache = v.JwksCache
    monkeypatch.setattr(v, "JwksCache", lambda: real_cache(fetch=issuer))
    token = _token(_claims())
    monkeypatch.setenv("OIDC_TOKEN", token)
    policy = Path(__file__).with_name("policy.toml")
    assert v.main(["--policy", str(policy)]) == 0
    out = capsys.readouterr().out
    assert "ACCEPTED" in out
    assert token not in out
    assert v.main(["--policy", str(policy), "--audience", "wrong-audience"]) == 1
    assert "REJECTED: audience mismatch" in capsys.readouterr().out
