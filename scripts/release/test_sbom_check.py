from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.release.sbom_check import SbomError, check, check_cyclonedx, check_spdx, main

HEX = "b" * 64
DIGEST = f"sha256:{HEX}"

CDX: dict[str, Any] = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "metadata": {"component": {"type": "container", "name": "img", "version": DIGEST}},
    "components": [{"name": "fastapi", "version": "0.163.0"}],
}
SPDX: dict[str, Any] = {
    "spdxVersion": "SPDX-2.3",
    "documentNamespace": "https://anchore.com/syft/image/img-1",
    "packages": [
        {"SPDXID": "SPDXRef-DocumentRoot-Image-img", "versionInfo": DIGEST},
        {"SPDXID": "SPDXRef-Package-fastapi", "versionInfo": "0.163.0"},
    ],
    "relationships": [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-DocumentRoot-Image-img",
        }
    ],
}


def test_valid_pair(tmp_path: Path) -> None:
    c, s = tmp_path / "c.json", tmp_path / "s.json"
    c.write_text(json.dumps(CDX))
    s.write_text(json.dumps(SPDX))
    assert check(c, s, DIGEST)["status"] == "PASS"
    assert main(["x", str(c), str(s), DIGEST]) == 0
    assert main(["x", str(c), str(s), "sha256:" + "c" * 64]) == 1
    assert main(["x"]) == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(bomFormat="SPDX"),
        lambda d: d.update(specVersion="1.4"),
        lambda d: d["metadata"].pop("component"),
        lambda d: d["metadata"]["component"].update(version="sha256:" + "0" * 64),
        lambda d: d.update(components=[]),
    ],
)
def test_bad_cyclonedx(mutate: Any) -> None:
    doc = copy.deepcopy(CDX)
    mutate(doc)
    with pytest.raises(SbomError):
        check_cyclonedx(doc, DIGEST)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(spdxVersion="SPDX-2.1"),
        lambda d: d.update(documentNamespace="not-a-uri"),
        lambda d: d.update(packages=d["packages"][:1]),
        lambda d: d.update(relationships=[]),
        lambda d: d["packages"][0].update(versionInfo="sha256:" + "0" * 64),
    ],
)
def test_bad_spdx(mutate: Any) -> None:
    doc = copy.deepcopy(SPDX)
    mutate(doc)
    with pytest.raises(SbomError):
        check_spdx(doc, DIGEST)


def test_rejects_invalid_digest(tmp_path: Path) -> None:
    with pytest.raises(SbomError):
        check(tmp_path / "a", tmp_path / "b", "md5:abc")


@pytest.mark.parametrize("cdx_text", ['{"bomFormat": "CycloneDX", "specVersion": "1"}', "[]"])
def test_cli_reports_fail_for_odd_input(
    tmp_path: Path, cdx_text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "c.json").write_text(cdx_text)
    (tmp_path / "s.json").write_text(json.dumps(SPDX))
    code = main(["x", str(tmp_path / "c.json"), str(tmp_path / "s.json"), DIGEST])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"
