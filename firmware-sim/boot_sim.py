"""Secure boot SIMULATION. This is not real secure boot and runs no firmware.

It models the decisions a boot ROM makes so they can be tested:

  ROM (immutable)      holds the SHA-256 of the root public key, as if fused into OTP
  Fuses (one-way)      security version counter and revoked key ids; values only ever increase
  Key certificate      the root key signs an intermediate signing key (role, key id, not_after)
  Image                the intermediate key signs the image header (version, security_version,
                       sha256, size); the header hash binds the payload
  Measured boot        each verified stage is extended into a PCR-like register and logged

Ed25519 is used for brevity. Every failure stops the boot (fail closed).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class BootError(Exception):
    """Boot refused. The message names the failed check."""


def _raw(pub: Ed25519PublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(pub: Ed25519PublicKey) -> str:
    return hashlib.sha256(_raw(pub)).hexdigest()


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


@dataclass
class Fuses:
    security_version: int = 0
    revoked_key_ids: set[str] = field(default_factory=set)

    def advance(self, version: int) -> None:
        self.security_version = max(self.security_version, version)  # never decreases

    def revoke(self, kid: str) -> None:
        self.revoked_key_ids.add(kid)  # never removed


@dataclass(frozen=True)
class Rom:
    root_key_hash: str


@dataclass
class MeasuredBoot:
    pcr: bytes = b"\x00" * 32
    log: list[tuple[str, str]] = field(default_factory=list)

    def extend(self, label: str, data: bytes) -> None:
        digest = hashlib.sha256(data).digest()
        self.pcr = hashlib.sha256(self.pcr + digest).digest()
        self.log.append((label, digest.hex()))


def issue_key_certificate(
    root: Ed25519PrivateKey, signing_pub: Ed25519PublicKey, not_after: dt.datetime
) -> dict[str, str]:
    body = {
        "role": "image-signing",
        "key": _b64(_raw(signing_pub)),
        "key_id": key_id(signing_pub),
        "issuer_key": _b64(_raw(root.public_key())),
        "not_after": not_after.isoformat(),
    }
    return {"body": _canonical(body).decode(), "sig": _b64(root.sign(_canonical(body)))}


def sign_image(
    signer: Ed25519PrivateKey, payload: bytes, version: int, security_version: int
) -> dict[str, Any]:
    header = {
        "version": version,
        "security_version": security_version,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "signer": key_id(signer.public_key()),
    }
    return {
        "header": _canonical(header).decode(),
        "sig": _b64(signer.sign(_canonical(header))),
        "payload": payload,
    }


def _verify(pub: Ed25519PublicKey, sig_b64: str, data: bytes, what: str) -> None:
    try:
        pub.verify(base64.b64decode(sig_b64, validate=True), data)
    except (InvalidSignature, ValueError) as exc:
        raise BootError(f"{what}: bad signature") from exc


def boot(
    rom: Rom,
    fuses: Fuses,
    cert: dict[str, str] | None,
    image: dict[str, Any] | None,
    now: dt.datetime,
    commit: bool = False,
) -> MeasuredBoot:
    """Runs the boot checks. With commit=True a successful boot advances the security fuse."""
    mb = MeasuredBoot()
    if not cert or "body" not in cert or "sig" not in cert:
        raise BootError("key certificate missing")
    if not image or "header" not in image or "sig" not in image:
        raise BootError("image is unsigned")

    body = json.loads(cert["body"])
    root_pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(body["issuer_key"]))
    if key_id(root_pub) != rom.root_key_hash:
        raise BootError("wrong chain: certificate issuer is not the ROM root key")
    _verify(root_pub, cert["sig"], cert["body"].encode(), "key certificate")
    if body.get("role") != "image-signing":
        raise BootError("key certificate role is not image-signing")
    if dt.datetime.fromisoformat(body["not_after"]) < now:
        raise BootError("key certificate expired")
    signing_pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(body["key"]))
    if key_id(signing_pub) != body["key_id"]:
        raise BootError("key certificate key_id mismatch")
    if body["key_id"] in fuses.revoked_key_ids:
        raise BootError("signing key revoked")
    mb.extend("key-certificate", cert["body"].encode())

    header = json.loads(image["header"])
    if header.get("signer") != body["key_id"]:
        raise BootError("image signer does not match certified key")
    _verify(signing_pub, image["sig"], image["header"].encode(), "image header")
    payload: bytes = image.get("payload", b"")
    if len(payload) != header["size"] or hashlib.sha256(payload).hexdigest() != header["sha256"]:
        raise BootError("image payload does not match signed header (tampered)")
    if header["security_version"] < fuses.security_version:
        raise BootError(
            f"downgrade: security_version {header['security_version']}"
            f" < fuse {fuses.security_version}"
        )
    mb.extend("image", payload)
    if commit:
        fuses.advance(header["security_version"])
    return mb


def demo() -> int:  # pragma: no cover - console demonstration only
    """Prints the six scenarios. Run: python firmware-sim/boot_sim.py"""
    now = dt.datetime.now(dt.UTC)
    root, other_root, signing = (Ed25519PrivateKey.generate() for _ in range(3))
    rom, fuses = Rom(key_id(root.public_key())), Fuses(security_version=2)
    cert = issue_key_certificate(root, signing.public_key(), now + dt.timedelta(days=365))
    good = sign_image(signing, b"firmware v3", version=3, security_version=3)
    tampered = {**good, "payload": b"firmware v3!"}
    old = sign_image(signing, b"firmware v1", version=1, security_version=1)
    wrong = issue_key_certificate(other_root, signing.public_key(), now + dt.timedelta(days=365))
    cases: list[tuple[str, dict[str, str] | None, dict[str, Any] | None, Fuses]] = [
        ("valid image", cert, good, fuses),
        ("tampered payload", cert, tampered, fuses),
        ("unsigned image", cert, {"payload": b"x"}, fuses),
        ("downgraded image", cert, old, fuses),
        ("revoked key", cert, good, Fuses(2, {key_id(signing.public_key())})),
        ("wrong chain", wrong, good, fuses),
    ]
    print("SIMULATION ONLY: not real secure boot.")
    for name, c, img, f in cases:
        try:
            mb = boot(rom, f, c, img, now)
            print(f"ACCEPT  {name:18} PCR={mb.pcr.hex()[:16]}...")
        except BootError as exc:
            print(f"REJECT  {name:18} {exc}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(demo())
