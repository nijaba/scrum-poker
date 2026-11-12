"""Jira Cloud for one room at a time, through the room's own connection.

Access tokens stay in memory. Refreshes for a room run one at a time, and the
rotated refresh token is saved, encrypted, after every refresh. Every failure
becomes a JiraError whose code the room and the settings page understand.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

import httpx2

from app.config import AtlassianConfig, Settings
from app.jira.crypto import TokenCipher
from app.jira.html import clean, from_text
from app.room.ports import BacklogError, Clock, PointsWriteError
from app.store.rooms import RoomRecord, RoomStore

log = logging.getLogger(__name__)

MESSAGES = {
    "jira_unavailable": "Jira is not set up on this server.",
    "jira_not_connected": "The room's owner needs to connect Jira in the room settings.",
    "jira_reconnect": (
        "Jira no longer accepts this room's connection."
        " The room's owner needs to reconnect Jira in the room settings."
    ),
    "jira_no_board": "The room's owner needs to choose a Jira board in the room settings.",
    "jira_board_missing": "Jira cannot find the room's board. The owner can choose another one.",
    "jira_unreachable": "Could not reach Jira. Try again.",
    "jira_denied": "Jira did not grant access. Try connecting again.",
}

BACKLOG_PAGE = 50
MAX_PAGES = 100  # 5,000 tickets; a guard against a runaway loop, not a product limit
TOKEN_MARGIN = 60  # refresh a minute before Jira would refuse the access token


class JiraError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or MESSAGES.get(code) or "Jira answered unexpectedly."
        super().__init__(self.message)


class JiraService:
    def __init__(self, settings: Settings, store: RoomStore, clock: Clock) -> None:
        self.settings = settings
        self.store = store
        self.clock = clock
        self.cipher = TokenCipher(settings.token_key)
        # Tests point this at the app itself, to reach the fake Atlassian in-process.
        self.transport: httpx2.AsyncBaseTransport | None = None
        self._tokens: dict[str, tuple[str, float, str]] = {}  # slug -> (access, expiry, sealed)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def config(self) -> AtlassianConfig:
        if self.settings.atlassian is None:
            raise JiraError("jira_unavailable")
        return self.settings.atlassian

    def _http(self) -> httpx2.AsyncClient:
        if self.transport is not None:
            return httpx2.AsyncClient(transport=self.transport, timeout=15.0)
        return httpx2.AsyncClient(timeout=15.0)

    # Tokens

    async def connect(self, slug: str, code: str) -> RoomRecord:
        """Finish the owner's consent: exchange the code, then save the room's connection."""
        data = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.callback_url,
            },
            refusal="jira_denied",
        )
        access = data["access_token"]
        email = None
        async with self._http() as http:
            try:
                me = await http.get(f"{self.config.api_url}/me", headers=_bearer(access))
            except httpx2.TransportError as err:
                raise JiraError("jira_unreachable") from err
        if me.status_code == 200:
            email = me.json().get("email")
        sealed = self.cipher.seal(data["refresh_token"])
        record = await asyncio.to_thread(self.store.set_jira_connection, slug, sealed, email)
        self._tokens[slug] = (access, self._expiry(data), sealed)
        return record

    def forget(self, slug: str) -> None:
        self._tokens.pop(slug, None)

    async def _access(self, slug: str, *, force: bool = False) -> tuple[str, RoomRecord]:
        async with self._locks[slug]:
            record = await asyncio.to_thread(self.store.get, slug)
            if record is None or not record.jira.connected:
                raise JiraError("jira_not_connected")
            cached = self._tokens.get(slug)
            if (
                cached
                and not force
                and cached[2] == record.jira.token
                and cached[1] > self.clock.now()
            ):
                return cached[0], record
            refresh = self.cipher.open(record.jira.token)
            if refresh is None:
                raise JiraError("jira_reconnect")
            data = await self._token_request(
                {"grant_type": "refresh_token", "refresh_token": refresh}, refusal="jira_reconnect"
            )
            sealed = record.jira.token
            if data.get("refresh_token"):  # tokens rotate: keep the new one
                sealed = self.cipher.seal(data["refresh_token"])
                await asyncio.to_thread(self.store.set_jira_token, slug, sealed)
            self._tokens[slug] = (data["access_token"], self._expiry(data), sealed)
            return data["access_token"], record

    async def _token_request(self, body: dict[str, str], *, refusal: str) -> dict[str, Any]:
        config = self.config
        payload = {"client_id": config.client_id, "client_secret": config.client_secret, **body}
        async with self._http() as http:
            try:
                response = await http.post(config.token_url, json=payload)
            except httpx2.TransportError as err:
                raise JiraError("jira_unreachable") from err
        if response.status_code in (400, 401, 403):
            log.info("Atlassian refused a %s grant: %s", body["grant_type"], response.text[:200])
            raise JiraError(refusal)
        if response.status_code != 200:
            raise JiraError("jira_error", f"Jira answered unexpectedly ({response.status_code}).")
        data = response.json()
        if "access_token" not in data:
            raise JiraError("jira_error")
        return data

    def _expiry(self, data: dict[str, Any]) -> float:
        return self.clock.now() + float(data.get("expires_in", 3600)) - TOKEN_MARGIN

    # Requests

    async def _request(
        self, slug: str, method: str, url: str, **kwargs: Any
    ) -> tuple[httpx2.Response, RoomRecord]:
        """A call with the room's access token, refreshed once if Jira says it expired."""
        access, record = await self._access(slug)
        async with self._http() as http:
            for attempt in (1, 2):
                try:
                    response = await http.request(method, url, headers=_bearer(access), **kwargs)
                except httpx2.TransportError as err:
                    raise JiraError("jira_unreachable") from err
                if response.status_code == 401 and attempt == 1:
                    access, record = await self._access(slug, force=True)
                    continue
                if response.status_code == 401:
                    raise JiraError("jira_reconnect")
                return response, record
        raise AssertionError("unreachable")

    def _site(self, cloud_id: str) -> str:
        return f"{self.config.api_url}/ex/jira/{cloud_id}/rest/agile/1.0"

    async def sites(self, slug: str) -> list[dict[str, str]]:
        response, _ = await self._request(
            slug, "GET", f"{self.config.api_url}/oauth/token/accessible-resources"
        )
        _check(response)
        return [{"cloud_id": s["id"], "name": s["name"], "url": s["url"]} for s in response.json()]

    async def boards(self, slug: str, cloud_id: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            response, _ = await self._request(
                slug,
                "GET",
                f"{self._site(cloud_id)}/board",
                params={"startAt": page * 50, "maxResults": 50},
            )
            _check(response)
            data = response.json()
            values = data.get("values", [])
            found += [{"id": b["id"], "name": b["name"], "type": b.get("type")} for b in values]
            if data.get("isLast", True) or not values:
                break
        return found

    async def backlog(self, slug: str) -> list[dict[str, Any]]:
        """The board's backlog in rank order, as ticket dicts for the room engine."""
        record = await asyncio.to_thread(self.store.get, slug)
        if record is None or not record.jira.connected:
            raise JiraError("jira_not_connected")
        jira = record.jira
        if not jira.has_board:
            raise JiraError("jira_no_board")
        site = self._site(jira.cloud_id)

        response, _ = await self._request(
            slug, "GET", f"{site}/board/{jira.board_id}/configuration"
        )
        _check(response, missing="jira_board_missing")
        field = (((response.json().get("estimation") or {}).get("field")) or {}).get("fieldId")

        fields = ["summary", "issuetype", "priority", "labels", "description", "epic", "parent"]
        if field:
            fields.append(field)
        tickets: list[dict[str, Any]] = []
        start = 0
        for _ in range(MAX_PAGES):
            response, _ = await self._request(
                slug,
                "GET",
                f"{site}/board/{jira.board_id}/backlog",
                params={
                    "startAt": start,
                    "maxResults": BACKLOG_PAGE,
                    "fields": ",".join(fields),
                    "expand": "renderedFields",
                },
            )
            _check(response, missing="jira_board_missing")
            data = response.json()
            issues = data.get("issues", [])
            for issue in issues:
                if not _estimable(issue):
                    continue
                tickets.append(_ticket(issue, field, jira.site_url, len(tickets) + 1))
            start += len(issues)
            if not issues or start >= data.get("total", start):
                break
        return tickets

    async def write_points(self, slug: str, key: str, points: float) -> None:
        record = await asyncio.to_thread(self.store.get, slug)
        if record is None or not record.jira.connected:
            raise JiraError("jira_not_connected")
        if not record.jira.has_board:
            raise JiraError("jira_no_board")
        value = str(int(points)) if float(points).is_integer() else str(points)
        response, _ = await self._request(
            slug,
            "PUT",
            f"{self._site(record.jira.cloud_id)}/issue/{key}/estimation",
            params={"boardId": record.jira.board_id},
            json={"value": value},
        )
        _check(response)


class JiraRooms:
    """The room engine's backlog source and points writer, backed by Jira."""

    def __init__(self, service: JiraService) -> None:
        self.service = service

    async def load_backlog(self, slug: str) -> list[dict[str, Any]]:
        try:
            return await self.service.backlog(slug)
        except JiraError as err:
            raise BacklogError(err.message, err.code) from err

    async def write_points(self, slug: str, ticket_key: str, points: float) -> None:
        try:
            await self.service.write_points(slug, ticket_key, points)
        except JiraError as err:
            raise PointsWriteError(err.message, err.code) from err


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _check(response: httpx2.Response, missing: str | None = None) -> None:
    if response.status_code < 300:
        return
    if response.status_code == 404 and missing:
        raise JiraError(missing)
    if response.status_code in (400, 403, 404):
        raise JiraError("jira_rejected", _jira_message(response))
    raise JiraError("jira_error", f"Jira answered unexpectedly ({response.status_code}).")


def _jira_message(response: httpx2.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = {}
    parts = list(data.get("errorMessages") or []) + [
        str(v) for v in (data.get("errors") or {}).values()
    ]
    return " ".join(parts) or f"Jira refused the request ({response.status_code})."


def _estimable(issue: dict[str, Any]) -> bool:
    """Whether the issue is a ticket the team estimates: not an epic, not a sub-task.

    Epics, and any type above them, group tickets; sub-tasks split one. Jira Cloud gives every
    issue type a hierarchy level (-1 sub-task, 0 standard, 1 epic) and a subtask flag, which
    hold when the type is renamed or translated. The names are a fallback for a response
    without them.
    """
    kind = (issue.get("fields") or {}).get("issuetype") or {}
    if kind.get("subtask") is True:
        return False
    level = kind.get("hierarchyLevel")
    if isinstance(level, int):
        return level == 0
    return kind.get("name") not in ("Epic", "Sub-task", "Subtask")


def _ticket(
    issue: dict[str, Any], field: str | None, site_url: str | None, rank: int
) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    rendered = (issue.get("renderedFields") or {}).get("description")
    raw = fields.get("description")
    if rendered:
        description = clean(rendered)
    elif isinstance(raw, str):
        description = from_text(raw)
    else:
        description = ""
    epic = (fields.get("epic") or {}).get("name")
    parent = fields.get("parent") or {}
    parent_fields = parent.get("fields") or {}
    if not epic and (parent_fields.get("issuetype") or {}).get("name") == "Epic":
        epic = parent_fields.get("summary")
    points = fields.get(field) if field else None
    return {
        "key": issue["key"],
        "summary": fields.get("summary") or "",
        "type": (fields.get("issuetype") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "epic": epic,
        "labels": fields.get("labels") or [],
        "description": description,
        "story_points": points if isinstance(points, int | float) else None,
        "url": f"{site_url}/browse/{issue['key']}" if site_url else None,
        "rank": rank,
    }
