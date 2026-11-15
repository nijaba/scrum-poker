"""The light and dark palettes in frontend/src/app.css. Case TH-03, at Unit level."""

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).parent.parent / "frontend" / "src" / "app.css").read_text()

# Text tokens and the backgrounds each one is drawn on.
PAIRS = [
    ("ink", "ground"),
    ("ink", "surface"),
    ("ink", "chip"),
    ("text-2", "ground"),
    ("text-2", "surface"),
    ("text-3", "ground"),
    ("text-3", "surface"),
    ("text-3", "chip"),
    ("link", "ground"),
    ("link", "surface"),
    ("link-hover", "surface"),
    ("accent", "surface"),
    ("on-accent", "accent"),
    ("danger", "surface"),
    ("danger", "danger-bg"),
    ("disabled-text", "chip"),
    ("on-table", "table"),
    ("on-table-2", "table"),
    ("ground", "ink"),  # the deck note
    ("card-ink", "card-stock"),  # card faces, the same in both palettes
]


def block(start: str) -> str:
    """The declarations of the first rule that begins with `start`."""
    i = CSS.index(start)
    return CSS[CSS.index("{", i) + 1 : CSS.index("}", i)]


def tokens(body: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", body))


def luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


LIGHT = tokens(block(":root {"))
DARK = {**LIGHT, **tokens(block(':root[data-theme="dark"]'))}


def test_th03_the_dark_palette_is_the_same_whether_chosen_or_from_the_device():
    media = CSS[CSS.index("@media (prefers-color-scheme: dark)") :]
    assert tokens(block(':root[data-theme="dark"]')) == tokens(
        block_in(media, ':root:not([data-theme="light"])')
    )
    assert set(tokens(block(':root[data-theme="dark"]'))) <= set(LIGHT)


def block_in(text: str, start: str) -> str:
    i = text.index(start)
    return text[text.index("{", i) + 1 : text.index("}", i)]


@pytest.mark.parametrize("palette", ["light", "dark"])
@pytest.mark.parametrize(("text", "background"), PAIRS)
def test_th03_every_text_colour_is_readable_in_both_palettes(palette, text, background):
    colours = LIGHT if palette == "light" else DARK
    ratio = contrast(colours[text], colours[background])
    assert ratio >= 4.5, f"{palette}: --{text} on --{background} is {ratio:.2f}:1"
