"""Real cosign verification: identity, issuer and tamper checks.

Keyless cases use a public image signed by its publisher's GitHub Actions workflow (the
Chainguard base image this project builds on), so they exercise real Sigstore certificates and
the Rekor transparency log. Tamper cases sign a local blob with an ephemeral key pair.

Run: pytest tests/integration -m network
Needs: cosign on PATH (or COSIGN env var) and internet access.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.network

# winget installs the release binary under its asset name.
COSIGN = (
    os.environ.get("COSIGN") or shutil.which("cosign") or shutil.which("cosign-windows-amd64")
)
IMAGE = (
    "cgr.dev/chainguard/python@sha256:"
    "b194f818c3fbf172c83597753e72561f14f58d22e9ea6bf148b7597246f65c8f"
)
IDENTITY = (
    "https://github.com/chainguard-images/images/.github/workflows/release.yaml@refs/heads/main"
)
ISSUER = "https://token.actions.githubusercontent.com"

if COSIGN is None:
    pytest.skip("cosign not available", allow_module_level=True)


def _cosign(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    assert COSIGN is not None
    return subprocess.run(
        [COSIGN, *args],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env={**os.environ, **(env or {})},
    )


def test_keyless_signature_with_expected_identity_and_issuer() -> None:
    r = _cosign(
        "verify", IMAGE, "--certificate-identity", IDENTITY, "--certificate-oidc-issuer", ISSUER
    )
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize(
    ("identity_args", "issuer"),
    [
        (["--certificate-identity", IDENTITY.replace("release.yaml", "evil.yaml")], ISSUER),
        (["--certificate-identity", IDENTITY.replace("refs/heads/main", "refs/heads/dev")], ISSUER),
        (["--certificate-identity", IDENTITY], "https://accounts.google.com"),
        (["--certificate-identity-regexp", r"^https://github\.com/siiick-brain/.*"], ISSUER),
    ],
    ids=["wrong-workflow", "wrong-ref", "wrong-issuer", "wrong-repository"],
)
def test_keyless_signature_rejects_wrong_identity(identity_args: list[str], issuer: str) -> None:
    r = _cosign("verify", IMAGE, *identity_args, "--certificate-oidc-issuer", issuer)
    assert r.returncode != 0


def test_modified_blob_fails_signature(tmp_path: Path) -> None:
    env = {"COSIGN_PASSWORD": "", "COSIGN_YES": "true"}
    gen = subprocess.run(
        [str(COSIGN), "generate-key-pair"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, **env},
    )
    assert gen.returncode == 0, gen.stderr
    blob = tmp_path / "SHA256SUMS"
    blob.write_text("a" * 64 + "  pkg.zip\n")
    key, pub, bundle = tmp_path / "cosign.key", tmp_path / "cosign.pub", tmp_path / "b.bundle"
    signed = _cosign(
        "sign-blob",
        "--key",
        str(key),
        "--use-signing-config=false",
        "--tlog-upload=false",
        "--bundle",
        str(bundle),
        str(blob),
        env=env,
    )
    assert signed.returncode == 0, signed.stderr

    verify = (
        "verify-blob",
        "--key",
        str(pub),
        "--bundle",
        str(bundle),
        "--insecure-ignore-tlog=true",
        str(blob),
    )
    ok = _cosign(*verify)
    assert ok.returncode == 0, ok.stderr

    blob.write_text("b" * 64 + "  pkg.zip\n")
    bad = _cosign(*verify)
    assert bad.returncode != 0
    assert "invalid signature" in bad.stderr
