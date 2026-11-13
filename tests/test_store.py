"""The SQLite room store, at Integration level against a real file.

PK-03 (restart with the volume attached) is proved here by reopening the file.
PK-05 (no session data in the file) is proved in test_rooms_api.py after a live session.
"""

import sqlite3

import pytest

from app.room.scales import custom, fibonacci, tshirt
from app.store.rooms import Delegate, RoomRecord, RoomStore, SlugTaken

OWNER = ("google", "g-owner")


def record(slug="team-a", **kw):
    return RoomRecord(slug=slug, owner=OWNER, owner_label="owner@example.com", **kw)


@pytest.fixture
def path(tmp_path):
    return tmp_path / "data" / "rooms.sqlite3"


@pytest.fixture
def store(path):
    s = RoomStore(path)
    yield s
    s.close()


def test_create_and_read_a_room(store):
    store.create(record())

    room = store.get("team-a")
    assert room.slug == "team-a"
    assert room.owner == OWNER
    assert room.scale == fibonacci()
    assert room.timer_seconds == 30
    assert room.sound is False
    assert room.delegates == ()


def test_slugs_are_unique(store):
    store.create(record())
    with pytest.raises(SlugTaken):
        store.create(record())


def test_pk03_rooms_delegates_and_settings_survive_a_restart(path):
    first = RoomStore(path)
    first.create(record())
    first.update(
        "team-a",
        scale=tshirt({"S": 2, "M": 3}),
        timer_seconds=45,
        sound=True,
        delegates=[Delegate("google", "ben@example.com"), Delegate("github", "chloe-dev")],
    )
    first.close()

    again = RoomStore(path)
    room = again.get("team-a")
    assert room.scale == tshirt({"S": 2, "M": 3})
    assert room.timer_seconds == 45
    assert room.sound is True
    assert room.delegates == (
        Delegate("github", "chloe-dev"),
        Delegate("google", "ben@example.com"),
    )
    again.close()


def test_custom_scale_round_trips_exactly(store):
    store.create(record(scale=custom(["1", "2", "4", "?", {"label": "big", "value": 20}])))
    assert store.get("team-a").scale == custom(["1", "2", "4", "?", {"label": "big", "value": 20}])


def test_rs05_a_room_saved_with_an_older_fibonacci_list_gets_the_current_cards(store, path):
    store.create(record())
    old = (
        '{"kind": "fibonacci", "cards": ['
        + ", ".join(
            f'{{"label": "{label}", "value": {label}}}'
            for label in ("1", "2", "3", "5", "8", "13", "21")
        )
        + ', {"label": "?", "value": null}]}'
    )
    with sqlite3.connect(path) as db:
        db.execute("UPDATE rooms SET scale = ? WHERE slug = 'team-a'", (old,))

    assert store.get("team-a").scale == fibonacci()
    assert [c.label for c in store.get("team-a").scale.cards][-3:] == ["34", "55", "?"]


def test_rename_keeps_the_old_slug_as_a_redirect(store):
    store.create(record())
    store.update("team-a", delegates=[Delegate("google", "ben@example.com")])

    store.rename("team-a", "alpha")

    assert store.get("team-a") is None
    assert store.resolve("team-a") == "alpha"
    assert store.resolve("alpha") == "alpha"
    assert store.get("alpha").delegates == (Delegate("google", "ben@example.com"),)
    with pytest.raises(SlugTaken):
        store.create(record("team-a"))  # a retired name stays reserved


def test_renaming_twice_redirects_every_old_name(store):
    store.create(record())
    store.rename("team-a", "alpha")
    store.rename("alpha", "beta")

    assert store.resolve("team-a") == "beta"
    assert store.resolve("alpha") == "beta"


def test_a_room_can_take_back_its_own_old_name(store):
    store.create(record())
    store.rename("team-a", "alpha")
    store.rename("alpha", "team-a")

    assert store.resolve("team-a") == "team-a"
    assert store.resolve("alpha") == "team-a"


def test_rename_onto_another_room_is_rejected(store):
    store.create(record())
    store.create(record("team-b"))
    with pytest.raises(SlugTaken):
        store.rename("team-a", "team-b")


def test_delete_removes_the_room_its_delegates_and_redirects(store, path):
    store.create(record())
    store.update("team-a", delegates=[Delegate("google", "ben@example.com")])
    store.rename("team-a", "alpha")

    store.delete("alpha")

    assert store.resolve("alpha") is None
    assert store.resolve("team-a") is None
    db = sqlite3.connect(path)
    assert db.execute("select count(*) from delegates").fetchone() == (0,)
    db.close()
    store.create(record("team-a"))  # the name is free again


def test_rooms_for_an_account(store):
    store.create(record("mine"))
    store.create(RoomRecord("theirs", ("github", "77"), "someone"))
    store.update("theirs", delegates=[Delegate("google", "owner@example.com")])
    store.create(RoomRecord("other", ("github", "77"), "someone"))

    from app.auth.identity import Identity

    me = Identity("google", "g-owner", "Olive", email="owner@example.com")
    assert [(r.slug, access) for r, access in store.rooms_for(me)] == [
        ("mine", "owner"),
        ("theirs", "delegate"),
    ]


def test_the_file_holds_only_room_definitions(store, path):
    store.create(record())
    db = sqlite3.connect(path)
    tables = {row[0] for row in db.execute("select name from sqlite_master where type='table'")}
    db.close()
    assert tables == {"rooms", "delegates", "slug_aliases"}


# Step 4: each room's Jira connection


def test_a_room_keeps_its_jira_connection_and_board(path):
    from app.store.rooms import JiraLink

    first = RoomStore(path)
    first.create(record())
    first.set_jira_connection("team-a", token="ciphertext-1", email="owner@example.com")
    first.set_jira_board(
        "team-a",
        cloud_id="cloud-1",
        site_url="https://shop.atlassian.net",
        site_name="shop",
        board_id=7,
        board_name="SHOP board",
    )
    first.set_jira_token("team-a", "ciphertext-2")
    first.close()

    again = RoomStore(path)
    jira = again.get("team-a").jira
    assert jira == JiraLink(
        token="ciphertext-2",
        email="owner@example.com",
        cloud_id="cloud-1",
        site_url="https://shop.atlassian.net",
        site_name="shop",
        board_id=7,
        board_name="SHOP board",
    )
    assert jira.connected and jira.has_board
    again.clear_jira("team-a")
    assert again.get("team-a").jira == JiraLink()
    again.close()


def test_reconnecting_keeps_the_board(store):
    store.create(record())
    store.set_jira_connection("team-a", token="t1", email="a@example.com")
    store.set_jira_board("team-a", "c", "https://x.atlassian.net", "x", 1, "B")
    store.set_jira_connection("team-a", token="t2", email="a@example.com")

    assert store.get("team-a").jira.board_id == 1


def test_version_1_files_are_upgraded(path):
    import sqlite3 as sq

    from app.store.rooms import SCHEMA

    path.parent.mkdir(parents=True, exist_ok=True)
    db = sq.connect(path)
    db.executescript(SCHEMA + "PRAGMA user_version = 1;")
    import json

    db.execute(
        "INSERT INTO rooms VALUES ('old', 'google', 'g', 'o@x.com', ?, 30, 0, '2026-01-01')",
        (json.dumps(fibonacci().to_dict()),),
    )
    db.commit()
    db.close()

    store = RoomStore(path)
    assert store.get("old").jira.connected is False
    store.set_jira_connection("old", token="t", email="o@x.com")
    assert store.get("old").jira.token == "t"
    store.close()
