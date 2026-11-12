"""Figures shown on reveal: average, median and consensus."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.room.scales import Card, number


@dataclass(frozen=True)
class Results:
    votes: int
    average: float | None  # mean of numeric values, to one decimal
    median: float | None
    consensus: bool  # everyone chose the same card
    top_label: str | None  # the most-chosen card
    top_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "votes": self.votes,
            "average": self.average,
            "median": number(self.median),
            "consensus": self.consensus,
            "top": None
            if self.top_label is None
            else {"label": self.top_label, "count": self.top_count},
        }


def compute_results(votes: Iterable[Card], order: Sequence[Card] = ()) -> Results:
    """Results for a set of votes.

    Cards without a value are left out of the average and median. `order` is the
    scale's card order and breaks ties for the most-chosen card.
    """
    votes = list(votes)
    values = [c.value for c in votes if c.value is not None]

    average = None
    median = None
    if values:
        mean = Decimal(str(statistics.fmean(values)))
        average = float(mean.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        median = float(statistics.median(values))

    counts = Counter(c.label for c in votes)
    top_label = None
    top_count = 0
    if counts:
        rank = {c.label: i for i, c in enumerate(order)}
        top_label, top_count = min(counts.items(), key=lambda kv: (-kv[1], rank.get(kv[0], 0)))

    return Results(
        votes=len(votes),
        average=average,
        median=median,
        consensus=len(counts) == 1,
        top_label=top_label,
        top_count=top_count,
    )
