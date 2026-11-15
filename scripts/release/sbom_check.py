"""Semantic checks for CycloneDX and SPDX SBOMs produced by Syft for one image digest.

Schema validation is done separately with cyclonedx-cli in CI. This module checks what a schema
cannot: that the SBOM describes the exact artifact digest and is not empty.

Usage: python -m scripts.release.sbom_check <cyclonedx.json> <spdx.json> <sha256:digest>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SbomError(ValueError):
    """The SBOM is invalid or does not describe the expected artifact."""


def _contains(obj: Any, needle: str) -> bool:
    return needle in json.dumps(obj)


def check_cyclonedx(doc: dict[str, Any], digest: str) -> int:
    if doc.get("bomFormat") != "CycloneDX":
        raise SbomError("CycloneDX: bomFormat is not CycloneDX")
    major, minor = (int(x) for x in str(doc.get("specVersion", "0.0")).split(".")[:2])
    if (major, minor) < (1, 5):
        raise SbomError(f"CycloneDX: specVersion {doc.get('specVersion')} is older than 1.5")
    component = doc.get("metadata", {}).get("component")
    if not component:
        raise SbomError("CycloneDX: metadata.component is missing")
    if not _contains(component, digest.removeprefix("sha256:")):
        raise SbomError("CycloneDX: metadata.component does not reference the artifact digest")
    components = doc.get("components") or []
    if not components:
        raise SbomError("CycloneDX: no components")
    return len(components)


def check_spdx(doc: dict[str, Any], digest: str) -> int:
    if doc.get("spdxVersion") not in {"SPDX-2.3", "SPDX-3.0"}:
        raise SbomError(f"SPDX: unsupported spdxVersion {doc.get('spdxVersion')}")
    if not doc.get("documentNamespace", "").startswith(("http://", "https://")):
        raise SbomError("SPDX: documentNamespace missing or not a URI")
    packages = doc.get("packages") or []
    if len(packages) < 2:
        raise SbomError("SPDX: fewer than two packages")
    described = set(doc.get("documentDescribes") or [])
    for rel in doc.get("relationships") or []:
        if rel.get("relationshipType") == "DESCRIBES":
            described.add(rel.get("relatedSpdxElement"))
    roots = [p for p in packages if p.get("SPDXID") in described]
    if not roots or not any(_contains(r, digest.removeprefix("sha256:")) for r in roots):
        raise SbomError("SPDX: described root package does not reference the artifact digest")
    return len(packages)


def check(cdx_path: Path, spdx_path: Path, digest: str) -> dict[str, object]:
    if not DIGEST_RE.match(digest):
        raise SbomError(f"invalid digest {digest!r}")
    cdx = json.loads(cdx_path.read_text(encoding="utf-8"))
    spdx = json.loads(spdx_path.read_text(encoding="utf-8"))
    return {
        "digest": digest,
        "cyclonedx_components": check_cyclonedx(cdx, digest),
        "spdx_packages": check_spdx(spdx, digest),
        "status": "PASS",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        result = check(Path(argv[1]), Path(argv[2]), argv[3])
    except (ValueError, AttributeError, OSError) as exc:  # SbomError, JSON and shape errors
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
