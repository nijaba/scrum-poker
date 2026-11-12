# Build plan

Six steps, in order. A step is done when its boxes are ticked and its test-plan cases pass.
Case IDs refer to `docs/test-plan.md`. Manual and Sandbox cases are run by a person; list them in your summary instead of ticking them yourself.

## Step 0: skeleton (done)

- [x] Python package, FastAPI app factory and `/healthz`
- [x] pytest and ruff set up, with one passing test
- [x] Fake backlog fixture: 12 tickets, 8 without an estimate, 4 with estimates totalling 16 points

## Step 1: room engine against the fake backlog

Design: "Room engine" in `docs/design.md`.

- [x] Scales: Fibonacci, T-shirt with value mapping, custom list; cards with a label and an optional numeric value
- [x] Round state machine: voting, revealed, confirmed; restart vote
- [x] Results on reveal: average, median, consensus
- [x] Queue with cursor and per-ticket results; skip and rewind; session and backlog counters
- [x] Countdown as a server-side deadline, 30 s default, settable; sound setting carried in the room state
- [x] One asyncio task per live room, commands through a queue, per-client snapshots that hide votes before reveal
- [x] WebSocket endpoint for players and facilitators (facilitator identity is stubbed until step 3)
- [x] Room reset: re-seat only clients that answer the check-in

Cases: RE-01, RE-03, RE-04, RE-05, RE-06, RR-01 to RR-05, RQ-01 to RQ-06, RC-01, RC-02, RC-03, RS-01 to RS-04, RX-01, RX-03, RX-04.

## Step 2: room UI

Design: "Room engine", "Ticket card", "Auth, rooms and delegates" (players). Mock-ups: `docs/mockups/`.
Front-end framework: Svelte with TypeScript (owner, 2026-11-11).

- [x] Vite project in `frontend/`, built output served by the Python app
- [x] Join screen: name prompt, player cookie with name and random ID
- [x] Room screen while voting: ticket card, players with face-down cards, card row, counters
- [x] Room screen after reveal: face-up cards, average, median, consensus, final-points picker
- [x] Facilitator panel: countdown, reveal, restart, confirm, skip, rewind, reset room
- [x] Countdown rendering and synthesized sound with a local mute
- [x] Playwright set up with one facilitator and several players

Cases: RE-02, RR-06, RQ-07, RC-04, RX-02, AR-14, AR-15, AR-16, JC-14 (against the fake backlog). Manual: RC-05, RC-06, RC-07.
Manual RC-05, RC-06 and RC-07 passed on 2026-11-11, run by the owner.

## Step 3: SSO, persistent rooms and delegates

Design: "Auth, rooms and delegates", "What is stored where".

- [x] Google and GitHub sign-in with Authlib; signed session cookie
- [x] Allowlist of accounts that may create rooms
- [x] SQLite room store: slug, owner, delegates, scale, timer default, sound setting
- [x] Create, configure and delete rooms; unique short names; `/r/<slug>` links
- [x] Delegates per room by Google email or GitHub username
- [x] Room settings screen (see `docs/mockups/room-settings.html`)
- [x] Fake SSO provider for tests

Cases: AR-01, AR-02, AR-04 to AR-13, PK-03, PK-05, PK-06, HS-04, HS-05 (Google and GitHub). Manual: AR-03.

## Step 4: Jira Cloud

Design: "Jira Cloud".

- [x] Atlassian OAuth with the seven scopes, one connection per room set up by the owner; refresh tokens stored encrypted and rotated
- [x] Pick site and board in room settings
- [x] Load the board backlog with paging; build the queue and backlog counters
- [x] Leave epics out of the queue and the counters
- [x] Write points through the board's estimation endpoint; advance only on success
- [x] Use the room's Jira connection; tell facilitators the owner must connect or reconnect when it is missing
- [x] Fake Jira for tests

Cases: JC-03, JC-04, JC-15, JC-07 to JC-10, JC-12, JC-13, HS-05 (Atlassian). Sandbox: JC-01, JC-02, JC-05, JC-06, JC-11.

## Step 5: mini window

Design: "Mini mode". Mock-up: `docs/mockups/mini-window.html`.

- [x] Compact view: ticket key, countdown, card row, voted count
- [x] Document Picture-in-Picture window where the browser supports it
- [x] Popup fallback with the same view

Cases: MM-02, MM-03, MM-04. Manual: MM-01, MM-05, MM-06, MM-07.

## Step 6: Dockerfile and deployment notes

Design: "HTTPS", "Packaging and build order".
Ask the owner for the hostname before writing the deployment notes.

- [x] Multi-stage Dockerfile: Node stage builds the front end, slim Python image serves it
- [x] Configuration from environment variables; SQLite file on one volume; single uvicorn worker
- [x] HTTPS behind a proxy: forwarded-protocol header, redirect from HTTP, HSTS, Secure cookies
- [x] Deployment notes in `README.md`

Cases: PK-01, PK-02, PK-04, HS-01, HS-02, HS-03.
