"""Jira's rendered description, cleaned before any browser sees it."""

from __future__ import annotations

import html

import nh3

TAGS = {
    "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "del", "ins", "sub", "sup", "span",
    "code", "pre", "blockquote", "ul", "ol", "li", "a",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip


def clean(rendered: str) -> str:
    """Only formatting tags; links only to http, https or mailto, opened safely."""
    return nh3.clean(
        rendered,
        tags=TAGS,
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
    )


def from_text(text: str) -> str:
    """Plain text as HTML, for a ticket that has no rendered description."""
    paragraphs = [p for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
