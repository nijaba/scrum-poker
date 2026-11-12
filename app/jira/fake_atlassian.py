"""A local stand-in for Jira Cloud: Atlassian OAuth, the site list, /me, boards, backlog and
estimation. For tests, E2E runs and development only.

It is mounted at /_fake-jira when SCRUM_POKER_FAKE_JIRA=1, which configuration refuses
outside localhost. Tests drive its switches: reject writes, expire access tokens,
revoke refresh tokens. "Unreachable" is simulated by the test transport, not here.
"""

from __future__ import annotations

import html
import json
import secrets
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

CLOUD_ID = "cloud-shop"
SITE = {"id": CLOUD_ID, "name": "shop", "url": "https://shop.atlassian.net"}
ESTIMATE_FIELD = "customfield_10016"
ACCOUNT = {"account_id": "acc-owner", "email": "owner@example.com", "name": "Olive Owner"}
PAGE_LIMIT = 50  # the backlog never returns more than this per page, like Jira


def _issue(ticket: dict[str, Any], index: int) -> dict[str, Any]:
    description = ticket.get("description") or ""
    epic = ticket.get("epic")
    return {
        "id": str(10000 + index),
        "key": ticket["key"],
        "fields": {
            "summary": ticket.get("summary", ""),
            "issuetype": _issue_type(ticket.get("type") or "Story"),
            "priority": {"name": ticket.get("priority") or "Medium"},
            "labels": list(ticket.get("labels") or []),
            "description": description,
            "epic": {"name": epic} if epic else None,
            "status": _status(ticket.get("status") or "To Do"),
            "sprint": ticket.get("sprint"),
            ESTIMATE_FIELD: ticket.get("story_points"),
        },
        "renderedFields": {"description": f"<p>{html.escape(description)}</p>"},
    }


def _status(name: str) -> dict[str, Any]:
    """A status as Jira Cloud sends it, with its category: new (To Do), indeterminate, done."""
    key = {"In Progress": "indeterminate", "In Review": "indeterminate", "Done": "done"}.get(
        name, "new"
    )
    label = {"new": "To Do", "indeterminate": "In Progress", "done": "Done"}[key]
    return {"name": name, "statusCategory": {"key": key, "name": label}}


def _issue_type(name: str) -> dict[str, Any]:
    """An issue type as Jira Cloud sends it: epics sit at level 1, sub-tasks at -1."""
    level = {"Epic": 1, "Sub-task": -1, "Subtask": -1}.get(name, 0)
    return {"name": name, "hierarchyLevel": level, "subtask": level < 0}


def big_backlog(count: int = 120) -> list[dict[str, Any]]:
    """`count` unestimated tickets, for paging tests."""
    return [
        {"key": f"BIG-{i}", "summary": f"Ticket {i}", "type": "Task", "story_points": None}
        for i in range(1, count + 1)
    ]


class FakeAtlassian:
    def __init__(
        self,
        backlog: list[dict[str, Any]] | None = None,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.clock = clock
        self.boards: dict[int, dict[str, Any]] = {
            1: {
                "name": "SHOP board",
                "issues": [_issue(t, i) for i, t in enumerate(backlog or [])],
            },
            2: {"name": "BIG board", "issues": [_issue(t, i) for i, t in enumerate(big_backlog())]},
        }
        self.writes: list[tuple[str, str, int]] = []  # (issue key, value, board ID)
        self.fail_writes: str | None = None  # when set, Jira rejects writes with this message
        self.access_ttl = 3600
        self.codes: dict[str, str] = {}  # code -> redirect_uri
        self.access_tokens: dict[str, float] = {}  # token -> expiry
        self.refresh_tokens: set[str] = set()
        self.refreshes = 0
        self.app = self._build()

    # Switches for tests

    def issue_refresh_token(self) -> str:
        token = "refresh-" + secrets.token_urlsafe(12)
        self.refresh_tokens.add(token)
        return token

    def expire_access_tokens(self) -> None:
        self.access_tokens.clear()

    def revoke_refresh_tokens(self) -> None:
        self.refresh_tokens.clear()

    def estimate(self, board_id: int, key: str) -> Any:
        for issue in self.boards[board_id]["issues"]:
            if issue["key"] == key:
                return issue["fields"][ESTIMATE_FIELD]
        raise KeyError(key)

    # The app

    def _tokens(self) -> dict[str, Any]:
        access = "access-" + secrets.token_urlsafe(12)
        self.access_tokens[access] = self.clock() + self.access_ttl
        return {
            "access_token": access,
            "refresh_token": self.issue_refresh_token(),
            "expires_in": self.access_ttl,
            "token_type": "Bearer",
            "scope": "fake",
        }

    def _check(self, authorization: str | None) -> None:
        token = (authorization or "").removeprefix("Bearer ").strip()
        expiry = self.access_tokens.get(token)
        if expiry is None or expiry <= self.clock():
            raise HTTPException(401, "Unauthorized")

    def _board(self, cloud_id: str, board_id: int) -> dict[str, Any]:
        if cloud_id != CLOUD_ID or board_id not in self.boards:
            raise HTTPException(404, "Board not found")
        return self.boards[board_id]

    def _build(self) -> FastAPI:
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @app.get("/auth/authorize")
        async def authorize(request: Request, approve: str | None = None):
            q = dict(request.query_params)
            if q.get("audience") != "api.atlassian.com" or q.get("response_type") != "code":
                raise HTTPException(400, "audience=api.atlassian.com and response_type=code needed")
            if not q.get("redirect_uri") or not q.get("state"):
                raise HTTPException(400, "redirect_uri and state are required")
            sep = "&" if "?" in q["redirect_uri"] else "?"
            if approve == "1":
                code = secrets.token_urlsafe(12)
                self.codes[code] = q["redirect_uri"]
                query = urlencode({"code": code, "state": q["state"]})
                return RedirectResponse(f"{q['redirect_uri']}{sep}{query}", 302)
            if approve == "0":
                query = urlencode({"error": "access_denied", "state": q["state"]})
                return RedirectResponse(f"{q['redirect_uri']}{sep}{query}", 302)
            scopes = "".join(f"<li><code>{html.escape(s)}</code></li>" for s in q["scope"].split())
            accept = html.escape("?" + urlencode({**q, "approve": "1"}))
            cancel = html.escape("?" + urlencode({**q, "approve": "0"}))
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><title>Fake Atlassian consent</title>"
                "<style>body{font-family:system-ui;margin:48px auto;max-width:30rem;padding:0 16px}"
                "a{display:inline-block;margin-right:16px;font-size:18px}</style>"
                "<h1>Fake Jira Cloud</h1><p>For local development and tests only.</p>"
                f"<p>Scrum poker asks for:</p><ul>{scopes}</ul>"
                f'<a href="{accept}">Accept</a><a href="{cancel}">Cancel</a>'
            )

        @app.post("/auth/oauth/token")
        async def token(request: Request):
            raw = (await request.body()).decode()
            if request.headers.get("content-type", "").startswith("application/json"):
                form = json.loads(raw or "{}")
            else:
                form = {k: v[0] for k, v in parse_qs(raw).items()}
            if form.get("grant_type") == "authorization_code":
                redirect = self.codes.pop(form.get("code", ""), None)
                if redirect is None or redirect != form.get("redirect_uri"):
                    return JSONResponse({"error": "invalid_grant"}, status_code=403)
                return self._tokens()
            if form.get("grant_type") == "refresh_token":
                old = form.get("refresh_token", "")
                if old not in self.refresh_tokens:
                    return JSONResponse(
                        {
                            "error": "unauthorized_client",
                            "error_description": "refresh_token is invalid",
                        },
                        status_code=403,
                    )
                self.refresh_tokens.discard(old)  # tokens rotate
                self.refreshes += 1
                return self._tokens()
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

        @app.get("/api/oauth/token/accessible-resources")
        async def resources(authorization: str | None = Header(None)):
            self._check(authorization)
            return [{**SITE, "scopes": [], "avatarUrl": ""}]

        @app.get("/api/me")
        async def me(authorization: str | None = Header(None)):
            self._check(authorization)
            return ACCOUNT

        jira = "/api/ex/jira/{cloud_id}/rest/agile/1.0"

        @app.get(jira + "/board")
        async def boards(
            cloud_id: str,
            startAt: int = 0,  # noqa: N803 (Jira's parameter names)
            maxResults: int = 50,  # noqa: N803
            authorization: str | None = Header(None),
        ):
            self._check(authorization)
            if cloud_id != CLOUD_ID:
                raise HTTPException(404, "Site not found")
            values = [
                {"id": i, "name": b["name"], "type": "scrum"}
                for i, b in sorted(self.boards.items())
            ]
            page = values[startAt : startAt + maxResults]
            return {
                "startAt": startAt,
                "maxResults": maxResults,
                "total": len(values),
                "isLast": startAt + len(page) >= len(values),
                "values": page,
            }

        @app.get(jira + "/board/{board_id}/configuration")
        async def configuration(
            cloud_id: str, board_id: int, authorization: str | None = Header(None)
        ):
            self._check(authorization)
            board = self._board(cloud_id, board_id)
            return {
                "id": board_id,
                "name": board["name"],
                "estimation": {
                    "type": "field",
                    "field": {"fieldId": ESTIMATE_FIELD, "displayName": "Story Points"},
                },
            }

        @app.get(jira + "/board/{board_id}/backlog")
        async def backlog(
            cloud_id: str,
            board_id: int,
            startAt: int = 0,  # noqa: N803
            maxResults: int = 50,  # noqa: N803
            expand: str = "",
            authorization: str | None = Header(None),
        ):
            self._check(authorization)
            issues = self._board(cloud_id, board_id)["issues"]
            size = min(maxResults, PAGE_LIMIT)
            page = issues[startAt : startAt + size]
            if "renderedFields" not in expand:
                page = [{k: v for k, v in i.items() if k != "renderedFields"} for i in page]
            return {"startAt": startAt, "maxResults": size, "total": len(issues), "issues": page}

        @app.put("/api/ex/jira/{cloud_id}/rest/agile/1.0/issue/{key}/estimation")
        async def estimate(
            cloud_id: str,
            key: str,
            request: Request,
            boardId: int,  # noqa: N803
            authorization: str | None = Header(None),
        ):
            self._check(authorization)
            board = self._board(cloud_id, boardId)
            if self.fail_writes:
                return JSONResponse(
                    {"errorMessages": [self.fail_writes], "errors": {}}, status_code=400
                )
            value = (await request.json()).get("value")
            for issue in board["issues"]:
                if issue["key"] == key:
                    issue["fields"][ESTIMATE_FIELD] = float(value)
                    self.writes.append((key, value, boardId))
                    return {"fieldId": ESTIMATE_FIELD, "value": value}
            raise HTTPException(404, "Issue not found")

        return app
