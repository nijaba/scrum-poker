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

Cases: RE-01, RE-03, RE-04, RE-05, RE-06, RR-01 to RR-05, RQ-01 to RQ-06, RC-01, RC-02, RC-03, RS-01 to RS-05, RX-01, RX-03, RX-04.

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
- [x] Little extras: coffee break, splitting hint, nobody knows, perfect consensus, arcade deck

Cases: RE-02, RR-06, RQ-07, RC-04, RX-02, AR-14, AR-15, AR-16, JC-14 (against the fake backlog), EE-01 to EE-12. Manual: RC-05, RC-06, RC-07.
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
- [x] Menu behind your name in the room header: Your rooms, Room settings (owner), Log out
- [x] Refuse a name already at the table

Cases: AR-01, AR-02, AR-04 to AR-13, AR-17 to AR-19 (AR-19 in the browser), UM-01 to UM-07, PK-03, PK-05, PK-06, HS-04, HS-05 (Google and GitHub). Manual: AR-03.

## Step 4: Jira Cloud

Design: "Jira Cloud".

- [x] Atlassian OAuth with the seven scopes, one connection per room set up by the owner; refresh tokens stored encrypted and rotated
- [x] Pick site and board in room settings
- [x] Load the board backlog with paging; build the queue and backlog counters
- [x] Leave epics, sub-tasks, started or resolved tickets and sprint tickets out of the queue and the counters
- [x] Write points through the board's estimation endpoint; advance only on success
- [x] Use the room's Jira connection; tell facilitators the owner must connect or reconnect when it is missing
- [x] Fake Jira for tests

Cases: JC-03, JC-04, JC-15 to JC-19, JC-07 to JC-10, JC-12, JC-13, HS-05 (Atlassian). Sandbox: JC-01, JC-02, JC-05, JC-06, JC-11.

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

## After step 6: queue filter

Design: "Queue filter". Decided by the owner on 2026-11-14: the queue rules become a per-room filter the owner sets, with the current rules as the default, an optional extra JQL, a preview, and re-estimation of tickets that already have an estimate.

- [x] Filter stored with the room and applied to the queue and counters
- [x] Extra JQL; preview; Reload backlog between tickets
- [x] Queue filter section and preview on the settings page

Cases: QF-01 to QF-10 and QF-12. Sandbox: QF-11, run by the owner on 2026-11-14 against the production Jira Cloud site: passed (the extra JQL narrows the backlog, and a typo shows Jira's message).

## After step 6: demo rooms

Design: "Demo rooms". Decided by the owner on 2026-11-13: one private room per visitor, a realistic team of bots, an in-memory sample backlog, off unless `DEMO_ROOMS=1`.

- [x] Demo rooms in memory, with a sample backlog and bots
- [x] Try a demo on the home page; demo banner and Add a bot in the room

- [x] `DEMO_MAX_ROOMS` and `DEMO_IDLE_SECONDS` settings; a friendly come-back-later note when every demo room is taken

- [x] The demo banner gives the configured idle time

- [x] Take the tour in the demo banner; Watch the video beside Try a demo
- [x] `TOUR_VIDEO` setting for the Watch the video button

Cases: DR-01 to DR-17.

## After step 6: phones and dark mode

Design: "Phones" and "Dark mode". Decided by the owner on 2026-11-14 from the mock-ups: a compact phone layout with the hand docked at the bottom and the facilitator's next step beside it (option A), a Remote view players can turn on (option B), and a dark palette that follows the device, with a Theme choice in the menu and the footer. Desktop layout unchanged.

- [x] Dark palette, Theme choice, applied before the page draws
- [x] Phone layout: one-row header, compact table, docked hand and facilitator actions, more-controls sheet
- [x] Remote view for players

Cases: PH-01 to PH-05, RV-01 to RV-03, TH-01 to TH-03. Manual: PH-06 and TH-04, run by the owner on 2026-11-15: passed.

## After step 6: tour and guide pictures

Design: "Tour" and "Guide pictures". Decided by the owner on 2026-11-15: a tour offered once on first visit, then on demand from the menu and the footer, with steps by role, and scripted screenshots in the guides.

- [x] Tour of the room by role, offered once, Tour in the menu and the footer
- [x] Tour of the settings page for owners
- [x] `scripts/guide_pictures.py` and pictures in the user and admin guides
- [x] The narrated tour video, served by the app at `/tour.mp4` for the README

Cases: TR-01 to TR-06, GP-01 to GP-03. Manual: TR-07, run by the owner on 2026-11-15: passed.

## After step 6: co-owners and handing a room over

Design: "Co-owners and handing a room over". Decided by the owner on 2026-11-16: a delegate can be a co-owner with every right but deleting and handing over the room; the owner offers the room to a delegate, who accepts; the old owner stays as a co-owner; the Jira connection stays, with a note to reconnect.

- [x] Delegate roles: Facilitator and Co-owner; co-owners manage the room and its Jira connection
- [x] Ownership offers: make, cancel, accept, decline, lapse after 7 days
- [x] Settings, home page and room show roles and offers

Cases: CO-01 to CO-07, OT-01 to OT-06.

## After step 6: a new home page

Design: "Rooms". Decided by the owner on 2026-11-16: make the home page more attractive.

- [x] A hero in the table's green, with a fanned hand of cards and the demo up front when signed out
- [x] The four steps of a session under the sign-in
- [x] Rooms as cards, with Create a room in the same grid

Cases: HP-01 to HP-03.

## After step 6: documentation checks and CI

Decided by the owner on 2026-11-16: run a short CI for documentation-only changes, check the documentation's links and the project page build, and audit the dependencies.

- [x] A short CI for documentation-only changes, with the required checks still reported
- [x] Links in the Markdown files, and the project page build, checked by tests
- [x] Python 3.13 required, as CI, Docker and development use
- [x] A dependency audit workflow: pip-audit and npm audit

Cases: DC-01 to DC-03.

## After step 6: a fuller tour and owner onboarding

Design: "Tour". Decided by the owner on 2026-11-16: explain more in the room tour, and help owners set a room up.

- [x] Show me more: a second part of the room tour, by role
- [x] A richer settings tour
- [x] The setup checklist on a room's settings page

Cases: TR-08 to TR-10, GS-01, GS-02.

## After step 6: common phone sizes

Decided by the owner on 2026-11-16: check every screen at common phone sizes in the local checks and CI, as long as it costs under 30 seconds (it takes about 10).

- [x] Every screen at six common phone sizes, from 360 × 800 to 430 × 932

Cases: PH-07. Manual: PH-06 stays the check on real phones.
