"""Figures shown on reveal: average, median, consensus, and the spread of cards."""

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
    spread: tuple[tuple[str, int], ...] = ()  # (card, how many chose it), in scale order
    high: str | None = None  # the highest numeric card, when the numeric cards differ
    low: str | None = None  # the lowest

    def to_dict(self) -> dict[str, Any]:
        return {
            "votes": self.votes,
            "average": self.average,
            "median": number(self.median),
            "consensus": self.consensus,
            "top": None
            if self.top_label is None
            else {"label": self.top_label, "count": self.top_count},
            "spread": [{"label": label, "count": count} for label, count in self.spread],
            "high": self.high,
            "low": self.low,
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
    rank = {c.label: i for i, c in enumerate(order)}
    top_label = None
    top_count = 0
    if counts:
        top_label, top_count = min(counts.items(), key=lambda kv: (-kv[1], rank.get(kv[0], 0)))
    spread = tuple(sorted(counts.items(), key=lambda kv: rank.get(kv[0], len(rank))))

    # The ends of the range, which is where the discussion usually starts.
    high = low = None
    numeric = [c for c in votes if c.value is not None]
    if len({c.value for c in numeric}) > 1:
        high = max(numeric, key=lambda c: c.value).label
        low = min(numeric, key=lambda c: c.value).label

    return Results(
        votes=len(votes),
        average=average,
        median=median,
        consensus=len(counts) == 1,
        top_label=top_label,
        top_count=top_count,
        spread=spread,
        high=high,
        low=low,
    )
