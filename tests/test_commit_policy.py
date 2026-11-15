"""Proves the commit-msg hook rejects trailers, wrong identities and bad titles.

Each case runs in a throwaway repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _find_bash() -> str | None:
    """Prefer Git for Windows' bash: the WSL bash.exe on PATH cannot run Windows paths."""
    git = shutil.which("git")
    if os.name == "nt" and git:
        for candidate in (
            Path(git).parents[1] / "bin" / "bash.exe",
            Path(git).parents[1] / "usr" / "bin" / "bash.exe",
        ):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


BASH = _find_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

GOOD_NAME, GOOD_EMAIL = (
    (ROOT / ".github/allowed-author").read_text().strip().removesuffix(">").split(" <")
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel in (
        "scripts/hooks/commit-msg",
        "scripts/lib/commit-policy.sh",
        ".github/allowed-author",
    ):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _hook(repo: Path, message: str, name: str = GOOD_NAME, email: str = GOOD_EMAIL) -> int:
    msg = repo / "MSG"
    msg.write_text(message, encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": GOOD_NAME,
        "GIT_COMMITTER_EMAIL": GOOD_EMAIL,
    }
    assert BASH is not None
    return subprocess.run(
        [BASH, "scripts/hooks/commit-msg", "MSG"], cwd=repo, env=env, capture_output=True
    ).returncode


@pytest.mark.parametrize(
    "message",
    [
        "feat: add notes endpoint\n",
        "fix(app): reject whitespace titles\n\nBody text.\n",
        "ci!: require pinned actions\n",
        'Revert "feat: add notes endpoint"\n',
        "# comment line\nchore(deps): bump ruff\n",
    ],
)
def test_accepts_valid_messages(repo: Path, message: str) -> None:
    assert _hook(repo, message) == 0


@pytest.mark.parametrize(
    "message",
    [
        "feat: x\n\nCo-authored-by: Someone <s@example.com>\n",
        "feat: x\n\nco-authored-by: Someone <s@example.com>\n",
        "feat: x\n\nAssisted-by: Claude\n",
        "did stuff\n",
        "Feat: capitalised type\n",
        "feat:missing space\n",
        "feat: " + "x" * 80 + "\n",
        "\n",
    ],
)
def test_rejects_invalid_messages(repo: Path, message: str) -> None:
    assert _hook(repo, message) == 1


def test_rejects_wrong_email(repo: Path) -> None:
    assert _hook(repo, "feat: x\n", email="other@example.com") == 1


def test_rejects_wrong_name(repo: Path) -> None:
    assert _hook(repo, "feat: x\n", name="someone-else") == 1
