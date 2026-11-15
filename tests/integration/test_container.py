"""Runtime checks against the built container image, not the Dockerfile text.

Run: BASTION_IMAGE=bastion-pipeline:local pytest tests/integration -m integration
CI sets BASTION_REQUIRE_DOCKER=1 so a missing Docker daemon fails instead of skipping.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.integration

IMAGE = os.environ.get("BASTION_IMAGE", "bastion-pipeline:local")
NONROOT_UID = "65532"


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=120,
        env={**os.environ, "MSYS_NO_PATHCONV": "1"},
    )


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return _docker("image", "inspect", IMAGE, check=False).returncode == 0


if not _docker_available():
    if os.environ.get("BASTION_REQUIRE_DOCKER") == "1":
        pytest.fail(f"Docker or image {IMAGE} unavailable", pytrace=False)
    pytest.skip(f"Docker or image {IMAGE} unavailable", allow_module_level=True)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def running() -> Iterator[tuple[str, int]]:
    """Start the image with the same restrictions as the Kubernetes pod spec."""
    name = f"bastion-it-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    _docker(
        "run",
        "-d",
        "--name",
        name,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "256m",
        "--pids-limit",
        "128",
        "-p",
        f"127.0.0.1:{port}:8000",
        IMAGE,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        else:
            logs = _docker("logs", name, check=False)
            pytest.fail(f"container never became healthy:\n{logs.stdout}{logs.stderr}")
        yield name, port
    finally:
        _docker("rm", "-f", name, check=False)


def _inspect(name: str) -> dict[str, object]:
    data: list[dict[str, object]] = json.loads(_docker("inspect", name).stdout)
    return data[0]


def test_health_responds_under_read_only_root(running: tuple[str, int]) -> None:
    _, port = running
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
        assert json.loads(r.read()) == {"status": "ok"}
        assert r.headers.get("server") is None


def test_crud_works_in_container(running: tuple[str, int]) -> None:
    _, port = running
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/notes",
        data=json.dumps({"title": "it", "content": "runtime"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
        assert json.loads(r.read())["title"] == "it"


def test_process_runs_as_nonroot_uid(running: tuple[str, int]) -> None:
    name, _ = running
    status = _docker(
        "exec", name, "/usr/bin/python", "-c", "print(open('/proc/1/status').read())"
    ).stdout
    uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
    assert uid_line.split()[1:] == [NONROOT_UID] * 4


def test_effective_capabilities_are_empty(running: tuple[str, int]) -> None:
    name, _ = running
    status = _docker(
        "exec", name, "/usr/bin/python", "-c", "print(open('/proc/1/status').read())"
    ).stdout
    caps = {line.split(":")[0]: line.split()[1] for line in status.splitlines() if "Cap" in line}
    assert caps["CapEff"] == "0000000000000000"
    assert caps["CapBnd"] == "0000000000000000"
    nnp = next(line for line in status.splitlines() if line.startswith("NoNewPrivs:"))
    assert nnp.split()[1] == "1"


def test_root_filesystem_is_not_writable(running: tuple[str, int]) -> None:
    name, _ = running
    result = _docker(
        "exec", name, "/usr/bin/python", "-c", "open('/srv/app/pwned','w')", check=False
    )
    assert result.returncode != 0
    assert "Read-only file system" in result.stderr


def test_application_code_not_owned_by_runtime_user(running: tuple[str, int]) -> None:
    name, _ = running
    out = _docker(
        "exec", name, "/usr/bin/python", "-c", "import os;print(os.stat('/srv/app/main.py').st_uid)"
    ).stdout
    assert out.strip() == "0"


@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/bash", "/busybox/sh"])
def test_no_shell_in_image(shell: str) -> None:
    result = _docker("run", "--rm", "--entrypoint", shell, IMAGE, "-c", "id", check=False)
    assert result.returncode != 0


def test_image_config_is_hardened() -> None:
    cfg = json.loads(_docker("image", "inspect", IMAGE, "--format", "{{json .Config}}").stdout)
    assert cfg["User"] == f"{NONROOT_UID}:{NONROOT_UID}"
    assert not any(k.lower().startswith(("token", "secret", "password")) for k in cfg["Env"])
    assert cfg["Entrypoint"][0] == "/usr/bin/python"


def test_no_dev_tools_in_image() -> None:
    probe = (
        "import importlib.util as u;"
        "print([m for m in ('pytest','ruff','mypy','pip') if u.find_spec(m)])"
    )
    out = _docker("run", "--rm", "--entrypoint", "/usr/bin/python", IMAGE, "-c", probe).stdout
    assert out.strip() == "[]"
