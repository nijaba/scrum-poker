# ruff: noqa: E501  (ticket descriptions are long strings)
"""The demo rooms' sample backlog: made-up tickets in Jira rank order, in the shape the
room expects from Jira. Each demo room works on its own copy, through its queue filter.

The first twelve are the tests' fake backlog (tests/fixtures/fake_backlog.json). The last four
exist for the queue filter (design.md, "Demo rooms"): an epic, a sub-task, a ticket in progress
and one resolved as Won't Do, which the default filter leaves out.
"""

from __future__ import annotations

import copy
import html
from collections.abc import Callable
from typing import Any

from app.jira.jql_subset import FIELDS_TEXT, jql_matcher
from app.room.ports import BacklogError
from app.room.queue_filter import QueueFilter

SAMPLE_BACKLOG = [
    {
        "rank": 1,
        "key": "SHOP-131",
        "summary": "Guest checkout button on the cart page",
        "type": "Story",
        "priority": "Medium",
        "epic": "Checkout revamp",
        "labels": ["checkout"],
        "description": "Sample description for SHOP-131.",
        "story_points": 3,
    },
    {
        "rank": 2,
        "key": "SHOP-134",
        "summary": "Order confirmation page redesign",
        "type": "Story",
        "priority": "Medium",
        "epic": "Checkout revamp",
        "labels": ["checkout"],
        "description": "As a shopper who has just paid, I want a clear confirmation page so that I know the order went through and what happens next. Show the order number, the items, the delivery address and the expected delivery window. Offer a link to track the order and a button to continue shopping. The page must work on small screens, read well with a screen reader, and load in under a second on a mid-range phone. Payment failures keep the shopper on the checkout page with the error, so they never land here by mistake. Analytics fire one purchase event per order, even when the page is reloaded.",
        "story_points": None,
    },
    {
        "rank": 3,
        "key": "SHOP-136",
        "summary": "Promo code field validation",
        "type": "Bug",
        "priority": "High",
        "epic": "Checkout revamp",
        "labels": ["checkout"],
        "description": "Sample description for SHOP-136.",
        "story_points": 5,
    },
    {
        "rank": 4,
        "key": "SHOP-138",
        "summary": "Address autocomplete at checkout",
        "type": "Story",
        "priority": "Medium",
        "epic": "Checkout revamp",
        "labels": ["checkout", "mobile"],
        "description": "Sample description for SHOP-138.",
        "story_points": None,
    },
    {
        "rank": 5,
        "key": "SHOP-139",
        "summary": "Show a delivery estimate on the product page",
        "type": "Story",
        "priority": "Low",
        "epic": None,
        "labels": ["catalog"],
        "description": "Sample description for SHOP-139.",
        "story_points": None,
    },
    {
        "rank": 6,
        "key": "SHOP-140",
        "summary": "Fix rounding in cart totals",
        "type": "Bug",
        "priority": "High",
        "epic": None,
        "labels": ["checkout"],
        "description": "Sample description for SHOP-140.",
        "story_points": 3,
    },
    {
        "rank": 7,
        "key": "SHOP-142",
        "summary": "Save card details for faster checkout",
        "type": "Story",
        "priority": "High",
        "epic": "Checkout revamp",
        "labels": ["payments", "mobile"],
        "description": "As a returning shopper, I want my card saved after the first purchase so that I can pay in one tap. Covers tokenising the card with the payment provider, a consent checkbox at checkout, and a way to remove a saved card from the account page.",
        "story_points": None,
    },
    {
        "rank": 8,
        "key": "SHOP-143",
        "summary": "Apple Pay on the product page",
        "type": "Story",
        "priority": "Medium",
        "epic": "Checkout revamp",
        "labels": ["payments"],
        "description": "Sample description for SHOP-143.",
        "story_points": None,
    },
    {
        "rank": 9,
        "key": "SHOP-145",
        "summary": "Retry failed payment webhooks",
        "type": "Task",
        "priority": "High",
        "epic": None,
        "labels": ["payments"],
        "description": "Sample description for SHOP-145.",
        "story_points": 5,
    },
    {
        "rank": 10,
        "key": "SHOP-147",
        "summary": "Refund status emails",
        "type": "Story",
        "priority": "Medium",
        "epic": None,
        "labels": ["notifications"],
        "description": "Sample description for SHOP-147.",
        "story_points": None,
    },
    {
        "rank": 11,
        "key": "SHOP-149",
        "summary": "Wishlist sharing link",
        "type": "Story",
        "priority": "Low",
        "epic": None,
        "labels": ["catalog"],
        "description": "Sample description for SHOP-149.",
        "story_points": None,
    },
    {
        "rank": 12,
        "key": "SHOP-150",
        "summary": "Sort search results by price",
        "type": "Story",
        "priority": "Low",
        "epic": None,
        "labels": ["catalog"],
        "description": "Sample description for SHOP-150.",
        "story_points": None,
    },
    {
        "rank": 13,
        "key": "SHOP-151",
        "summary": "Checkout revamp",
        "type": "Epic",
        "kind": "epic",
        "priority": "Medium",
        "epic": None,
        "labels": ["checkout"],
        "description": "Groups the checkout tickets. Epics are never estimated themselves.",
        "story_points": None,
    },
    {
        "rank": 14,
        "key": "SHOP-152",
        "summary": "Unit tests for the promo code parser",
        "type": "Sub-task",
        "kind": "subtask",
        "priority": "Medium",
        "epic": "Checkout revamp",
        "labels": ["checkout"],
        "description": "A sub-task of SHOP-136. It comes up only when the queue filter includes sub-tasks.",
        "story_points": None,
    },
    {
        "rank": 15,
        "key": "SHOP-153",
        "summary": "Lazy-load product images",
        "type": "Story",
        "status": "In Progress",
        "category": "indeterminate",
        "priority": "Medium",
        "epic": None,
        "labels": ["catalog", "performance"],
        "description": "Already started. It comes up only when the queue filter includes tickets in progress.",
        "story_points": None,
    },
    {
        "rank": 16,
        "key": "SHOP-154",
        "summary": "Gift wrapping option",
        "type": "Story",
        "resolution": "Won't Do",
        "priority": "Low",
        "epic": None,
        "labels": ["checkout"],
        "description": "Resolved as Won't Do while still in a To Do status. It comes up only when the queue filter includes resolved tickets.",
        "story_points": None,
    },
]

# What the room needs of a ticket; the rest describes it for the queue filter.
ROOM_FIELDS = ("rank", "key", "summary", "type", "priority", "epic", "labels", "description")
ROOM_FIELDS += ("story_points", "status")


def _admitted(ticket: dict[str, Any], chosen: QueueFilter) -> bool:
    """The same rule as a real room's Jira backlog (app/jira/client.py, _estimable), on the
    sample's own fields: never epics; sub-tasks, tickets in progress and resolved tickets only
    when the filter takes them; Done never."""
    kind = ticket.get("kind", "standard")
    if kind == "epic" or (kind == "subtask" and not chosen.subtasks):
        return False
    category = ticket.get("category", "new")
    if category not in (("new", "indeterminate") if chosen.in_progress else ("new",)):
        return False
    return not (ticket.get("resolution") and not chosen.resolved)


def _as_issue(ticket: dict[str, Any]) -> dict[str, Any]:
    """Just enough of a Jira issue for the JQL subset to read."""
    return {
        "key": ticket["key"],
        "fields": {
            "labels": ticket.get("labels") or [],
            "issuetype": {"name": ticket["type"]},
            "priority": {"name": ticket.get("priority") or ""},
            "status": {"name": ticket.get("status", "To Do")},
        },
    }


class DemoBacklog:
    """A demo room's backlog source and points writer, on its own copy of the sample.

    `current_filter` gives the room's saved queue filter each time the backlog loads."""

    def __init__(self, current_filter: Callable[[], QueueFilter]) -> None:
        self.current_filter = current_filter
        self.tickets = copy.deepcopy(SAMPLE_BACKLOG)
        self.writes: list[tuple[str, float]] = []

    def backlog(self, chosen: QueueFilter) -> list[dict[str, Any]]:
        """The tickets the filter takes, in rank order, as the room expects them. Tickets that
        already have an estimate are included: they count in the backlog counters."""
        matches = None
        if chosen.jql:
            matches = jql_matcher(chosen.jql)
            if matches is None:
                raise BacklogError(
                    f"The demo understands only simple JQL ({chosen.jql}): field = value or"
                    f" field in (a, b), joined by AND, on {FIELDS_TEXT}.",
                    "jira_bad_filter",
                )
        found = []
        for ticket in self.tickets:
            if not _admitted(ticket, chosen) or (matches and not matches(_as_issue(ticket))):
                continue
            shown = {name: ticket.get(name) for name in ROOM_FIELDS}
            shown["status"] = ticket.get("status", "To Do")
            shown["description"] = f"<p>{html.escape(ticket.get('description') or '')}</p>"
            shown["url"] = None
            found.append(shown)
        return found

    async def load_backlog(self, slug: str) -> list[dict[str, Any]]:
        return self.backlog(self.current_filter())

    async def write_points(self, slug: str, ticket_key: str, points: float) -> None:
        self.writes.append((ticket_key, points))
        for ticket in self.tickets:
            if ticket["key"] == ticket_key:
                ticket["story_points"] = points
