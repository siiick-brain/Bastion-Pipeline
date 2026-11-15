"""Update package format.

A package is a directory with three files:
  payload.bin     the update content
  manifest.json   canonical JSON (sorted keys, no whitespace), see FIELDS
  manifest.sig    base64 raw r||s ECDSA P-256 SHA-256 signature over manifest.json bytes
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from bastion_update.crypto import Signer, key_id

FORMAT = "bastion-update/v1"
PAYLOAD, MANIFEST, SIGNATURE = "payload.bin", "manifest.json", "manifest.sig"
FIELDS = {
    "format",
    "name",
    "version",
    "min_version",
    "sha256",
    "size",
    "key_id",
    "created",
    "expires",
}
SEMVER = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")
MAX_PAYLOAD = 64 * 1024 * 1024
MAX_MANIFEST = 4096


class PackageError(ValueError):
    """The package or manifest is malformed."""


def parse_version(v: str) -> tuple[int, int, int]:
    m = SEMVER.match(v)
    if not m:
        raise PackageError(f"invalid version {v!r}")
    return int(m[1]), int(m[2]), int(m[3])


def _ts(value: str, field: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise PackageError(f"invalid {field} timestamp") from exc
    if parsed.tzinfo is None:
        raise PackageError(f"{field} must include a timezone")
    return parsed


@dataclass(frozen=True)
class Manifest:
    format: str
    name: str
    version: str
    min_version: str
    sha256: str
    size: int
    key_id: str
    created: str
    expires: str

    def canonical(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()

    @property
    def created_at(self) -> dt.datetime:
        return _ts(self.created, "created")

    @property
    def expires_at(self) -> dt.datetime:
        return _ts(self.expires, "expires")

    @classmethod
    def parse(cls, raw: bytes) -> Manifest:
        if len(raw) > MAX_MANIFEST:
            raise PackageError("manifest too large")
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PackageError("manifest is not valid JSON") from exc
        if not isinstance(data, dict) or set(data) != FIELDS:
            raise PackageError("manifest fields do not match the v1 schema")
        if data["format"] != FORMAT:
            raise PackageError(f"unsupported format {data['format']!r}")
        for f in FIELDS - {"size"}:
            if not isinstance(data[f], str):
                raise PackageError(f"{f} must be a string")
        if not isinstance(data["size"], int) or isinstance(data["size"], bool):
            raise PackageError("size must be an integer")
        if not 0 <= data["size"] <= MAX_PAYLOAD:
            raise PackageError("size out of range")
        if not re.fullmatch(r"[0-9a-f]{64}", data["sha256"]):
            raise PackageError("sha256 must be 64 lowercase hex characters")
        if not re.fullmatch(r"[0-9a-f]{64}", data["key_id"]):
            raise PackageError("key_id must be 64 lowercase hex characters")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", data["name"]):
            raise PackageError("invalid name")
        m = cls(**data)
        if parse_version(m.min_version) > parse_version(m.version):
            raise PackageError("min_version is greater than version")
        if m.expires_at <= m.created_at:
            raise PackageError("expires is not after created")
        if m.canonical() != raw:
            raise PackageError("manifest is not in canonical form")
        return m


def build(
    payload: bytes,
    out_dir: Path,
    *,
    name: str,
    version: str,
    min_version: str,
    signer: Signer,
    now: dt.datetime | None = None,
    lifetime: dt.timedelta = dt.timedelta(days=90),
) -> Manifest:
    """Writes payload, canonical manifest and signature into out_dir."""
    now = now or dt.datetime.now(dt.UTC)
    manifest = Manifest(
        format=FORMAT,
        name=name,
        version=version,
        min_version=min_version,
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
        key_id=key_id(signer.public_key()),
        created=now.replace(microsecond=0).isoformat(),
        expires=(now + lifetime).replace(microsecond=0).isoformat(),
    )
    canonical = manifest.canonical()
    Manifest.parse(canonical)  # refuse to sign anything the verifier would reject
    signature = signer.sign(canonical)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / PAYLOAD).write_bytes(payload)
    (out_dir / MANIFEST).write_bytes(canonical)
    (out_dir / SIGNATURE).write_text(base64.b64encode(signature).decode() + "\n")
    return manifest
