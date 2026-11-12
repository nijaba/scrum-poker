"""Card scales: Fibonacci, T-shirt with a value mapping, and custom lists.

Each card has a label and an optional numeric value. Cards without a value,
such as "?", are left out of the statistics and cannot be confirmed as points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.room.errors import CommandError

MAX_CARDS = 30
MAX_LABEL = 10

FIBONACCI = ("1", "2", "3", "5", "8", "13", "21", "?")
TSHIRT_MAPPING: dict[str, float] = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8, "XXL": 13}


@dataclass(frozen=True)
class Card:
    label: str
    value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "value": number(self.value)}


@dataclass(frozen=True)
class Scale:
    kind: str  # "fibonacci", "tshirt" or "custom"
    cards: tuple[Card, ...]

    def card(self, label: str) -> Card | None:
        for card in self.cards:
            if card.label == label:
                return card
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "cards": [c.to_dict() for c in self.cards]}

    @staticmethod
    def from_dict(data: Any) -> Scale:
        """Build a scale from a client command. Raises CommandError when invalid."""
        if not isinstance(data, dict):
            raise CommandError("invalid_scale", "A scale must be an object.")
        kind = data.get("kind")
        if kind == "fibonacci":
            return fibonacci()
        if kind == "tshirt":
            mapping = data.get("mapping")
            if mapping is not None and not isinstance(mapping, dict):
                raise CommandError("invalid_scale", "The T-shirt mapping must be an object.")
            return tshirt(mapping)
        if kind == "custom":
            cards = data.get("cards")
            if not isinstance(cards, list):
                raise CommandError("invalid_scale", "A custom scale needs a list of cards.")
            return custom(cards)
        raise CommandError("invalid_scale", "Unknown scale kind.")


def fibonacci() -> Scale:
    return Scale("fibonacci", tuple(_card_from_label(label) for label in FIBONACCI))


def tshirt(mapping: dict[str, Any] | None = None) -> Scale:
    """T-shirt sizes with an editable mapping, plus "?"."""
    mapping = TSHIRT_MAPPING if mapping is None else mapping
    cards = [_card(label, value) for label, value in mapping.items()]
    cards.append(Card("?"))
    return validated("tshirt", cards)


def custom(items: list[Any]) -> Scale:
    """A custom list. Items are labels ("5", "?") or {"label", "value"} objects.

    A plain label that reads as a number gets that number as its value.
    """
    cards = []
    for item in items:
        if isinstance(item, str):
            cards.append(_card_from_label(item))
        elif isinstance(item, dict):
            cards.append(_card(item.get("label"), item.get("value")))
        else:
            raise CommandError("invalid_scale", "Each card is a label or a {label, value} object.")
    return validated("custom", cards)


def number(value: float | None) -> float | int | None:
    """Render whole numbers as ints so clients show 5, not 5.0."""
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def parse_value(value: Any) -> float | None:
    """A card or points value: a finite, non-negative number, or None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CommandError("invalid_value", "A value must be a number.")
    if not math.isfinite(value) or value < 0:
        raise CommandError("invalid_value", "A value must be a finite number, zero or more.")
    return float(value)


def _card(label: Any, value: Any) -> Card:
    if not isinstance(label, str) or not label.strip():
        raise CommandError("invalid_scale", "Each card needs a label.")
    label = label.strip()
    if len(label) > MAX_LABEL:
        raise CommandError("invalid_scale", f"Card labels are at most {MAX_LABEL} characters.")
    return Card(label, parse_value(value))


def _card_from_label(label: str) -> Card:
    try:
        value = float(label)
    except ValueError:
        value = None
    if value is not None and (not math.isfinite(value) or value < 0):
        value = None
    return _card(label, value)


def validated(kind: str, cards: list[Card]) -> Scale:
    if not cards:
        raise CommandError("invalid_scale", "A scale needs at least one card.")
    if len(cards) > MAX_CARDS:
        raise CommandError("invalid_scale", f"A scale has at most {MAX_CARDS} cards.")
    labels = [c.label for c in cards]
    if len(set(labels)) != len(labels):
        raise CommandError("invalid_scale", "Card labels must be unique.")
    return Scale(kind, tuple(cards))
