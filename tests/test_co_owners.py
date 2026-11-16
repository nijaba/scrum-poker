"""Co-owners and handing a room over, at Integration level.

Cases CO-01 to CO-05 and OT-01 to OT-05. CO-02 and OT-02's Jira part are in test_jira.py,
CO-06 in test_store.py, CO-07 and OT-06 in tests/e2e/test_co_owners_e2e.py.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from tests.identities import (
    DELEGATE,
    GH_DELEGATE,
    GH_OUTSIDER,
    OUTSIDER,
    OWNER,
    headers,
    open_ws,
)

ROOM = "/ws/rooms/team-a"
DEE = {"provider": "google", "identifier": "delegate@example.com"}
OCTO = {"provider": "github", "identifier": "octo-delegate"}


def api(client, method, path, identity=None, **kw):
    return client.request(method, path, headers=headers(client.app, identity), **kw)


def patch(client, body, identity=OWNER, slug="team-a"):
    return api(client, "PATCH", f"/api/rooms/{slug}", identity, json=body)


def set_delegates(client, *entries, identity=OWNER):
    response = patch(client, {"delegates": list(entries)}, identity)
    assert response.status_code == 200, response.text
    return response.json()


def co(entry):
    return {**entry, "role": "co_owner"}


def state(ws, predicate=lambda s: True):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and predicate(msg):
            return msg


def offer(client, entry=DEE, identity=OWNER):
    return api(client, "POST", "/api/rooms/team-a/ownership", identity, json=entry)


def answer(client, verb, identity):
    return api(client, "POST", f"/api/rooms/team-a/ownership/{verb}", identity, json={})


# Co-owners


def test_co01_a_co_owner_manages_the_room(client):
    body = set_delegates(client, co(DEE), OCTO)
    assert body["settings"]["delegates"] == [
        {"provider": "github", "identifier": "octo-delegate", "role": "facilitator"},
        {"provider": "google", "identifier": "delegate@example.com", "role": "co_owner"},
    ]

    seen = api(client, "GET", "/api/rooms/team-a", DELEGATE).json()
    assert seen["access"] == "co_owner"
    assert seen["settings"]["owner"] == "owner@example.com"

    assert patch(client, {"timer_seconds": 45}, DELEGATE).status_code == 200
    # Co-owners change delegates and their roles, including other co-owners.
    changed = set_delegates(client, co(DEE), co(OCTO), identity=DELEGATE)
    assert {d["role"] for d in changed["settings"]["delegates"]} == {"co_owner"}
    renamed = patch(client, {"slug": "team-z"}, DELEGATE)
    assert renamed.status_code == 200 and renamed.json()["slug"] == "team-z"
    assert client.app.state.store.get("team-z").timer_seconds == 45

    assert api(client, "GET", "/api/rooms", DELEGATE).json() == [
        {"slug": "team-z", "access": "co_owner", "offer": None}
    ]


def test_co01_a_facilitator_delegate_still_cannot_manage(client):
    set_delegates(client, co(DEE), OCTO)

    assert patch(client, {"timer_seconds": 45}, GH_DELEGATE).status_code == 403
    assert api(client, "DELETE", "/api/rooms/team-a", GH_DELEGATE).status_code == 403
    assert api(client, "GET", "/api/rooms/team-a", GH_DELEGATE).json() == {
        "slug": "team-a",
        "access": "delegate",
    }


def test_co03_a_co_owner_cannot_delete_or_hand_the_room_over(client):
    set_delegates(client, co(DEE), OCTO)

    assert api(client, "DELETE", "/api/rooms/team-a", DELEGATE).status_code == 403
    assert offer(client, OCTO, DELEGATE).status_code == 403
    assert api(client, "DELETE", "/api/rooms/team-a/ownership", DELEGATE).status_code == 403

    room = client.app.state.store.get("team-a")
    assert room is not None and room.owner == OWNER.key and room.offer is None


def test_co04_a_role_change_reaches_the_live_room(client):
    set_delegates(client, DEE)
    with open_ws(client, ROOM, DELEGATE, ("pd", "Dee")) as ws:
        snap = state(ws, lambda s: s["you"]["seated"])
        assert (snap["you"]["access"], snap["you"]["role"]) == ("delegate", "facilitator")

        set_delegates(client, co(DEE))
        snap = state(ws, lambda s: s["you"]["access"] == "co_owner")
        assert snap["you"]["role"] == "facilitator"

        set_delegates(client, DEE)
        state(ws, lambda s: s["you"]["access"] == "delegate")


def test_co05_roles_are_checked(client):
    for role in ("owner", "admin", "", None, 3):
        assert patch(client, {"delegates": [{**DEE, "role": role}]}).status_code == 422
    body = set_delegates(client, DEE)
    assert body["settings"]["delegates"][0]["role"] == "facilitator"


# Handing the room over


def test_ot01_the_owner_offers_the_room_to_a_delegate(client):
    set_delegates(client, DEE, OCTO)

    response = offer(client)
    assert response.status_code == 200, response.text
    made = response.json()["settings"]["offer"]
    assert (made["provider"], made["identifier"]) == ("google", "delegate@example.com")
    assert made["expires_at"]

    # The delegate sees it on the home page, on the room and in the live room.
    assert api(client, "GET", "/api/rooms", DELEGATE).json() == [
        {"slug": "team-a", "access": "delegate", "offer": {"from": "owner@example.com"}}
    ]
    assert api(client, "GET", "/api/rooms/team-a", DELEGATE).json()["offer"] == {
        "from": "owner@example.com"
    }
    with open_ws(client, ROOM, DELEGATE) as ws:
        assert state(ws)["you"]["offer"] == {"from": "owner@example.com"}
    with open_ws(client, ROOM, GH_DELEGATE) as ws:
        assert state(ws)["you"]["offer"] is None

    # A new offer replaces it.
    offer(client, OCTO)
    assert api(client, "GET", "/api/rooms", DELEGATE).json()[0]["offer"] is None
    assert api(client, "GET", "/api/rooms", GH_DELEGATE).json()[0]["offer"] == {
        "from": "owner@example.com"
    }


def test_ot02_accepting_makes_the_delegate_the_owner(client):
    set_delegates(client, DEE, OCTO)
    offer(client)
    with (
        open_ws(client, ROOM, OWNER, ("po", "Olive")) as olive,
        open_ws(client, ROOM, DELEGATE, ("pd", "Dee")) as dee,
    ):
        state(olive, lambda s: s["you"]["seated"])
        state(dee, lambda s: s["you"]["seated"])

        response = answer(client, "accept", DELEGATE)
        assert response.status_code == 200, response.text
        assert response.json()["access"] == "owner"

        assert state(dee, lambda s: s["you"]["access"] == "owner")["you"]["offer"] is None
        assert state(olive, lambda s: s["you"]["access"] == "co_owner")["you"]["seated"]

    room = client.app.state.store.get("team-a")
    assert room.owner == DELEGATE.key
    assert room.owner_label == "delegate@example.com"
    assert room.offer is None
    assert sorted((d.identifier, d.role) for d in room.delegates) == [
        ("octo-delegate", "facilitator"),
        ("owner@example.com", "co_owner"),
    ]
    # The new owner can now delete the room; the old owner cannot.
    assert api(client, "DELETE", "/api/rooms/team-a", OWNER).status_code == 403
    assert api(client, "GET", "/api/rooms", OWNER).json() == [
        {"slug": "team-a", "access": "co_owner", "offer": None}
    ]


def test_ot02_a_github_delegate_becomes_owner_by_account_id(client):
    set_delegates(client, OCTO)
    offer(client, OCTO)
    assert answer(client, "accept", GH_DELEGATE).status_code == 200
    room = client.app.state.store.get("team-a")
    assert room.owner == GH_DELEGATE.key
    assert room.owner_label == "octo-delegate"
    # The match is on the account ID now: a later rename on GitHub keeps ownership.
    from app.auth.identity import Identity

    renamed = Identity("github", GH_DELEGATE.subject, "Octo", login="octo-renamed")
    assert api(client, "GET", "/api/rooms/team-a", renamed).json()["access"] == "owner"


def test_ot03_declining_or_cancelling_changes_nothing_else(client):
    set_delegates(client, DEE)
    offer(client)
    assert answer(client, "decline", DELEGATE).status_code == 204
    room = client.app.state.store.get("team-a")
    assert room.offer is None and room.owner == OWNER.key
    assert [(d.identifier, d.role) for d in room.delegates] == [
        ("delegate@example.com", "facilitator")
    ]

    offer(client)
    assert api(client, "DELETE", "/api/rooms/team-a/ownership", OWNER).status_code == 204
    assert client.app.state.store.get("team-a").offer is None
    assert answer(client, "accept", DELEGATE).status_code == 409


def test_ot04_an_offer_lapses_after_seven_days(client, settings):
    set_delegates(client, DEE)
    offer(client)
    old = (datetime.now(UTC) - timedelta(days=7, minutes=1)).isoformat(timespec="seconds")
    db = sqlite3.connect(settings.database_path)
    db.execute("UPDATE rooms SET offer_at = ? WHERE slug = 'team-a'", (old,))
    db.commit()
    db.close()

    assert api(client, "GET", "/api/rooms", DELEGATE).json()[0]["offer"] is None
    assert api(client, "GET", "/api/rooms/team-a", OWNER).json()["settings"]["offer"] is None
    assert answer(client, "accept", DELEGATE).status_code == 409
    assert client.app.state.store.get("team-a").owner == OWNER.key


def test_ot05_only_the_right_people_make_or_answer_offers(client):
    set_delegates(client, DEE, OCTO)

    # Only the owner offers, and only to a delegate.
    assert offer(client, OCTO, DELEGATE).status_code == 403
    assert offer(client, OCTO, OUTSIDER).status_code == 403
    assert offer(client, OCTO, None).status_code == 401
    for entry in (
        {"provider": "google", "identifier": "outsider@example.org"},
        {"provider": "github", "identifier": "delegate@example.com"},
        {"provider": "google"},
    ):
        assert offer(client, entry).status_code == 422
    assert client.app.state.store.get("team-a").offer is None

    offer(client)
    # Only the offered account answers.
    for identity in (GH_DELEGATE, OUTSIDER, GH_OUTSIDER, OWNER):
        assert answer(client, "accept", identity).status_code == 403
        assert answer(client, "decline", identity).status_code == 403
    assert answer(client, "accept", None).status_code == 401
    # Only the owner cancels.
    assert api(client, "DELETE", "/api/rooms/team-a/ownership", DELEGATE).status_code == 403
    assert client.app.state.store.get("team-a").offer is not None

    # Removing the offered delegate cancels the offer.
    set_delegates(client, OCTO)
    assert client.app.state.store.get("team-a").offer is None
    assert answer(client, "accept", DELEGATE).status_code == 409


def test_ot05_ownership_writes_refuse_other_sites(client):
    set_delegates(client, DEE)
    response = client.post(
        "/api/rooms/team-a/ownership",
        json=DEE,
        headers={**headers(client.app, OWNER), "origin": "https://evil.example.org"},
    )
    assert response.status_code == 403
