"""Builds and signs an update package through PKCS#11.

Usage (inside the update-signing container, after init-token.sh):
  python build_update.py --payload firmware.bin --version 1.2.0 --min-version 1.1.0 --out pkg/
Env: PKCS11_MODULE, PKCS11_TOKEN, PKCS11_KEY_LABEL, PKCS11_PIN_FILE (the PIN is read from a
file so it never appears in the process list or the shell history).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from bastion_update.crypto import public_pem
from bastion_update.package import PackageError, build


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--payload", type=Path, required=True)
    ap.add_argument("--name", default="bastion-firmware")
    ap.add_argument("--version", required=True)
    ap.add_argument("--min-version", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--export-public-key", type=Path)
    args = ap.parse_args(argv)

    from bastion_update.pkcs11_signer import Pkcs11Signer

    pin = Path(os.environ["PKCS11_PIN_FILE"]).read_text(encoding="ascii").strip()
    signer = Pkcs11Signer(
        os.environ.get("PKCS11_MODULE", "/usr/lib/softhsm/libsofthsm2.so"),
        os.environ.get("PKCS11_TOKEN", "bastion-update"),
        pin,
        os.environ.get("PKCS11_KEY_LABEL", "update-signing"),
    )
    try:
        m = build(
            args.payload.read_bytes(),
            args.out,
            name=args.name,
            version=args.version,
            min_version=args.min_version,
            signer=signer,
        )
    except PackageError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    if args.export_public_key:
        args.export_public_key.write_bytes(public_pem(signer.public_key()))
    print(f"signed {m.name} {m.version} key_id={m.key_id[:16]}... sha256={m.sha256[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
