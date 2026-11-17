from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from scripts.release import sonar_status

SHA = "a" * 40


def _fetcher(analyses: list[dict[str, Any]], gate: dict[str, Any] | None = None) -> Any:
    def fetch(url: str) -> dict[str, Any]:
        if "/project_analyses/search" in url:
            return {"analyses": analyses}
        assert "analysisId=AN1" in url
        return {"projectStatus": gate or {}}

    return fetch


def test_pass_when_gate_ok_for_the_released_commit() -> None:
    fetch = _fetcher([{"key": "AN1", "revision": SHA}], {"status": "OK", "conditions": []})
    assert sonar_status.status_for("proj", SHA, fetch) == "PASS"


def test_fail_lists_failed_conditions() -> None:
    gate = {
        "status": "ERROR",
        "conditions": [
            {"status": "ERROR", "metricKey": "new_coverage"},
            {"status": "OK", "metricKey": "new_bugs"},
        ],
    }
    fetch = _fetcher([{"key": "AN1", "revision": SHA}], gate)
    assert sonar_status.status_for("proj", SHA, fetch) == "FAIL: new_coverage"


def test_no_analysis_for_the_commit_is_none() -> None:
    fetch = _fetcher([{"key": "OTHER", "revision": "b" * 40}])
    assert sonar_status.status_for("proj", SHA, fetch) is None


def test_project_key_read_from_properties(tmp_path: Path) -> None:
    props = tmp_path / "sonar-project.properties"
    props.write_text("# c\nsonar.organization=o\nsonar.projectKey=o_p\n")
    assert sonar_status.project_key(props) == "o_p"


def test_main_writes_nothing_when_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(url: str) -> dict[str, Any]:
        raise OSError("network down")

    monkeypatch.setattr(sonar_status, "https_json", boom)
    out = tmp_path / "sonarcloud.txt"
    assert sonar_status.main(["--revision", SHA, "--out", str(out)]) == 0
    assert not out.exists()


def test_main_writes_nothing_on_an_unexpected_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sonar_status, "https_json", lambda url: ["not", "an", "object"])
    out = tmp_path / "sonarcloud.txt"
    assert sonar_status.main(["--revision", SHA, "--out", str(out)]) == 0
    assert not out.exists()


def test_main_writes_pass_for_an_analysed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _fetcher([{"key": "AN1", "revision": SHA}], {"status": "OK", "conditions": []})
    monkeypatch.setattr(sonar_status, "https_json", fetch)
    out = tmp_path / "sonarcloud.txt"
    assert sonar_status.main(["--revision", SHA, "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "PASS\n"


def test_main_writes_nothing_when_the_commit_has_no_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sonar_status, "https_json", _fetcher([]))
    out = tmp_path / "sonarcloud.txt"
    assert sonar_status.main(["--revision", SHA, "--out", str(out)]) == 0
    assert not out.exists()


def test_project_key_missing_is_an_error(tmp_path: Path) -> None:
    props = tmp_path / "sonar-project.properties"
    props.write_text("sonar.organization=o\n")
    with pytest.raises(ValueError, match="projectKey"):
        sonar_status.project_key(props)


def test_https_json_refuses_plain_http() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        sonar_status.https_json("http://sonarcloud.io/api")


def test_https_json_reads_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class Reply(io.BytesIO):
        def __enter__(self) -> Reply:
            return self

        def __exit__(self, *exc: object) -> None:
            self.close()

    def fake_urlopen(url: str, timeout: int) -> Reply:
        assert url.startswith("https://")
        assert timeout == 30
        return Reply(b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert sonar_status.https_json("https://sonarcloud.io/api") == {"ok": True}
