"""A tiny subset of JQL, read in Python: `field = value` and `field in (a, b)`, joined by AND,
on labels, type, priority, status and key. The development fake (app/jira/fake_atlassian.py)
and the demo rooms' sample backlog (app/demo/backlog.py) both use it; real rooms send JQL to
Jira, which reads all of it."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

FIELDS_TEXT = "labels, type, priority, status and key"

# The few JQL fields this subset understands, and the issue field each one reads.
_JQL_FIELDS = {"labels": "labels", "type": "issuetype", "issuetype": "issuetype"}
_JQL_FIELDS |= {"priority": "priority", "status": "status", "key": "key"}
_CLAUSE = re.compile(r"^\s*(\w+)\s*(=|in)\s*(.+?)\s*$", re.IGNORECASE)


def jql_matcher(jql: str) -> Callable[[dict[str, Any]], bool] | None:
    """A predicate for a tiny JQL subset: `field = value` and `field in (a, b)`, joined
    by AND, on labels, type, priority, status and key. None if the subset cannot read it."""
    tests = []
    for clause in re.split(r"\s+AND\s+", jql.strip(), flags=re.IGNORECASE):
        found = _CLAUSE.match(clause)
        if not found or found.group(1).lower() not in _JQL_FIELDS:
            return None
        name, op, raw = found.group(1).lower(), found.group(2).lower(), found.group(3)
        if op == "in":
            if not (raw.startswith("(") and raw.endswith(")")):
                return None
            values = [v.strip().strip("\"'") for v in raw[1:-1].split(",")]
        else:
            values = [raw.strip("\"'")]
        tests.append((_JQL_FIELDS[name], {v.lower() for v in values if v}))

    def matches(issue: dict[str, Any]) -> bool:
        for field, wanted in tests:
            if field == "key":
                have = {issue["key"].lower()}
            elif field == "labels":
                have = {label.lower() for label in issue["fields"].get("labels") or []}
            else:
                have = {((issue["fields"].get(field) or {}).get("name") or "").lower()}
            if not have & wanted:
                return False
        return True

    return matches
