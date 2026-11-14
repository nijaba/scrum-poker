"""A room's queue filter: which backlog tickets its sessions walk through.

The default is the long-standing rule: standard work types in Jira's To Do status
category, with no resolution and no estimate. The owner can widen it, or narrow
the backlog with extra JQL. See design.md, "Queue filter".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MAX_JQL = 500
TOGGLES = ("subtasks", "in_progress", "resolved", "estimated")


class FilterError(ValueError):
    """The filter cannot be used. The message says why."""


@dataclass(frozen=True)
class QueueFilter:
    subtasks: bool = False  # sub-tasks join; epics never do
    in_progress: bool = False  # Jira's In Progress status category joins To Do
    resolved: bool = False  # tickets with a resolution join
    estimated: bool = False  # tickets that already have an estimate join, to re-estimate
    jql: str = ""  # narrows the backlog, through the endpoint's jql parameter

    @property
    def is_default(self) -> bool:
        return self == QueueFilter()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Any) -> QueueFilter:
        """Read a filter from JSON. Missing fields take the default."""
        if not isinstance(data, dict):
            raise FilterError("The queue filter is an object.")
        unknown = set(data) - {*TOGGLES, "jql"}
        if unknown:
            raise FilterError(f"Unknown queue filter fields: {', '.join(sorted(unknown))}.")
        for name in TOGGLES:
            if name in data and not isinstance(data[name], bool):
                raise FilterError(f"The queue filter's {name} is true or false.")
        jql = data.get("jql", "")
        if not isinstance(jql, str):
            raise FilterError("The queue filter's JQL is text.")
        jql = jql.strip()
        if len(jql) > MAX_JQL:
            raise FilterError(f"The queue filter's JQL is at most {MAX_JQL} characters.")
        return QueueFilter(**{name: data.get(name, False) for name in TOGGLES}, jql=jql)
