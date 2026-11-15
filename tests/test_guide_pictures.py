"""The pictures in the user and admin guides. Cases GP-01 and GP-02, at Unit level."""

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).parent.parent / "docs"
IMAGES = DOCS / "images"
SCRIPT = (Path(__file__).parent.parent / "scripts" / "guide_pictures.py").read_text()
GUIDES = [DOCS / "user-guide.md", DOCS / "admin-guide.md"]
PICTURE = re.compile(r"!\[([^\]]*)\]\((images/[^)\s]+)\)")


def shown() -> list[tuple[str, str, str]]:
    return [(g.name, alt, path) for g in GUIDES for alt, path in PICTURE.findall(g.read_text())]


def test_gp01_both_guides_show_pictures():
    names = {guide for guide, _, _ in shown()}
    assert names == {"user-guide.md", "admin-guide.md"}


@pytest.mark.parametrize(("guide", "alt", "path"), shown())
def test_gp01_every_picture_exists_and_has_alt_text(guide, alt, path):
    assert (DOCS / path).is_file(), f"{guide} shows {path}, which is missing"
    assert len(alt.split()) >= 3, f"{guide}: {path} needs alt text that says what it shows"


@pytest.mark.parametrize("picture", sorted(p.name for p in IMAGES.glob("*.png")))
def test_gp02_every_picture_is_shown_and_scripted(picture):
    assert any(path == f"images/{picture}" for _, _, path in shown()), f"no guide shows {picture}"
    assert f'"{picture}"' in SCRIPT, f"scripts/guide_pictures.py does not make {picture}"
