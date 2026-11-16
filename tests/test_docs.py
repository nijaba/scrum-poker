"""The documentation and the CI around it. Cases DC-01 to DC-03, at Unit level.

These read files only, so CI runs them for a documentation-only change too.
"""

import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} +(.+?) *#*$", re.M)
FENCE = re.compile(r"^```.*?^```", re.M | re.S)


def tracked_markdown() -> list[Path]:
    """The Markdown files in git, so a local, untracked note is not checked."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    return [ROOT / name for name in out.split()]


def anchors(path: Path) -> set[str]:
    """GitHub's heading anchors: lower case, punctuation dropped, spaces to hyphens."""
    found: set[str] = set()
    for title in HEADING.findall(FENCE.sub("", path.read_text())):
        text = re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", r"\1", title).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
        found.add(slug)
    return found


def links(path: Path) -> list[str]:
    text = FENCE.sub("", path.read_text())
    return [a or b for a, b in LINK.findall(text)]


@pytest.mark.parametrize("doc", tracked_markdown(), ids=lambda p: str(p.relative_to(ROOT)))
def test_dc01_every_link_in_the_docs_leads_somewhere(doc):
    broken = []
    for target in links(doc):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # https:, mailto: and the like
            continue
        file_part, _, anchor = target.partition("#")
        dest = (doc.parent / file_part).resolve() if file_part else doc
        if not dest.exists():
            broken.append(f"{target}: no such file")
        elif anchor and dest.suffix == ".md" and anchor.lower() not in anchors(dest):
            broken.append(f"{target}: no heading #{anchor} in {dest.name}")
    assert not broken, f"{doc.relative_to(ROOT)} has broken links: {broken}"


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("src", "href", "poster") and value:
                self.refs.append(value)


def test_dc02_the_project_page_builds_with_every_file_it_uses(tmp_path):
    out = tmp_path / "site"
    subprocess.run([str(ROOT / "scripts" / "build_site.sh"), str(out)], check=True)
    page = _Refs()
    page.feed((out / "index.html").read_text())
    css = (out / "style.css").read_text()
    local = [r for r in page.refs if not re.match(r"^([a-z]+:|//|#)", r)]
    local += re.findall(r"url\(['\"]?(?!data:|https?:)([^'\")]+)", css)
    assert local, "the page uses no local files, so this check proves nothing"
    missing = [r for r in local if not (out / r).is_file()]
    assert not missing, f"the built page refers to files the build left out: {missing}"
    anchors_on_page = set(re.findall(r'id="([^"]+)"', (out / "index.html").read_text()))
    jumps = [r[1:] for r in page.refs if r.startswith("#") and len(r) > 1]
    missing_sections = set(jumps) - anchors_on_page
    assert not missing_sections, f"links to missing sections: {missing_sections}"


# DC-03: scripts/ci_changes.sh, which lets CI run a short version for documentation.


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("needs git and bash")

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    git("commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "start")
    return tmp_path, git


def commit(repo, *files):
    path, git = repo
    for name in files:
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(name)
    git("add", "-A")
    git("commit", "-q", "--no-gpg-sign", "-m", "change")
    return git("rev-parse", "HEAD")


def decide(repo, event, base, head):
    path, _ = repo
    script = ROOT / "scripts" / "ci_changes.sh"
    out = subprocess.run(
        ["bash", str(script), event, base, head], cwd=path, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


DOCS_ONLY = [
    ("README.md",),
    ("docs/user-guide.md", "docs/images/a.png"),
    ("site/index.html", "scripts/build_site.sh", ".github/workflows/pages.yml"),
    (".claude/rules/x.md", "LICENSE", "frontend/README.md"),
]
CODE = [
    ("app/main.py",),
    ("README.md", "tests/test_x.py"),
    ("pyproject.toml",),
    ("frontend/public/tour.mp4",),
    ("scripts/guide_pictures.py",),
    (".github/workflows/ci.yml",),
    ("Dockerfile",),
]


@pytest.mark.parametrize("files", DOCS_ONLY)
@pytest.mark.parametrize("event", ["pull_request", "push"])
def test_dc03_documentation_only_runs_the_short_ci(repo, files, event):
    base = repo[1]("rev-parse", "HEAD")
    head = commit(repo, *files)
    assert decide(repo, event, base, head) == "code=false"


@pytest.mark.parametrize("files", CODE)
def test_dc03_any_other_change_runs_the_full_ci(repo, files):
    base = repo[1]("rev-parse", "HEAD")
    head = commit(repo, *files)
    assert decide(repo, "pull_request", base, head) == "code=true"


def test_dc03_when_in_doubt_the_full_ci_runs(repo):
    base = repo[1]("rev-parse", "HEAD")
    head = commit(repo, "README.md")
    assert decide(repo, "workflow_dispatch", base, head) == "code=true"
    assert decide(repo, "push", "0" * 40, head) == "code=true"
    assert decide(repo, "pull_request", "", head) == "code=true"
    assert decide(repo, "pull_request", "deadbeef", head) == "code=true"
    assert decide(repo, "pull_request", head, head) == "code=true"
