"""Device side: trust store, persistent anti-rollback state, verification and atomic install.

Install layout under the device root:
  state.json             {"installed_version", "rollback_floor"}; written atomically
  versions/<version>/    installed payloads
  current                text file naming the active version; replaced atomically
  staging/               temporary, removed on success and on failure

Every check fails closed: any error rejects the package and leaves the device unchanged.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from bastion_update import crypto
from bastion_update.package import (
    MANIFEST,
    PAYLOAD,
    SIGNATURE,
    Manifest,
    PackageError,
    parse_version,
)

CLOCK_SKEW = dt.timedelta(minutes=5)


class UpdateRejected(Exception):
    """Verification failed. The device state was not changed."""


@dataclass
class TrustStore:
    keys: dict[str, ec.EllipticCurvePublicKey] = field(default_factory=dict)
    revoked: set[str] = field(default_factory=set)

    def add(self, public_key: ec.EllipticCurvePublicKey) -> str:
        kid = crypto.key_id(public_key)
        self.keys[kid] = public_key
        return kid


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    if hasattr(os, "O_DIRECTORY"):  # make the rename durable on POSIX
        dfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)


@dataclass(frozen=True)
class State:
    installed_version: str = "0.0.0"
    rollback_floor: str = "0.0.0"


class Device:
    def __init__(self, root: Path, trust: TrustStore) -> None:
        self.root = root
        self.trust = trust

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def state(self) -> State:
        if not self.state_path.exists():
            return State()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            s = State(str(data["installed_version"]), str(data["rollback_floor"]))
            parse_version(s.installed_version)
            parse_version(s.rollback_floor)
        except (KeyError, TypeError, ValueError, PackageError) as exc:
            # Corrupt state must not reset the counter to zero: refuse all updates.
            raise UpdateRejected("anti-rollback state is corrupt; refusing updates") from exc
        return s

    def current(self) -> str | None:
        p = self.root / "current"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None

    def verify(self, package: Path, now: dt.datetime | None = None) -> Manifest:
        now = now or dt.datetime.now(dt.UTC)
        try:
            raw_manifest = (package / MANIFEST).read_bytes()
            sig_text = (package / SIGNATURE).read_text(encoding="ascii").strip()
        except FileNotFoundError as exc:
            raise UpdateRejected(f"missing {Path(exc.filename).name}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise UpdateRejected("unreadable package") from exc

        try:
            manifest = Manifest.parse(raw_manifest)
        except PackageError as exc:
            raise UpdateRejected(f"malformed manifest: {exc}") from exc

        if manifest.key_id in self.trust.revoked:
            raise UpdateRejected("signing key is revoked")
        key = self.trust.keys.get(manifest.key_id)
        if key is None:
            raise UpdateRejected("signing key is not trusted")
        try:
            signature = base64.b64decode(sig_text, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise UpdateRejected("signature is not valid base64") from exc
        if not crypto.verify(key, signature, raw_manifest):
            raise UpdateRejected("invalid signature")

        if now > manifest.expires_at:
            raise UpdateRejected("package expired")
        if manifest.created_at > now + CLOCK_SKEW:
            raise UpdateRejected("package created in the future")

        payload_path = package / PAYLOAD
        if not payload_path.is_file():
            raise UpdateRejected("missing payload.bin")
        if payload_path.stat().st_size != manifest.size:
            raise UpdateRejected("payload size mismatch")
        digest = hashlib.sha256()
        with payload_path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        if digest.hexdigest() != manifest.sha256:
            raise UpdateRejected("payload hash mismatch")

        state = self.state()
        v = parse_version(manifest.version)
        if v < parse_version(state.rollback_floor):
            raise UpdateRejected(f"downgrade below rollback floor {state.rollback_floor} refused")
        # Same version: only to finish an interrupted activation.
        if v == parse_version(state.installed_version) and self.current() == manifest.version:
            raise UpdateRejected(f"version {manifest.version} is already installed")
        if v < parse_version(state.installed_version):
            raise UpdateRejected(f"downgrade from {state.installed_version} refused")
        return manifest

    def install(self, package: Path, now: dt.datetime | None = None) -> Manifest:
        """Verifies, stages, re-verifies the staged copy and switches atomically."""
        manifest = self.verify(package, now)
        staging = self.root / "staging"
        shutil.rmtree(staging, ignore_errors=True)
        try:
            staging.mkdir(parents=True)
            for name in (PAYLOAD, MANIFEST, SIGNATURE):
                shutil.copy2(package / name, staging / name)
            # Re-verify the staged copy (TOCTOU).
            if self.verify(staging, now) != manifest:
                raise UpdateRejected("package changed during installation")
            target = self.root / "versions" / manifest.version
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging, target)
            # State before current: a crash in between must not leave a rollback window.
            old = self.state()
            floor = max(parse_version(old.rollback_floor), parse_version(manifest.min_version))
            new_state = {
                "installed_version": manifest.version,
                "rollback_floor": ".".join(map(str, floor)),
            }
            _atomic_write(self.state_path, json.dumps(new_state, sort_keys=True).encode())
            _atomic_write(self.root / "current", manifest.version.encode())
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return manifest
