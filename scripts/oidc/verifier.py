"""Verifies a GitHub Actions OIDC token the way a cloud provider's trust policy would.

Checks, in order:
  1. Header: algorithm in an explicit allowlist (RS256), `kid` present.
  2. Key: `kid` resolved against GitHub's JWKS from the OIDC discovery document. An unknown
     `kid` triggers at most one JWKS refresh (key rotation), rate limited.
  3. Signature, issuer (exact), audience (exact), exp, nbf and iat with small leeway, and a
     maximum token lifetime.
  4. Mandatory claims present, then policy claims (repository, owner, ref, environment,
     event, job workflow ref) compared against a TOML policy file.

The raw token is never printed or logged. Identifiers in printed claims are masked.

CLI:
  python -m scripts.oidc.verifier --policy scripts/oidc/policy.toml [--token-env OIDC_TOKEN]
  With no token variable set, requests a token from the Actions runtime (needs id-token: write).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
from jwt.algorithms import RSAAlgorithm

GITHUB_ISSUER = "https://token.actions.githubusercontent.com"
ALLOWED_ALGORITHMS = ("RS256",)
LEEWAY_SECONDS = 30
MAX_LIFETIME_SECONDS = 60 * 60
JWKS_MIN_REFRESH_SECONDS = 60
MANDATORY_CLAIMS = (
    "iss",
    "aud",
    "exp",
    "iat",
    "nbf",
    "sub",
    "repository",
    "repository_owner",
    "ref",
    "job_workflow_ref",
    "event_name",
)

Fetcher = Callable[[str], dict[str, Any]]


class VerificationError(Exception):
    """The token or its claims were rejected. The message never contains the token."""


def https_json(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise VerificationError(f"refusing non-HTTPS URL {parsed.scheme}://{parsed.netloc}")
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - scheme checked
        data: dict[str, Any] = json.load(resp)
        return data


@dataclass
class JwksCache:
    """Resolves signing keys from the issuer's discovery document with rotation handling."""

    issuer: str = GITHUB_ISSUER
    fetch: Fetcher = https_json
    clock: Callable[[], float] = time.monotonic
    _keys: dict[str, Any] = field(default_factory=dict)
    _last_fetch: float | None = None

    def _refresh(self) -> None:
        discovery = self.fetch(f"{self.issuer}/.well-known/openid-configuration")
        if discovery.get("issuer") != self.issuer:
            raise VerificationError("discovery document issuer mismatch")
        jwks_uri = str(discovery.get("jwks_uri", ""))
        if not jwks_uri.startswith(self.issuer + "/"):
            raise VerificationError("jwks_uri is not hosted by the issuer")
        jwks = self.fetch(jwks_uri)
        keys: dict[str, Any] = {}
        for jwk in jwks.get("keys", []):
            if jwk.get("kty") == "RSA" and jwk.get("kid") and jwk.get("use", "sig") == "sig":
                keys[jwk["kid"]] = RSAAlgorithm.from_jwk(json.dumps(jwk))
        if not keys:
            raise VerificationError("JWKS contains no usable RSA signing keys")
        self._keys = keys
        self._last_fetch = self.clock()

    def key_for(self, kid: str) -> Any:
        if kid not in self._keys:
            recently = (
                self._last_fetch is not None
                and self.clock() - self._last_fetch < JWKS_MIN_REFRESH_SECONDS
            )
            if not recently:
                self._refresh()
        if kid not in self._keys:
            raise VerificationError("unknown signing key id")
        return self._keys[kid]


@dataclass(frozen=True)
class Policy:
    audience: str
    repository: str
    repository_owner: str
    refs: tuple[str, ...]
    environments: tuple[str, ...] = ()
    event_names: tuple[str, ...] = ()
    job_workflow_ref_prefix: str = ""

    @classmethod
    def load(cls, path: Path) -> Policy:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
        try:
            return cls(
                audience=raw["audience"],
                repository=raw["repository"],
                repository_owner=raw["repository_owner"],
                refs=tuple(raw["refs"]),
                environments=tuple(raw.get("environments", ())),
                event_names=tuple(raw.get("event_names", ())),
                job_workflow_ref_prefix=raw.get("job_workflow_ref_prefix", ""),
            )
        except KeyError as exc:
            raise VerificationError(f"policy is missing {exc.args[0]}") from exc


def verify_token(token: str, policy: Policy, keys: JwksCache) -> dict[str, Any]:
    """Returns the verified claims or raises VerificationError."""
    if not isinstance(token, str) or token.count(".") != 2 or len(token) > 16_384:
        raise VerificationError("malformed token")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise VerificationError("malformed token header") from exc
    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        raise VerificationError(f"algorithm {alg!r} is not allowed")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise VerificationError("token header has no kid")
    key = keys.key_for(kid)

    current = time.time()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key=key,
            algorithms=list(ALLOWED_ALGORITHMS),
            audience=policy.audience,
            issuer=keys.issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise VerificationError("token expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise VerificationError("token not yet valid") from exc
    except jwt.InvalidAudienceError as exc:
        raise VerificationError("audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise VerificationError("issuer mismatch") from exc
    except jwt.InvalidSignatureError as exc:
        raise VerificationError("bad signature") from exc
    except jwt.PyJWTError as exc:
        raise VerificationError(f"invalid token: {type(exc).__name__}") from exc

    if claims.get("aud") != policy.audience:  # exact string, not a list containing it
        raise VerificationError("audience mismatch")
    if claims["iat"] > current + LEEWAY_SECONDS:
        raise VerificationError("token issued in the future")
    if claims["exp"] - claims["iat"] > MAX_LIFETIME_SECONDS:
        raise VerificationError("token lifetime exceeds policy maximum")
    check_policy(claims, policy)
    return claims


def check_policy(claims: Mapping[str, Any], policy: Policy) -> None:
    missing = [c for c in MANDATORY_CLAIMS if c not in claims]
    if missing:
        raise VerificationError(f"missing mandatory claims: {', '.join(missing)}")
    if claims["repository"] != policy.repository:
        raise VerificationError("repository not allowed by policy")
    if claims["repository_owner"] != policy.repository_owner:
        raise VerificationError("repository owner not allowed by policy")
    if claims["ref"] not in policy.refs:
        raise VerificationError(f"ref {claims['ref']!r} not allowed by policy")
    if policy.environments and claims.get("environment") not in policy.environments:
        raise VerificationError("environment not allowed by policy")
    if policy.event_names and claims["event_name"] not in policy.event_names:
        raise VerificationError("event not allowed by policy")
    if policy.job_workflow_ref_prefix and not str(claims["job_workflow_ref"]).startswith(
        policy.job_workflow_ref_prefix
    ):
        raise VerificationError("job workflow not allowed by policy")


MASKED = {"repository_id", "repository_owner_id", "actor_id", "run_id", "jti", "sub", "actor"}


def masked_claims(claims: Mapping[str, Any]) -> dict[str, Any]:
    """Claims safe to print: identifiers keep only their first and last two characters."""
    out: dict[str, Any] = {}
    for k, v in sorted(claims.items()):
        s = str(v)
        out[k] = (s[:2] + "*" * max(len(s) - 4, 3) + s[-2:]) if k in MASKED else v
    return out


def lifetime(claims: Mapping[str, Any]) -> str:
    iat = dt.datetime.fromtimestamp(claims["iat"], dt.UTC)
    exp = dt.datetime.fromtimestamp(claims["exp"], dt.UTC)
    seconds = int((exp - iat).total_seconds())
    return f"issued {iat.isoformat()} expires {exp.isoformat()} lifetime {seconds}s"


def request_actions_token(audience: str) -> str:
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not bearer:
        raise VerificationError("not running in GitHub Actions with id-token: write")
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(  # noqa: S310
        f"{url}{sep}audience={urllib.parse.quote(audience)}",
        headers={"Authorization": f"bearer {bearer}"},
    )
    if not req.full_url.startswith("https://"):
        raise VerificationError("token request URL is not HTTPS")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        value = json.load(resp).get("value")
    if not isinstance(value, str):
        raise VerificationError("Actions runtime returned no token")
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a GitHub Actions OIDC token")
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--token-env", default="OIDC_TOKEN")
    ap.add_argument("--audience", help="override the policy audience (negative tests)")
    args = ap.parse_args(argv)
    try:
        policy = Policy.load(args.policy)
        request_aud = policy.audience
        if args.audience:
            policy = Policy(**{**policy.__dict__, "audience": args.audience})
        token = os.environ.get(args.token_env) or request_actions_token(request_aud)
        claims = verify_token(token, policy, JwksCache())
    except VerificationError as exc:
        print(f"REJECTED: {exc}")
        return 1
    print("ACCEPTED")
    print(lifetime(claims))
    print(json.dumps(masked_claims(claims), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
