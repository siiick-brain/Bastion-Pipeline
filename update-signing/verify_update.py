"""Verifies an update package and optionally installs it with anti-rollback protection.

Usage:
  python verify_update.py PACKAGE --trusted-key pub.pem [--revoked-key-id HEX ...]
                          [--device-root DIR --install]
Exit codes: 0 accepted, 1 rejected, 2 usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bastion_update.crypto import load_public_key
from bastion_update.device import Device, TrustStore, UpdateRejected


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("package", type=Path)
    ap.add_argument("--trusted-key", type=Path, action="append", required=True)
    ap.add_argument("--revoked-key-id", action="append", default=[])
    ap.add_argument("--device-root", type=Path, default=Path("device"))
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args(argv)

    trust = TrustStore(revoked=set(args.revoked_key_id))
    try:
        for path in args.trusted_key:
            trust.add(load_public_key(path.read_bytes()))
    except (OSError, ValueError) as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    device = Device(args.device_root, trust)
    try:
        m = device.install(args.package) if args.install else device.verify(args.package)
    except UpdateRejected as exc:
        print(f"REJECTED: {exc}")
        return 1
    action = "INSTALLED" if args.install else "VERIFIED"
    print(f"{action}: {m.name} {m.version} (rollback floor now {device.state().rollback_floor})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
