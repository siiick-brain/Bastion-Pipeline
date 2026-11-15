"""ECDSA P-256 helpers.

Signatures are stored as raw r||s (64 bytes), the PKCS#11 CKM_ECDSA format.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

COORD = 32


class Signer(Protocol):
    def sign(self, data: bytes) -> bytes:
        """Returns a raw r||s ECDSA P-256 SHA-256 signature over data."""
        ...

    def public_key(self) -> ec.EllipticCurvePublicKey: ...


def key_id(public_key: ec.EllipticCurvePublicKey) -> str:
    """SHA-256 of the DER SubjectPublicKeyInfo, hex encoded."""
    der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(der).hexdigest()


def raw_to_der(raw: bytes) -> bytes:
    if len(raw) != 2 * COORD:
        raise ValueError("raw signature must be 64 bytes")
    return encode_dss_signature(
        int.from_bytes(raw[:COORD], "big"), int.from_bytes(raw[COORD:], "big")
    )


def der_to_raw(der: bytes) -> bytes:
    r, s = decode_dss_signature(der)
    return r.to_bytes(COORD, "big") + s.to_bytes(COORD, "big")


def verify(public_key: ec.EllipticCurvePublicKey, raw_sig: bytes, data: bytes) -> bool:
    if not isinstance(public_key.curve, ec.SECP256R1):
        return False
    try:
        public_key.verify(raw_to_der(raw_sig), data, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError):
        return False
    return True


def load_public_key(pem: bytes) -> ec.EllipticCurvePublicKey:
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("expected an EC P-256 public key")
    return key


def public_pem(public_key: ec.EllipticCurvePublicKey) -> bytes:
    return public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


class SoftwareSigner:
    """In-memory key for tests only. Production signing goes through PKCS#11."""

    def __init__(self, private_key: ec.EllipticCurvePrivateKey | None = None) -> None:
        self._key = private_key or ec.generate_private_key(ec.SECP256R1())

    def sign(self, data: bytes) -> bytes:
        return der_to_raw(self._key.sign(data, ec.ECDSA(hashes.SHA256())))

    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._key.public_key()
