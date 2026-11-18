"""Boot simulation: accepts one valid image and rejects the five attack cases."""

from __future__ import annotations

import base64
import datetime as dt
import json
from typing import Any

import boot_sim as bs
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

NOW = dt.datetime(2026, 11, 15, tzinfo=dt.UTC)
ROOT, OTHER_ROOT, SIGNING, ROGUE = (Ed25519PrivateKey.generate() for _ in range(4))
ROM = bs.Rom(bs.key_id(ROOT.public_key()))
CERT = bs.issue_key_certificate(ROOT, SIGNING.public_key(), NOW + dt.timedelta(days=365))
GOOD = bs.sign_image(SIGNING, b"firmware v3", version=3, security_version=3)


def fuses() -> bs.Fuses:
    return bs.Fuses(security_version=2)


def test_valid_image_boots_and_is_measured() -> None:
    mb = bs.boot(ROM, fuses(), CERT, GOOD, NOW)
    assert [label for label, _ in mb.log] == ["key-certificate", "image"]
    assert mb.pcr != b"\x00" * 32


def test_measurement_is_deterministic_and_order_sensitive() -> None:
    a = bs.boot(ROM, fuses(), CERT, GOOD, NOW).pcr
    b = bs.boot(ROM, fuses(), CERT, GOOD, NOW).pcr
    assert a == b
    other = bs.boot(ROM, fuses(), CERT, bs.sign_image(SIGNING, b"firmware v4", 4, 3), NOW).pcr
    assert other != a


def test_tampered_image_is_rejected() -> None:
    with pytest.raises(bs.BootError, match="tampered"):
        bs.boot(ROM, fuses(), CERT, {**GOOD, "payload": b"firmware v3!"}, NOW)


def test_tampered_header_is_rejected() -> None:
    header = json.loads(GOOD["header"])
    header["security_version"] = 99
    forged = {**GOOD, "header": json.dumps(header, sort_keys=True, separators=(",", ":"))}
    with pytest.raises(bs.BootError, match="bad signature"):
        bs.boot(ROM, fuses(), CERT, forged, NOW)


@pytest.mark.parametrize("image", [None, {}, {"payload": b"x"}, {"header": "{}", "payload": b"x"}])
def test_unsigned_image_is_rejected(image: dict[str, Any] | None) -> None:
    with pytest.raises(bs.BootError, match="unsigned"):
        bs.boot(ROM, fuses(), CERT, image, NOW)


def test_downgraded_image_is_rejected() -> None:
    old = bs.sign_image(SIGNING, b"firmware v1", version=1, security_version=1)
    with pytest.raises(bs.BootError, match="downgrade"):
        bs.boot(ROM, fuses(), CERT, old, NOW)


def test_commit_advances_fuse_and_blocks_previous_version() -> None:
    f = fuses()
    bs.boot(ROM, f, CERT, GOOD, NOW, commit=True)
    assert f.security_version == 3
    v2 = bs.sign_image(SIGNING, b"firmware v2", version=2, security_version=2)
    with pytest.raises(bs.BootError, match="downgrade"):
        bs.boot(ROM, f, CERT, v2, NOW)
    f.advance(1)
    assert f.security_version == 3  # fuses never go backwards


def test_revoked_key_is_rejected() -> None:
    f = fuses()
    f.revoke(bs.key_id(SIGNING.public_key()))
    with pytest.raises(bs.BootError, match="revoked"):
        bs.boot(ROM, f, CERT, GOOD, NOW)


def test_wrong_chain_is_rejected() -> None:
    wrong = bs.issue_key_certificate(OTHER_ROOT, SIGNING.public_key(), NOW + dt.timedelta(days=365))
    with pytest.raises(bs.BootError, match="wrong chain"):
        bs.boot(ROM, fuses(), wrong, GOOD, NOW)


def test_image_signed_by_uncertified_key_is_rejected() -> None:
    rogue_image = bs.sign_image(ROGUE, b"firmware v3", version=3, security_version=3)
    with pytest.raises(bs.BootError, match="does not match certified key"):
        bs.boot(ROM, fuses(), CERT, rogue_image, NOW)


def test_certificate_issuer_swap_is_rejected() -> None:
    body = json.loads(CERT["body"])
    body["issuer_key"] = base64.b64encode(bs._raw(OTHER_ROOT.public_key())).decode()
    forged = {"body": json.dumps(body, sort_keys=True, separators=(",", ":")), "sig": CERT["sig"]}
    with pytest.raises(bs.BootError, match="wrong chain"):
        bs.boot(ROM, fuses(), forged, GOOD, NOW)


def test_certificate_body_tamper_is_rejected() -> None:
    body = json.loads(CERT["body"])
    body["not_after"] = (NOW + dt.timedelta(days=9999)).isoformat()
    forged = {"body": json.dumps(body, sort_keys=True, separators=(",", ":")), "sig": CERT["sig"]}
    with pytest.raises(bs.BootError, match="key certificate: bad signature"):
        bs.boot(ROM, fuses(), forged, GOOD, NOW)


def test_expired_certificate_is_rejected() -> None:
    old = bs.issue_key_certificate(ROOT, SIGNING.public_key(), NOW - dt.timedelta(days=1))
    with pytest.raises(bs.BootError, match="expired"):
        bs.boot(ROM, fuses(), old, GOOD, NOW)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("role", "debug", "role"), ("key_id", "0" * 64, "key_id mismatch")],
)
def test_certificate_field_checks(field: str, value: str, message: str) -> None:
    body = json.loads(
        bs.issue_key_certificate(ROOT, SIGNING.public_key(), NOW + dt.timedelta(days=1))["body"]
    )
    body[field] = value
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    cert = {"body": raw, "sig": base64.b64encode(ROOT.sign(raw.encode())).decode()}
    with pytest.raises(bs.BootError, match=message):
        bs.boot(ROM, fuses(), cert, GOOD, NOW)


def test_missing_certificate_is_rejected() -> None:
    with pytest.raises(bs.BootError, match="certificate missing"):
        bs.boot(ROM, fuses(), None, GOOD, NOW)


def test_garbage_signature_is_rejected() -> None:
    with pytest.raises(bs.BootError, match="bad signature"):
        bs.boot(ROM, fuses(), CERT, {**GOOD, "sig": "%%%"}, NOW)
