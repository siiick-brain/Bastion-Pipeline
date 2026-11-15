"""Signed update verification with software keys. Same verifier code as the PKCS#11 path."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import shutil
from pathlib import Path

import pytest
import verify_update
from bastion_update import crypto
from bastion_update.device import Device, TrustStore, UpdateRejected
from bastion_update.package import MANIFEST, PAYLOAD, SIGNATURE, Manifest, PackageError, build
from cryptography.hazmat.primitives.asymmetric import ec

NOW = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.UTC)
SIGNER = crypto.SoftwareSigner()
OTHER = crypto.SoftwareSigner()


def _pkg(
    tmp: Path,
    version: str = "1.1.0",
    min_version: str = "1.0.0",
    signer: crypto.Signer = SIGNER,
    payload: bytes = b"firmware-bytes",
    name: str = "p",
) -> Path:
    out = tmp / f"{name}-{version}"
    build(
        payload,
        out,
        name="bastion-firmware",
        version=version,
        min_version=min_version,
        signer=signer,
        now=NOW,
    )
    return out


@pytest.fixture
def device(tmp_path: Path) -> Device:
    trust = TrustStore()
    trust.add(SIGNER.public_key())
    return Device(tmp_path / "device", trust)


def test_valid_package_installs_and_advances_counter(tmp_path: Path, device: Device) -> None:
    m = device.install(_pkg(tmp_path), NOW)
    assert m.version == "1.1.0"
    assert device.current() == "1.1.0"
    assert device.state().installed_version == "1.1.0"
    assert device.state().rollback_floor == "1.0.0"
    assert (device.root / "versions/1.1.0/payload.bin").read_bytes() == b"firmware-bytes"
    assert not (device.root / "staging").exists()


def test_tampered_payload_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    (pkg / PAYLOAD).write_bytes(b"firmware-bytez")
    with pytest.raises(UpdateRejected, match="hash mismatch"):
        device.install(pkg, NOW)
    assert device.current() is None


def test_appended_payload_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    with (pkg / PAYLOAD).open("ab") as fh:
        fh.write(b"extra")
    with pytest.raises(UpdateRejected, match="size mismatch"):
        device.verify(pkg, NOW)


def test_unsigned_package_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    (pkg / SIGNATURE).unlink()
    with pytest.raises(UpdateRejected, match=r"missing manifest\.sig"):
        device.verify(pkg, NOW)


def test_invalid_signature_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    raw = bytearray(base64.b64decode((pkg / SIGNATURE).read_text()))
    raw[10] ^= 0xFF
    (pkg / SIGNATURE).write_text(base64.b64encode(bytes(raw)).decode())
    with pytest.raises(UpdateRejected, match="invalid signature"):
        device.verify(pkg, NOW)


@pytest.mark.parametrize("sig", ["!!!not-base64!!!", base64.b64encode(b"short").decode(), ""])
def test_garbage_signature_is_rejected(tmp_path: Path, device: Device, sig: str) -> None:
    pkg = _pkg(tmp_path)
    (pkg / SIGNATURE).write_text(sig)
    with pytest.raises(UpdateRejected):
        device.verify(pkg, NOW)


def test_wrong_key_is_rejected(tmp_path: Path, device: Device) -> None:
    with pytest.raises(UpdateRejected, match="not trusted"):
        device.verify(_pkg(tmp_path, signer=OTHER), NOW)


def test_signature_from_wrong_key_with_trusted_key_id_is_rejected(
    tmp_path: Path, device: Device
) -> None:
    pkg = _pkg(tmp_path)
    forged = OTHER.sign((pkg / MANIFEST).read_bytes())
    (pkg / SIGNATURE).write_text(base64.b64encode(forged).decode())
    with pytest.raises(UpdateRejected, match="invalid signature"):
        device.verify(pkg, NOW)


def test_revoked_key_is_rejected(tmp_path: Path, device: Device) -> None:
    device.trust.revoked.add(crypto.key_id(SIGNER.public_key()))
    with pytest.raises(UpdateRejected, match="revoked"):
        device.verify(_pkg(tmp_path), NOW)


def test_missing_manifest_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    (pkg / MANIFEST).unlink()
    with pytest.raises(UpdateRejected, match=r"missing manifest\.json"):
        device.verify(pkg, NOW)


def test_missing_payload_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    (pkg / PAYLOAD).unlink()
    with pytest.raises(UpdateRejected, match="missing payload"):
        device.verify(pkg, NOW)


def _resign(pkg: Path, data: dict[str, object]) -> None:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    (pkg / MANIFEST).write_bytes(raw)
    (pkg / SIGNATURE).write_text(base64.b64encode(SIGNER.sign(raw)).decode())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(format="other/v9"), "unsupported format"),
        (lambda d: d.pop("expires"), "schema"),
        (lambda d: d.update(extra=1), "schema"),
        (lambda d: d.update(version="1.1"), "invalid version"),
        (lambda d: d.update(version="01.1.0"), "invalid version"),
        (lambda d: d.update(min_version="9.0.0"), "greater than version"),
        (lambda d: d.update(sha256="ABC"), "sha256"),
        (lambda d: d.update(size=-1), "size"),
        (lambda d: d.update(size=True), "size"),
        (lambda d: d.update(name="../evil"), "name"),
        (lambda d: d.update(version=110), "string"),
        (lambda d: d.update(created="yesterday"), "timestamp"),
        (lambda d: d.update(created="2026-11-15T12:00:00"), "timezone"),
        (lambda d: d.update(expires=d["created"]), "not after"),
    ],
)
def test_malformed_manifest_is_rejected(
    tmp_path: Path, device: Device, mutate: object, message: str
) -> None:
    pkg = _pkg(tmp_path)
    data = json.loads((pkg / MANIFEST).read_bytes())
    mutate(data)  # type: ignore[operator]
    _resign(pkg, data)
    with pytest.raises(UpdateRejected, match=message):
        device.verify(pkg, NOW)


@pytest.mark.parametrize(
    "raw", [b"not json", b"[]", b'{"a":1}', b"\xff\xfe", b"{" + b" " * 5000 + b"}"]
)
def test_garbage_manifest_is_rejected(tmp_path: Path, device: Device, raw: bytes) -> None:
    pkg = _pkg(tmp_path)
    (pkg / MANIFEST).write_bytes(raw)
    with pytest.raises(UpdateRejected, match="malformed"):
        device.verify(pkg, NOW)


def test_non_canonical_manifest_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    pretty = json.dumps(json.loads((pkg / MANIFEST).read_bytes()), indent=2).encode()
    (pkg / MANIFEST).write_bytes(pretty)
    (pkg / SIGNATURE).write_text(base64.b64encode(SIGNER.sign(pretty)).decode())
    with pytest.raises(UpdateRejected, match="canonical"):
        device.verify(pkg, NOW)


def test_expired_package_is_rejected(tmp_path: Path, device: Device) -> None:
    with pytest.raises(UpdateRejected, match="expired"):
        device.verify(_pkg(tmp_path), NOW + dt.timedelta(days=91))


def test_future_package_is_rejected(tmp_path: Path, device: Device) -> None:
    with pytest.raises(UpdateRejected, match="future"):
        device.verify(_pkg(tmp_path), NOW - dt.timedelta(hours=1))


def test_downgrade_is_rejected(tmp_path: Path, device: Device) -> None:
    device.install(_pkg(tmp_path, "1.2.0"), NOW)
    with pytest.raises(UpdateRejected, match="downgrade"):
        device.install(_pkg(tmp_path, "1.1.0"), NOW)
    assert device.current() == "1.2.0"


def test_downgrade_below_floor_is_rejected_even_after_state_review(
    tmp_path: Path, device: Device
) -> None:
    device.install(_pkg(tmp_path, "2.0.0", min_version="2.0.0"), NOW)
    with pytest.raises(UpdateRejected, match="rollback floor"):
        device.verify(_pkg(tmp_path, "1.9.9", min_version="1.0.0"), NOW)


def test_repeated_installation_is_rejected(tmp_path: Path, device: Device) -> None:
    pkg = _pkg(tmp_path)
    device.install(pkg, NOW)
    with pytest.raises(UpdateRejected, match="already installed"):
        device.install(pkg, NOW)


def test_counter_persists_across_process_restart(tmp_path: Path, device: Device) -> None:
    device.install(_pkg(tmp_path, "1.5.0", "1.4.0"), NOW)
    fresh = Device(device.root, device.trust)  # simulates a new process or container
    assert fresh.state().installed_version == "1.5.0"
    with pytest.raises(UpdateRejected, match="downgrade"):
        fresh.install(_pkg(tmp_path, "1.4.5"), NOW)


def test_floor_never_decreases(tmp_path: Path, device: Device) -> None:
    device.install(_pkg(tmp_path, "1.5.0", "1.5.0"), NOW)
    device.install(_pkg(tmp_path, "1.6.0", "1.0.0"), NOW)
    assert device.state().rollback_floor == "1.5.0"


@pytest.mark.parametrize(
    "content", ["{not json", '{"installed_version": "x", "rollback_floor": "1.0.0"}', "{}"]
)
def test_corrupt_state_fails_closed(tmp_path: Path, device: Device, content: str) -> None:
    device.root.mkdir(parents=True)
    device.state_path.write_text(content)
    with pytest.raises(UpdateRejected, match="corrupt"):
        device.install(_pkg(tmp_path), NOW)


def test_interrupted_install_leaves_previous_version(
    tmp_path: Path, device: Device, monkeypatch: pytest.MonkeyPatch
) -> None:
    device.install(_pkg(tmp_path, "1.1.0"), NOW)
    real_replace = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith(os.path.join("versions", "1.2.0")):
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="power loss"):
        device.install(_pkg(tmp_path, "1.2.0"), NOW)
    monkeypatch.setattr(os, "replace", real_replace)
    assert device.current() == "1.1.0"
    assert device.state().installed_version == "1.1.0"
    assert not (device.root / "staging").exists()
    # The same package installs cleanly on retry.
    assert device.install(_pkg(tmp_path, "1.2.0", name="retry"), NOW).version == "1.2.0"


def test_state_write_failure_keeps_old_state_file(
    tmp_path: Path, device: Device, monkeypatch: pytest.MonkeyPatch
) -> None:
    device.install(_pkg(tmp_path, "1.1.0"), NOW)
    before = device.state_path.read_bytes()
    real_replace = os.replace

    def flaky(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if str(dst).endswith("state.json"):
            raise OSError("disk full")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(OSError, match="disk full"):
        device.install(_pkg(tmp_path, "1.2.0"), NOW)
    monkeypatch.setattr(os, "replace", real_replace)
    assert device.state_path.read_bytes() == before
    assert not list(device.root.glob(".state.json.*"))
    # The new version must not be active while the counter still allows 1.1.x.
    assert device.current() == "1.1.0"


def test_failed_activation_can_be_retried(
    tmp_path: Path, device: Device, monkeypatch: pytest.MonkeyPatch
) -> None:
    device.install(_pkg(tmp_path, "1.1.0"), NOW)
    real_replace = os.replace

    def flaky(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if os.path.basename(str(dst)) == "current":
            raise OSError("power loss")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(OSError, match="power loss"):
        device.install(_pkg(tmp_path, "1.2.0"), NOW)
    monkeypatch.setattr(os, "replace", real_replace)
    with pytest.raises(UpdateRejected):
        device.install(_pkg(tmp_path, "1.1.5"), NOW)
    assert device.install(_pkg(tmp_path, "1.2.0", name="retry"), NOW).version == "1.2.0"
    assert device.current() == "1.2.0"


def test_package_swapped_during_install_is_rejected(
    tmp_path: Path, device: Device, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = _pkg(tmp_path)
    real_copy = shutil.copy2

    def swap(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> object:
        result = real_copy(src, dst)
        if str(dst).endswith(PAYLOAD):
            Path(dst).write_bytes(b"swapped!!!!!!!")
        return result

    monkeypatch.setattr(shutil, "copy2", swap)
    with pytest.raises(UpdateRejected, match="hash mismatch"):
        device.install(pkg, NOW)
    assert device.current() is None


def test_build_refuses_invalid_manifest(tmp_path: Path) -> None:
    with pytest.raises(PackageError):
        build(
            b"x",
            tmp_path / "o",
            name="Bad Name",
            version="1.0.0",
            min_version="1.0.0",
            signer=SIGNER,
            now=NOW,
        )


def test_crypto_helpers() -> None:
    assert not crypto.verify(SIGNER.public_key(), b"\x00" * 63, b"x")
    pem = crypto.public_pem(SIGNER.public_key())
    assert crypto.key_id(crypto.load_public_key(pem)) == crypto.key_id(SIGNER.public_key())
    p384 = crypto.public_pem(ec.generate_private_key(ec.SECP384R1()).public_key())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="P-256"):
        crypto.load_public_key(p384)
    with pytest.raises(ValueError, match="64 bytes"):
        crypto.raw_to_der(b"x")


def test_manifest_round_trip(tmp_path: Path) -> None:
    m = Manifest.parse((_pkg(tmp_path) / MANIFEST).read_bytes())
    assert m.version == "1.1.0"


def test_cli_verify_install_and_reject(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pub = tmp_path / "pub.pem"
    pub.write_bytes(crypto.public_pem(SIGNER.public_key()))
    pkg = tmp_path / "cli-pkg"
    build(
        b"payload",
        pkg,
        name="bastion-firmware",
        version="3.0.0",
        min_version="3.0.0",
        signer=SIGNER,
    )
    root = tmp_path / "dev"
    assert (
        verify_update.main([str(pkg), "--trusted-key", str(pub), "--device-root", str(root)]) == 0
    )
    assert (
        verify_update.main(
            [str(pkg), "--trusted-key", str(pub), "--device-root", str(root), "--install"]
        )
        == 0
    )
    assert "INSTALLED" in capsys.readouterr().out
    assert (
        verify_update.main(
            [str(pkg), "--trusted-key", str(pub), "--device-root", str(root), "--install"]
        )
        == 1
    )
    kid = crypto.key_id(SIGNER.public_key())
    assert (
        verify_update.main(
            [
                str(pkg),
                "--trusted-key",
                str(pub),
                "--revoked-key-id",
                kid,
                "--device-root",
                str(root),
            ]
        )
        == 1
    )
    assert verify_update.main([str(pkg), "--trusted-key", str(tmp_path / "none.pem")]) == 2
