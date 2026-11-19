"""scripts/release.sh refuses to tag a release it should not. Case VR-03, at Unit level.

Each test builds a throwaway repository with its own origin; RELEASE_DRY_RUN stops the
script before it tags, pushes or publishes anything.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "release.sh"


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("needs git and bash")
    origin, work = tmp_path / "origin.git", tmp_path / "work"

    def git(*args, cwd=work):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    git("clone", "-q", str(origin), str(work), cwd=tmp_path)
    (work / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.2.0"\n')
    git("add", "-A")
    git("commit", "-q", "--no-gpg-sign", "-m", "start")
    git("push", "-q", "origin", "main")
    return work, git


def release(work, version):
    env = {**os.environ, "RELEASE_DRY_RUN": "1", "RELEASE_ROOT": str(work)}
    return subprocess.run(
        ["bash", str(SCRIPT), version], cwd=work, capture_output=True, text=True, env=env
    )


def tags(git):
    return git("tag", "--list")


def test_vr03_a_ready_main_passes_the_checks(repo):
    work, git = repo
    out = release(work, "1.2.0")
    assert out.returncode == 0, out.stderr
    assert "v1.2.0" in out.stdout and tags(git) == ""


@pytest.mark.parametrize("version", ["1.3.0", "v1.2.0", "1.2", "latest"])
def test_vr03_the_version_must_be_the_one_in_pyproject(repo, version):
    work, git = repo
    out = release(work, version)
    assert out.returncode != 0 and tags(git) == ""


def test_vr03_off_main_or_with_changes_it_refuses(repo):
    work, git = repo
    (work / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.2.0"\n# edited\n')
    assert release(work, "1.2.0").returncode != 0
    git("checkout", "-q", "pyproject.toml")

    git("switch", "-q", "-c", "feature")
    assert release(work, "1.2.0").returncode != 0
    git("switch", "-q", "main")

    git("commit", "-q", "--no-gpg-sign", "--allow-empty", "-m", "not pushed")
    assert release(work, "1.2.0").returncode != 0  # ahead of origin/main
    assert tags(git) == ""


def test_vr03_an_existing_tag_is_never_reused(repo):
    work, git = repo
    git("tag", "v1.2.0")
    assert release(work, "1.2.0").returncode != 0
