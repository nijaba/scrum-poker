"""Room definitions in one SQLite file: slug, owner, delegates, scale, timer default, sound,
auto-reveal, and the room's Jira connection (refresh token encrypted by the caller, site and board).

The file never holds votes, results or session counters. Calls are short and
synchronous; async callers run them with `asyncio.to_thread`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from app.auth.access import access_for
from app.auth.identity import Identity
from app.room.queue_filter import QueueFilter
from app.room.room import DEFAULT_TIMER
from app.room.scales import Card, Scale, fibonacci, validated

SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE rooms (
    slug TEXT PRIMARY KEY,
    owner_provider TEXT NOT NULL,
    owner_subject TEXT NOT NULL,
    owner_label TEXT NOT NULL,
    scale TEXT NOT NULL,
    timer_seconds REAL NOT NULL,
    sound INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE delegates (
    room TEXT NOT NULL REFERENCES rooms(slug) ON DELETE CASCADE ON UPDATE CASCADE,
    provider TEXT NOT NULL,
    identifier TEXT NOT NULL,
    PRIMARY KEY (room, provider, identifier)
);
CREATE TABLE slug_aliases (
    slug TEXT PRIMARY KEY,
    room TEXT NOT NULL REFERENCES rooms(slug) ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX delegates_by_account ON delegates (provider, identifier);
"""

# Each step upgrades a file from the version before it.
MIGRATIONS = {
    2: """
ALTER TABLE rooms ADD COLUMN jira_token TEXT;
ALTER TABLE rooms ADD COLUMN jira_email TEXT;
ALTER TABLE rooms ADD COLUMN jira_cloud_id TEXT;
ALTER TABLE rooms ADD COLUMN jira_site_url TEXT;
ALTER TABLE rooms ADD COLUMN jira_site_name TEXT;
ALTER TABLE rooms ADD COLUMN jira_board_id INTEGER;
ALTER TABLE rooms ADD COLUMN jira_board_name TEXT;
""",
    3: """
ALTER TABLE rooms ADD COLUMN auto_reveal INTEGER NOT NULL DEFAULT 0;
""",
    4: """
ALTER TABLE rooms ADD COLUMN queue_filter TEXT;
""",
}

JIRA_COLUMNS = (
    "jira_token",
    "jira_email",
    "jira_cloud_id",
    "jira_site_url",
    "jira_site_name",
    "jira_board_id",
    "jira_board_name",
)


class SlugTaken(Exception):
    """The short name belongs to another room, or is a retired name kept as a redirect."""


@dataclass(frozen=True, order=True)
class Delegate:
    provider: str  # "google" or "github"
    identifier: str  # Google email or GitHub login, lowercased

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "identifier": self.identifier}


@dataclass(frozen=True)
class JiraLink:
    """The room's Jira connection. `token` is the refresh token, already encrypted."""

    token: str | None = None
    email: str | None = None
    cloud_id: str | None = None
    site_url: str | None = None
    site_name: str | None = None
    board_id: int | None = None
    board_name: str | None = None

    @property
    def connected(self) -> bool:
        return bool(self.token)

    @property
    def has_board(self) -> bool:
        return bool(self.cloud_id and self.board_id)


@dataclass(frozen=True)
class RoomRecord:
    slug: str
    owner: tuple[str, str]  # (provider, subject)
    owner_label: str  # the owner's email or GitHub login, for display
    scale: Scale = field(default_factory=fibonacci)
    timer_seconds: float = DEFAULT_TIMER
    sound: bool = False
    auto_reveal: bool = False
    delegates: tuple[Delegate, ...] = ()
    jira: JiraLink = field(default_factory=JiraLink)
    queue_filter: QueueFilter = field(default_factory=QueueFilter)

    def access(self, identity: Identity | None) -> str | None:
        return access_for(identity, self.owner, self.delegates)


class RoomStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    @property
    def _db(self) -> sqlite3.Connection:
        """The connection, opened (and the schema migrated) on first use."""
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._conn = conn
            self._migrate()
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # Reads

    def resolve(self, slug: str) -> str | None:
        """The room's current slug, following a retired name to its room."""
        with self._lock:
            row = self._db.execute("SELECT slug FROM rooms WHERE slug = ?", (slug,)).fetchone()
            if row is None:
                row = self._db.execute(
                    "SELECT room FROM slug_aliases WHERE slug = ?", (slug,)
                ).fetchone()
        return row[0] if row else None

    def get(self, slug: str) -> RoomRecord | None:
        with self._lock:
            return self._get(slug)

    def rooms_for(self, identity: Identity) -> list[tuple[RoomRecord, str]]:
        """Rooms this account owns or is a delegate of, with its access, by slug."""
        identifier = identity.email if identity.provider == "google" else identity.login
        with self._lock:
            slugs = self._db.execute(
                """
                SELECT slug FROM rooms WHERE owner_provider = ? AND owner_subject = ?
                UNION
                SELECT room FROM delegates WHERE provider = ? AND identifier = ?
                ORDER BY 1
                """,
                (*identity.key, identity.provider, (identifier or "").lower()),
            ).fetchall()
            records = [self._get(row[0]) for row in slugs]
        found = []
        for record in records:
            access = record.access(identity) if record else None
            if access:
                found.append((record, access))
        return found

    # Writes

    def create(self, record: RoomRecord) -> RoomRecord:
        with self._lock, self._transaction():
            if self._taken(record.slug):
                raise SlugTaken(record.slug)
            self._db.execute(
                "INSERT INTO rooms (slug, owner_provider, owner_subject, owner_label, scale,"
                " timer_seconds, sound, auto_reveal, queue_filter, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.slug,
                    *record.owner,
                    record.owner_label,
                    _scale_json(record.scale),
                    record.timer_seconds,
                    int(record.sound),
                    int(record.auto_reveal),
                    _filter_json(record.queue_filter),
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            self._set_delegates(record.slug, record.delegates)
            return self._get(record.slug)

    def update(
        self,
        slug: str,
        *,
        scale: Scale | None = None,
        timer_seconds: float | None = None,
        sound: bool | None = None,
        auto_reveal: bool | None = None,
        delegates: Iterable[Delegate] | None = None,
        queue_filter: QueueFilter | None = None,
    ) -> RoomRecord:
        with self._lock, self._transaction():
            current = self._get(slug)
            if current is None:
                raise KeyError(slug)
            new = replace(
                current,
                scale=current.scale if scale is None else scale,
                timer_seconds=current.timer_seconds if timer_seconds is None else timer_seconds,
                sound=current.sound if sound is None else sound,
                auto_reveal=current.auto_reveal if auto_reveal is None else auto_reveal,
                queue_filter=current.queue_filter if queue_filter is None else queue_filter,
            )
            self._db.execute(
                "UPDATE rooms SET scale = ?, timer_seconds = ?, sound = ?, auto_reveal = ?,"
                " queue_filter = ? WHERE slug = ?",
                (
                    _scale_json(new.scale),
                    new.timer_seconds,
                    int(new.sound),
                    int(new.auto_reveal),
                    _filter_json(new.queue_filter),
                    slug,
                ),
            )
            if delegates is not None:
                self._db.execute("DELETE FROM delegates WHERE room = ?", (slug,))
                self._set_delegates(slug, delegates)
            return self._get(slug)

    def rename(self, old: str, new: str) -> RoomRecord:
        """Give the room a new slug. The old one keeps redirecting and stays reserved."""
        with self._lock, self._transaction():
            if old == new:
                return self._get(old)
            owner_of_new = self._resolve_unlocked(new)
            if owner_of_new is not None and owner_of_new != old:
                raise SlugTaken(new)
            self._db.execute("DELETE FROM slug_aliases WHERE slug = ?", (new,))
            # Delegates and older aliases follow through ON UPDATE CASCADE.
            self._db.execute("UPDATE rooms SET slug = ? WHERE slug = ?", (new, old))
            self._db.execute("INSERT INTO slug_aliases VALUES (?, ?)", (old, new))
            return self._get(new)

    def set_jira_connection(self, slug: str, token: str, email: str | None) -> RoomRecord:
        """Connect (or reconnect) the room. A chosen board stays."""
        return self._set(slug, jira_token=token, jira_email=email)

    def set_jira_token(self, slug: str, token: str) -> None:
        """Replace the refresh token after a rotation."""
        self._set(slug, jira_token=token)

    def set_jira_board(
        self,
        slug: str,
        cloud_id: str,
        site_url: str,
        site_name: str,
        board_id: int,
        board_name: str,
    ) -> RoomRecord:
        return self._set(
            slug,
            jira_cloud_id=cloud_id,
            jira_site_url=site_url,
            jira_site_name=site_name,
            jira_board_id=board_id,
            jira_board_name=board_name,
        )

    def clear_jira(self, slug: str) -> RoomRecord:
        return self._set(slug, **dict.fromkeys(JIRA_COLUMNS))

    def delete(self, slug: str) -> None:
        """Delete the room. Its delegates and retired names go with it."""
        with self._lock, self._transaction():
            self._db.execute("DELETE FROM rooms WHERE slug = ?", (slug,))

    # Internals

    def _transaction(self):
        return _Transaction(self._db)

    def _migrate(self) -> None:
        # executescript commits on its own, so each script carries its transaction.
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError("The database was written by a newer version of the app.")
        if version == 0:
            self._db.executescript(f"BEGIN; {SCHEMA} PRAGMA user_version = 1; COMMIT;")
            version = 1
        while version < SCHEMA_VERSION:
            version += 1
            self._db.executescript(
                f"BEGIN; {MIGRATIONS[version]} PRAGMA user_version = {version}; COMMIT;"
            )

    def _set(self, slug: str, **columns) -> RoomRecord:
        assert set(columns) <= set(JIRA_COLUMNS)
        with self._lock, self._transaction():
            assignments = ", ".join(f"{name} = ?" for name in columns)
            cursor = self._db.execute(
                f"UPDATE rooms SET {assignments} WHERE slug = ?", (*columns.values(), slug)
            )
            if cursor.rowcount == 0:
                raise KeyError(slug)
            return self._get(slug)

    def _resolve_unlocked(self, slug: str) -> str | None:
        row = self._db.execute("SELECT slug FROM rooms WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            row = self._db.execute(
                "SELECT room FROM slug_aliases WHERE slug = ?", (slug,)
            ).fetchone()
        return row[0] if row else None

    def _taken(self, slug: str) -> bool:
        return self._resolve_unlocked(slug) is not None

    def _set_delegates(self, slug: str, delegates: Iterable[Delegate]) -> None:
        self._db.executemany(
            "INSERT OR IGNORE INTO delegates VALUES (?, ?, ?)",
            [(slug, d.provider, d.identifier.lower()) for d in delegates],
        )

    def _get(self, slug: str) -> RoomRecord | None:
        row = self._db.execute(
            "SELECT slug, owner_provider, owner_subject, owner_label, scale, timer_seconds, sound, "
            + ", ".join(JIRA_COLUMNS)
            + ", auto_reveal, queue_filter"
            + " FROM rooms WHERE slug = ?",
            (slug,),
        ).fetchone()
        if row is None:
            return None
        delegates = self._db.execute(
            "SELECT provider, identifier FROM delegates WHERE room = ?"
            " ORDER BY provider, identifier",
            (slug,),
        ).fetchall()
        return RoomRecord(
            slug=row[0],
            owner=(row[1], row[2]),
            owner_label=row[3],
            scale=_scale_from_json(row[4]),
            timer_seconds=row[5],
            sound=bool(row[6]),
            delegates=tuple(Delegate(p, i) for p, i in delegates),
            jira=JiraLink(*row[7:14]),
            auto_reveal=bool(row[14]),
            queue_filter=_filter_from_json(row[15]),
        )


class _Transaction:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def __enter__(self) -> None:
        self._db.execute("BEGIN IMMEDIATE")

    def __exit__(self, kind, value, tb) -> None:
        self._db.execute("ROLLBACK" if kind else "COMMIT")


def _filter_json(queue_filter: QueueFilter) -> str | None:
    """None for the default, so a room that never changed it follows a changed default."""
    return None if queue_filter.is_default else json.dumps(queue_filter.to_dict())


def _filter_from_json(text: str | None) -> QueueFilter:
    return QueueFilter() if text is None else QueueFilter.from_dict(json.loads(text))


def _scale_json(scale: Scale) -> str:
    return json.dumps(scale.to_dict())


def _scale_from_json(text: str) -> Scale:
    data = json.loads(text)
    if data["kind"] == "fibonacci":
        # Owners cannot edit Fibonacci, so rooms always get the current list of cards.
        return fibonacci()
    cards = [
        Card(c["label"], None if c["value"] is None else float(c["value"])) for c in data["cards"]
    ]
    return validated(data["kind"], cards)
