"""PKCS#11 signer backed by a token (SoftHSM2 in this project).

The private key is generated on the token as sensitive and non-extractable; only signing
operations cross the PKCS#11 boundary. Exercised by tests/test_pkcs11.py inside the
update-signing container (see update-signing/Dockerfile).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pkcs11
from cryptography.hazmat.primitives.asymmetric import ec
from pkcs11 import Attribute, KeyType, Mechanism, ObjectClass
from pkcs11.util.ec import encode_named_curve_parameters

from bastion_update.crypto import COORD

P256_OID = "secp256r1"


class Pkcs11Signer:
    def __init__(self, module_path: str, token_label: str, pin: str, key_label: str) -> None:
        self._lib = pkcs11.lib(module_path)
        self._token = self._lib.get_token(token_label=token_label)
        self._pin = pin
        self._label = key_label

    def _session(self) -> Any:
        return self._token.open(user_pin=self._pin, rw=True)

    def generate(self) -> None:
        """Creates an EC P-256 key pair on the token. The private key never leaves it."""
        with self._session() as session:
            params = session.create_domain_parameters(
                KeyType.EC,
                {Attribute.EC_PARAMS: encode_named_curve_parameters(P256_OID)},
                local=True,
            )
            params.generate_keypair(
                store=True,
                label=self._label,
                private_template={
                    Attribute.SENSITIVE: True,
                    Attribute.EXTRACTABLE: False,
                    Attribute.SIGN: True,
                    Attribute.TOKEN: True,
                },
                public_template={Attribute.VERIFY: True, Attribute.TOKEN: True},
            )

    def private_attributes(self) -> dict[str, bool]:
        with self._session() as session:
            key = session.get_key(object_class=ObjectClass.PRIVATE_KEY, label=self._label)
            return {
                "sensitive": bool(key[Attribute.SENSITIVE]),
                "extractable": bool(key[Attribute.EXTRACTABLE]),
                "never_extractable": bool(key[Attribute.NEVER_EXTRACTABLE]),
                "always_sensitive": bool(key[Attribute.ALWAYS_SENSITIVE]),
                "local": bool(key[Attribute.LOCAL]),
            }

    def sign(self, data: bytes) -> bytes:
        digest = hashlib.sha256(data).digest()
        with self._session() as session:
            key = session.get_key(object_class=ObjectClass.PRIVATE_KEY, label=self._label)
            raw: bytes = key.sign(digest, mechanism=Mechanism.ECDSA)
        if len(raw) != 2 * COORD:
            raise ValueError("unexpected signature length from token")
        return raw

    def public_key(self) -> ec.EllipticCurvePublicKey:
        with self._session() as session:
            key = session.get_key(object_class=ObjectClass.PUBLIC_KEY, label=self._label)
            point = key[Attribute.EC_POINT]
        # EC_POINT is a DER OCTET STRING wrapping the uncompressed point.
        if point[0] == 0x04 and len(point) == 67:
            point = point[2:]
        return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes(point))
