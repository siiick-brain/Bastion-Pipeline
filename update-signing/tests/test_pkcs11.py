"""Runs only inside the update-signing container, against a SoftHSM2 token."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

if not os.environ.get("PKCS11_PIN_FILE"):
    pytest.skip("needs the SoftHSM2 token from init-token.sh", allow_module_level=True)

from bastion_update import crypto
from bastion_update.device import Device, TrustStore, UpdateRejected
from bastion_update.pkcs11_signer import Pkcs11Signer

PIN = Path(os.environ["PKCS11_PIN_FILE"]).read_text().strip()
MODULE = os.environ["PKCS11_MODULE"]
WORK = Path(__file__).resolve().parents[1]


def _signer() -> Pkcs11Signer:
    return Pkcs11Signer(MODULE, "bastion-update", PIN, "update-signing")


def test_private_key_is_non_extractable_and_generated_on_token() -> None:
    attrs = _signer().private_attributes()
    assert attrs == {
        "sensitive": True,
        "extractable": False,
        "never_extractable": True,
        "always_sensitive": True,
        "local": True,
    }


def test_wrong_pin_is_refused() -> None:
    with pytest.raises(Exception):  # noqa: B017, PT011 - PKCS#11 raises PinIncorrect
        Pkcs11Signer(MODULE, "bastion-update", "0" * 32, "update-signing").sign(b"x")


def test_token_signature_verifies_with_exported_public_key() -> None:
    s = _signer()
    sig = s.sign(b"manifest")
    assert crypto.verify(s.public_key(), sig, b"manifest")
    assert not crypto.verify(s.public_key(), sig, b"manifesT")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=WORK,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(WORK)},
    )


def test_cli_build_sign_verify_install_and_downgrade(tmp_path: Path) -> None:
    payload = tmp_path / "fw.bin"
    payload.write_bytes(os.urandom(4096))
    pub = tmp_path / "pub.pem"
    root = tmp_path / "device"
    b = _run(
        "build_update.py",
        "--payload",
        str(payload),
        "--version",
        "2.0.0",
        "--min-version",
        "2.0.0",
        "--out",
        str(tmp_path / "v2"),
        "--export-public-key",
        str(pub),
    )
    assert b.returncode == 0, b.stderr
    assert PIN not in b.stdout + b.stderr
    v = _run(
        "verify_update.py",
        str(tmp_path / "v2"),
        "--trusted-key",
        str(pub),
        "--device-root",
        str(root),
        "--install",
    )
    assert v.returncode == 0, v.stdout
    old = _run(
        "build_update.py",
        "--payload",
        str(payload),
        "--version",
        "1.9.0",
        "--min-version",
        "1.0.0",
        "--out",
        str(tmp_path / "v1"),
    )
    assert old.returncode == 0
    d = _run(
        "verify_update.py",
        str(tmp_path / "v1"),
        "--trusted-key",
        str(pub),
        "--device-root",
        str(root),
        "--install",
    )
    assert d.returncode == 1
    assert "downgrade" in d.stdout


def test_counter_persists_on_mounted_state_volume() -> None:
    """The demo mounts a named volume at /state; a second container run must still refuse 1.0.0."""
    state_root = Path(os.environ.get("STATE_DIR", "/state"))
    if not state_root.exists() or not os.access(state_root, os.W_OK):
        pytest.skip("no writable /state volume mounted")
    trust = TrustStore()
    signer = _signer()
    trust.add(signer.public_key())
    device = Device(state_root / "device", trust)
    from bastion_update.package import build

    run = int(os.environ.get("DEMO_RUN", "1"))
    pkg = state_root / f"pkg-{run}"
    if run == 1:
        build(
            b"v1", pkg, name="bastion-firmware", version="5.0.0", min_version="5.0.0", signer=signer
        )
        device.install(pkg)
        assert device.state().installed_version == "5.0.0"
    else:
        assert device.state().installed_version == "5.0.0", "counter did not persist"
        build(
            b"old",
            pkg,
            name="bastion-firmware",
            version="4.0.0",
            min_version="1.0.0",
            signer=signer,
        )
        with pytest.raises(UpdateRejected, match="downgrade"):
            device.install(pkg)
