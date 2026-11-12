# Scrum poker admin guide

This guide is for whoever installs and looks after the server. It covers the sign-in and Jira
apps, every setting, who may create rooms, day-to-day operations and troubleshooting. For
using the app itself, see the [user guide](user-guide.md).

The first installation is a step-by-step in the README: [Deploying](../README.md#deploying).

## How it fits together

- **One container, one process.** The app serves the web page, its API and the live room
  connections. Live sessions (who is in a room, the cards, the counters) exist only in that
  process's memory.
- **One SQLite file** on a volume holds the room definitions: name, owner, delegates, settings,
  and each room's Jira connection with its refresh token encrypted.
- **A reverse proxy ends HTTPS** in front of the container. The provided setup uses Caddy,
  which also gets and renews the certificate.
- **Google and GitHub** sign in room owners and delegates. Players never sign in.
- **Jira Cloud**, through an Atlassian OAuth app: each room's owner connects their room to a
  board.

Run exactly one copy of the container with one worker. Two copies would split a room's
players between processes that can't see each other.

## The sign-in and Jira apps

All three use the app's public address in their callbacks. Plain `http://` addresses are
refused outside `localhost`.

### Google

1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials), set up
   the OAuth consent screen:
   - **Internal** if everyone who signs in is in your Google Workspace. No review needed.
   - **External** otherwise. Publish the app ("In production"): while it's in testing, only
     the test users you list can sign in. The app asks only for `openid email profile`, which
     don't need Google's verification.
2. Create an OAuth client ID of type **Web application** with this authorised redirect URI:
   `https://poker.nijalabs.com/auth/google/callback`
3. Put its ID and secret in `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

Google must report the email as verified, or sign-in is refused.

### GitHub

1. In [GitHub, Developer settings, OAuth Apps](https://github.com/settings/developers), create
   an app. Homepage `https://poker.nijalabs.com`, callback
   `https://poker.nijalabs.com/auth/github/callback`. Create it under your organisation if
   you'd rather the org owned it.
2. Generate a client secret, and put the ID and secret in `GITHUB_CLIENT_ID` and
   `GITHUB_CLIENT_SECRET`.

The app asks for `read:user`, plus `read:org` when the allowlist has a `github-org:` entry. If
that organisation restricts third-party OAuth apps, an org owner must approve this app, or the
membership check fails and those people can't create rooms.

You can enable Google, GitHub or both. With neither, nobody can sign in.

### Atlassian (Jira Cloud)

1. In the [Atlassian developer console](https://developer.atlassian.com/console/myapps/),
   create an **OAuth 2.0 integration**.
2. Under **Permissions**, add the Jira API and these granular scopes:
   - `read:board-scope:jira-software`
   - `read:board-scope.admin:jira-software`
   - `read:project:jira`
   - `read:issue-details:jira`
   - `write:issue:jira-software`
   - `read:me`

   The app also requests `offline_access` itself, for refresh tokens.
3. Under **Authorization**, set the callback URL to
   `https://poker.nijalabs.com/auth/atlassian/callback`.
4. Under **Distribution**, enable sharing if room owners other than the app's creator will
   connect Jira. A private app works only for the account that created it.
5. Put the client ID and secret in `ATLASSIAN_CLIENT_ID` and `ATLASSIAN_CLIENT_SECRET`, and set
   `TOKEN_ENCRYPTION_KEY`.

Room owners need a Jira account that can see the board and edit the tickets' estimates:
everything is read and written as them.

## Settings

The app reads its settings from environment variables. With Docker Compose, put them in
`.env` in the repository root; `.env.example` lists them with comments.

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_BASE_URL` | Yes | The public address, `https://poker.nijalabs.com`. Used for callbacks and redirects. Must be `https://` outside localhost. |
| `SESSION_SECRET` | Yes | Signs the sign-in cookie. At least 32 characters. |
| `TOKEN_ENCRYPTION_KEY` | With Jira | Encrypts the stored Jira refresh tokens. A Fernet key. |
| `ROOM_CREATOR_ALLOWLIST` | Yes, in practice | Who may create rooms. See below. Empty means nobody. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | One provider | Google sign-in. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | One provider | GitHub sign-in. |
| `ATLASSIAN_CLIENT_ID`, `ATLASSIAN_CLIENT_SECRET` | For Jira | The Atlassian app. Without them, rooms can't connect to Jira. |
| `DATABASE_PATH` | No | The SQLite file. The image and compose file use `/data/scrum-poker.sqlite3`. |
| `FORWARDED_ALLOW_IPS` | No | Proxies whose `X-Forwarded-Proto` the app believes, comma-separated, or `*`. Default `127.0.0.1`. The compose file sets `*`. |
| `PORT` | No | The port the container listens on. Default 8000. |
| `SITE_HOST` | No | Compose only: the hostname Caddy serves. Default `poker.nijalabs.com`. |
| `HTTP_PORT`, `HTTPS_PORT` | No | Compose only: the ports Caddy listens on. Defaults 80 and 443. Another HTTPS port also goes in `APP_BASE_URL` and the OAuth callbacks. |

Compose reads `SITE_HOST`, `HTTP_PORT` and `HTTPS_PORT` from `.env` only when started with
`docker compose --env-file ../.env up -d` from `deploy/`.

Generate the two secrets with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

```bash
docker run --rm python:3.13-slim sh -c "pip -q install cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

The app checks its settings at start-up and refuses to start with a clear message when one is
missing or wrong, for example "SESSION_SECRET is required outside localhost."

Variables starting `SCRUM_POKER_FAKE_` turn on a fake sign-in and a fake Jira for development.
The app refuses them outside localhost; never set them in production.

### Who may create rooms

`ROOM_CREATOR_ALLOWLIST` is a comma-separated list of entries:

| Entry | Who may create rooms |
| --- | --- |
| `*` | Anyone who signs in with Google or GitHub |
| `ana@example.com` | That Google account, by verified email |
| `github:ana-dev` | That GitHub user |
| `google-domain:nijalabs.com` | Anyone in that Google Workspace (by the account's Workspace, not the email address) |
| `github-org:acme` | Active members of that GitHub organisation |

For example: `ROOM_CREATOR_ALLOWLIST=google-domain:nijalabs.com,github:ana-dev`

The allowlist only controls creating rooms. Anyone can join a room as a player with its link,
and an owner can make anyone a delegate of their room.

GitHub organisation membership is checked at sign-in. Someone who leaves the organisation
keeps the right to create rooms until they sign out or their 30-day sign-in expires.

Restart the app after changing any setting:

```bash
cd deploy && docker compose --env-file ../.env up -d
```

## Operations

### Starting, stopping and logs

The commands in this guide run from `deploy/`, with `--env-file ../.env`. On a server set up
behind its own nginx ([README](../README.md#behind-an-existing-nginx)), run them from
`deploy/nginx/` with `--env-file ../../.env` instead; from `deploy/`, compose would also
start Caddy.

From `deploy/`:

```bash
docker compose ps
```

```bash
docker compose logs -f app
```

```bash
docker compose restart app
```

The container reports its health to Docker through `/healthz`. `docker compose ps` shows
`healthy` once the app is up.

### Upgrading

Upgrade between sessions: a restart ends every live session.

```bash
git pull
```

```bash
cd deploy && docker compose --env-file ../.env up -d --build
```

Rooms, settings, delegates and Jira connections are kept. People in a room at the time see
"Reconnecting…", and their page reconnects by itself once the app is back, but cards on the
table and the session counters are cleared. Points already confirmed are in Jira.

### Backups

The only data worth keeping is the SQLite file on the `rooms` volume. Take a consistent copy
while the app runs:

```bash
docker compose exec app python -c "import sqlite3; s = sqlite3.connect('/data/scrum-poker.sqlite3'); s.backup(sqlite3.connect('/data/backup.sqlite3'))"
```

```bash
docker compose cp app:/data/backup.sqlite3 ./scrum-poker-backup.sqlite3
```

Keep `TOKEN_ENCRYPTION_KEY` safe and apart from the backups. Without it, the backed-up Jira
connections can't be decrypted, and every owner has to reconnect Jira.

To restore, stop the app, copy the file back over `/data/scrum-poker.sqlite3` on the volume,
and start it again.

### Changing the secrets

| Changed | Effect |
| --- | --- |
| `SESSION_SECRET` | Everyone is signed out and signs in again. Rooms and Jira connections are unaffected. Do this if the secret may have leaked. |
| `TOKEN_ENCRYPTION_KEY` | Every room loses its Jira connection, and each owner must choose **Reconnect** in the room's settings. |
| The Atlassian client secret | Rotate it in the developer console, update `.env` and restart. Rooms keep their connections. |

### What the app stores

| Data | Where | Kept |
| --- | --- | --- |
| Room name, old names, scale, countdown and sound defaults | SQLite | Until the room is deleted |
| Owner's provider account ID and email or GitHub login | SQLite | Until the room is deleted |
| Delegates' Google emails and GitHub logins | SQLite | Until removed or the room is deleted |
| Jira refresh token (encrypted), Atlassian account email, site and board | SQLite | Until disconnected or the room is deleted |
| Votes, results, who is in a room, session counters | Memory | Until the session ends or the app restarts |
| A player's name and random player ID | That player's browser cookie | One year |
| A signed-in owner or delegate | Their browser cookie | 30 days, or until sign-out |

The app keeps no logs of votes. The container's access log records requests (addresses,
paths and status codes), including room names in the paths.

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| The container exits right after starting | A setting is missing or wrong. `docker compose logs app` shows which one. |
| Sign-in fails with a "redirect URI mismatch" error from Google or GitHub | The callback in the provider's app must be exactly `https://poker.nijalabs.com/auth/<provider>/callback`, and `APP_BASE_URL` must be `https://poker.nijalabs.com`. |
| Google sign-in works for you but not for colleagues | The consent screen is External and still in testing. Publish it, or add them as test users. |
| A signed-in person "cannot create rooms" | They're not on `ROOM_CREATOR_ALLOWLIST`. Add them and restart. For `github-org:`, check the organisation has approved the app. |
| The home page says "No sign-in provider is configured." | Neither Google nor GitHub is set up. |
| Room settings say "Jira is not set up on this server." | `ATLASSIAN_CLIENT_ID` and `ATLASSIAN_CLIENT_SECRET` aren't set. |
| Only you can connect Jira; other owners get an Atlassian error | Enable sharing in the Atlassian app's Distribution settings. |
| A room says "Jira no longer accepts this room's connection." | The refresh token expired (90 days unused), was revoked in Atlassian, or `TOKEN_ENCRYPTION_KEY` changed. The owner chooses **Reconnect**. |
| Confirming points fails on one board | The owner's Jira account can't edit that board's estimates, or the board's estimation field isn't set. Check the board's settings in Jira. |
| Pages keep redirecting, or everything shows "Reconnecting…" | The proxy isn't sending `X-Forwarded-Proto`, or `FORWARDED_ALLOW_IPS` doesn't include the proxy. Behind Caddy with the provided compose file both are set. |
| Players in the same room can't see each other | More than one copy of the app is running. Run one. |
| Caddy can't get a certificate | DNS for `poker.nijalabs.com` must point at the server, and ports 80 and 443 must be open to the internet (or, with other ports set, public port 80 or 443 must still reach Caddy). `docker compose logs caddy` says what failed. |
| Mini mode opens an ordinary window instead of floating | Expected in Safari. In other browsers the floating window needs HTTPS. |
