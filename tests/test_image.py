"""The container image: case PK-01, at Integration level.

Builds the Dockerfile from this checkout and starts it from environment variables
alone, configured as production would be. Skips when Docker is not running.
"""

import json
import subprocess
import uuid

import pytest

from tests.container import build_image, container, free_port, get

SITE = "https://poker.example.com"
PRODUCTION = {
    "APP_BASE_URL": SITE,
    "SESSION_SECRET": "s" * 40,
    "ROOM_CREATOR_ALLOWLIST": "*",
    "GOOGLE_CLIENT_ID": "cid",
    "GOOGLE_CLIENT_SECRET": "secret",
    "ATLASSIAN_CLIENT_ID": "cid",
    "ATLASSIAN_CLIENT_SECRET": "secret",
    "TOKEN_ENCRYPTION_KEY": "Q2Ab0Sx4cX9u8pHkC3m1n0dJb3l6YVZ0b2dQb2tlcjE=",
    "FORWARDED_ALLOW_IPS": "*",  # the test plays the proxy
}


@pytest.fixture(scope="module")
def image() -> str:
    return build_image()


def test_pk01_image_builds_and_starts_from_environment_variables(image):
    with container(image, PRODUCTION, free_port()) as base:
        status, headers, body = get(f"{base}/", {"X-Forwarded-Proto": "https"})
        assert status == 200
        assert "<title>Scrum poker</title>" in body
        assert headers["Strict-Transport-Security"] == "max-age=31536000"

        assert get(f"{base}/api/me", {"X-Forwarded-Proto": "https"})[0] == 200

        # Plain HTTP goes to the configured https:// address.
        status, headers, _ = get(f"{base}/r/team-a", {"X-Forwarded-Proto": "http"})
        assert status == 308
        assert headers["Location"] == f"{SITE}/r/team-a"


def test_pk01_container_runs_one_worker_as_a_non_root_user(image):
    with container(image, PRODUCTION, free_port()) as base:
        name = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"publish={base.rsplit(':', 1)[1]}"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        user = subprocess.run(["docker", "exec", name, "id", "-u"], capture_output=True, text=True)
        # Every process in the container but this probe: uvicorn alone, as PID 1.
        probe = (
            "import json, os; me = os.getpid();"
            "print(json.dumps([open(f'/proc/{p}/cmdline','rb').read()"
            ".replace(b'\\0', b' ').decode()"
            " for p in os.listdir('/proc') if p.isdigit() and int(p) != me]))"
        )
        processes = subprocess.run(
            ["docker", "exec", name, "python", "-c", probe], capture_output=True, text=True
        )
    assert user.stdout.strip() != "0"
    names = json.loads(processes.stdout)
    assert len(names) == 1, names
    assert "uvicorn app.main:app" in names[0] and "--workers 1" in names[0], names


def test_pk01_container_refuses_to_start_without_its_secrets(image):
    missing = {k: v for k, v in PRODUCTION.items() if k != "SESSION_SECRET"}
    name = f"scrum-poker-test-{uuid.uuid4().hex[:8]}"
    command = ["docker", "run", "--name", name]
    for key, value in missing.items():
        command += ["-e", f"{key}={value}"]
    try:
        done = subprocess.run([*command, image], capture_output=True, text=True, timeout=60)
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    assert done.returncode != 0
    assert "SESSION_SECRET is required" in done.stderr + done.stdout


def test_pk03_rooms_survive_a_container_restart_on_the_volume(image):
    volume = f"scrum-poker-test-{uuid.uuid4().hex[:8]}"
    local = {
        "APP_BASE_URL": "http://localhost:8000",
        "SCRUM_POKER_FAKE_SSO": "1",
        "ROOM_CREATOR_ALLOWLIST": "owner@example.com",
        "SESSION_SECRET": "s" * 40,
    }
    try:
        port = free_port()
        local["APP_BASE_URL"] = f"http://localhost:{port}"
        with container(image, local, port, volume, same_port=True) as base:
            assert get(f"{base}/r/vol-room")[0] == 404
            created = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{volume}:/data",
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    "from app.store.rooms import RoomStore, RoomRecord;"
                    "s = RoomStore('/data/scrum-poker.sqlite3');"
                    "s.create(RoomRecord('vol-room', ('google', 'g-owner'), 'owner@example.com'))",
                ],
                capture_output=True,
                text=True,
            )
            assert created.returncode == 0, created.stderr
        with container(image, local, port, volume, same_port=True) as base:
            assert get(f"{base}/r/vol-room")[0] == 200
    finally:
        subprocess.run(["docker", "volume", "rm", "-f", volume], capture_output=True)
