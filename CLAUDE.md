# Scrum poker

A multiplayer scrum poker web app that walks a team through the unestimated tickets of a Jira Cloud backlog, in rank order, and writes the agreed story points back to Jira.

The app was built in the six steps of `docs/build-plan.md`, all done, and has grown since in the plan's "After step 6" sections. Production runs the latest release at `https://poker.nijalabs.com`; guides and examples use `poker.example.com` for a self-hoster's own host.

## Firm constraints

These were decided by the owner. Do not trade them away; ask first if one blocks you.

- Python backend. No Go, no Node server.
- One lightweight container, one process. No external database, cache or queue.
- No session storage. Votes, results and session counters live in memory only.
- Room definitions persist in one SQLite file on a mounted volume.
- HTTPS only in deployment. `localhost` is the one exception.

## Commands

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"      # install the app and dev tools
pytest                       # run all tests
pytest -k re01               # run the tests for one test-plan case
ruff check .                 # lint
ruff format .                # format
pip-audit --skip-editable    # known vulnerabilities in the Python dependencies
(cd frontend && npm audit)   # and in the front-end packages
gitleaks git .               # secrets anywhere in the git history; false positives go in .gitleaksignore
trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed scrum-poker   # the built image
uvicorn app.main:app --reload --port 8000   # dev server, single worker
SCRUM_POKER_FAKE_BACKLOG=tests/fixtures/fake_backlog.json SCRUM_POKER_FAKE_SSO=1 SCRUM_POKER_FAKE_JIRA=1 \
  ROOM_CREATOR_ALLOWLIST=owner@example.com uvicorn app.main:app --port 8000  # local dev: fake sign-in and fake Jira
(cd frontend && npm install)                 # front-end packages
(cd frontend && npm run build)               # build frontend/dist, served by the Python app; E2E tests need it
(cd frontend && npm run dev)                 # Vite on :5173, proxying /api and /ws to :8000
(cd frontend && npm run check)               # svelte-check type check
pytest tests/e2e                             # Playwright E2E tests; they skip if frontend/dist is missing
pytest -k ph07                               # every screen at common phone sizes, about 10 s
docker build -t scrum-poker .                # the production image; pytest's image tests skip without Docker
(cd deploy && docker compose --env-file ../.env up -d --build)  # dedicated host: Caddy in front, see README "Deploying"
(cd deploy/nginx && docker compose --env-file ../../.env up -d --build)  # production: behind the host's nginx, from a release tag
scripts/release.sh 1.2.0                     # tag and publish a release, once a PR has set that version in pyproject.toml
```

With the fakes, open `/`, sign in as Olive Owner, create a room, then in its settings Connect Jira, accept, and pick SHOP board.

## Stack

- FastAPI on uvicorn for HTTP and WebSockets
- Authlib for OAuth (Google and GitHub sign-in, Atlassian for Jira); its client uses httpx2
- httpx2 (a runtime dependency) for Jira calls, Authlib's client and the test client. The design says httpx; httpx2 is its successor, and the current Starlette test client asks for it
- nh3 to sanitize Jira's rendered descriptions; cryptography (Fernet) to encrypt stored refresh tokens
- Standard-library `sqlite3` for the room store
- Front end: a small single-page app in Svelte with TypeScript, built with Vite, served as static files by the Python app

Add a dependency only when the current build step needs it, and say so in your summary.

## Layout

```
app/            Python package; app/main.py holds create_app()
tests/          pytest tests; tests/fixtures/fake_backlog.json is the shared fake backlog
frontend/       single-page app (created in step 2)
docs/           design.md, test-plan.md, build-plan.md, mockups/
deploy/         docker-compose.yml and Caddyfile; deploy/nginx/ for a host with its own nginx (production)
Dockerfile      multi-stage: Node builds frontend/, slim Python serves it
.claude/        settings, path-scoped rules, the /next-step skill
```

Packages inside `app/`: `room/` (engine), `store/` (SQLite), `auth/` (sign-in, access), `jira/` (client, connect flow, fakes), `demo/` (demo rooms, bots, sample backlog).

## How to work here

1. Follow `docs/build-plan.md` in order. Finish a step before starting the next.
2. Read the matching sections of `docs/design.md` before writing code. It is the source of truth for behaviour.
3. Write tests first. Every case in `docs/test-plan.md` has an ID such as `RE-01`; put the ID in the test name (`test_re01_votes_stay_hidden`) so `pytest -k re01` finds it.
4. Before saying a step is done, run what CI runs: `pytest`, `ruff check .`, `ruff format --check .` and `(cd frontend && npm run check)`. After front-end changes, also run the browser tests in Firefox and WebKit (`pytest tests/e2e --browser firefox`, then `webkit`).
5. Tick the boxes in `docs/build-plan.md` as cases pass.
6. If the design is silent or wrong, stop and ask. When the owner decides, update `docs/design.md` in the same change.

`/next-step` picks up the next unfinished step and follows this routine.

## Rules that must always hold

Room engine

- The server is the only authority. Each live room is one asyncio task that owns its state and reads commands from a queue.
- Never send a vote's value to any client before reveal. Before reveal a client learns only who has voted.
- A round is `voting -> revealed -> confirmed`. Votes after reveal are rejected.
- The countdown is a server-side deadline. Expiry signals "time's up" and never reveals.
- Session counters are derived from per-ticket results, so a rewind and re-estimate never double counts.
- Facilitator commands from a player connection are rejected.

Jira

- The queue is the board backlog's tickets in Jira's rank order, through the room's queue filter. By default only tickets with no estimate, of standard work types (no epics or sub-tasks), in Jira's To Do status category, with no resolution enter it or the counters; the owner or a co-owner can change that in the room settings (design.md, "Queue filter"). Epics, and tickets in an active or future sprint, never enter.
- Write points through the board's estimation endpoint. The room advances only after Jira accepts the write.
- Each room has one Jira connection, set up by its owner or a co-owner. The backlog loads and every write goes through it, so Jira records writes under whoever connected it.
- Refresh tokens rotate: store the new one after every refresh, encrypted.

Auth and storage

- Owners and delegates sign in with Google or GitHub. Players never sign in.
- Match delegates on verified email or GitHub login, never on display name.
- The owner and co-owners change room settings, delegates and the Jira connection. Only the owner deletes the room or hands it over (design.md, "Co-owners and handing a room over").
- The SQLite file never holds votes, results or session counters.
- Session and player cookies are marked Secure outside `localhost`.

Runtime

- Run exactly one uvicorn worker. Live rooms sit in process memory.

## Decided

- Hostname: `poker.nijalabs.com`, behind the host's existing nginx (`deploy/nginx/`, app on `127.0.0.1:8100`). `deploy/` with Caddy stays for a dedicated host. Guides use `poker.example.com`; the mock-ups show `[YOUR DOMAIN]`.
- Versions: semantic versioning from 1.0.0, `pyproject.toml` the one source, releases tagged `vX.Y.Z` by `scripts/release.sh`, production deployed from a release tag (design.md, "Versions and releases").

## Assumptions already in the design

Change these only if the owner says so.

- Delegates can use Reset room, like the other session controls.
- Reset room keeps the queue position and session counters.
- Consensus means everyone chose the same card; otherwise show the most-chosen card and its count.
- TLS ends at a reverse proxy or load balancer in front of the container.

## References

- `docs/design.md`: architecture and behaviour
- `docs/test-plan.md`: test cases with IDs, expected results and levels
- `docs/build-plan.md`: the six build steps, the work after them, and which cases gate each part
- `docs/mockups/`: static HTML mock-ups of the four screens, with the colours and type they use
