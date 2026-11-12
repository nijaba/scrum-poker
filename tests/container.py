"""Build the image and run containers from it, for cases PK-01 and PK-02.

Tests that use these skip, with the reason, when Docker is not installed or not running.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "scrum-poker:test"


def docker_ready() -> str | None:
    """None when Docker can build and run; otherwise why not."""
    if not shutil.which("docker"):
        return "docker is not installed"
    probe = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if probe.returncode != 0:
        return "the Docker daemon is not running"
    return None


def build_image() -> str:
    reason = docker_ready()
    if reason:
        pytest.skip(reason)
    done = subprocess.run(
        ["docker", "build", "-t", IMAGE, str(ROOT)], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr[-4000:]
    return IMAGE


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url: str, headers: dict[str, str] | None = None):
    """GET without following redirects: (status, headers, body)."""

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read().decode()


@contextmanager
def container(
    image: str, env: dict[str, str], port: int, volume: str | None = None, same_port: bool = False
) -> Iterator[str]:
    """Run the image with these environment variables only; yield its address.

    With `same_port`, the app listens on `port` inside the container too, so an
    APP_BASE_URL of http://localhost:<port> also reaches it from inside, as the
    fake sign-in needs.
    """
    name = f"scrum-poker-test-{uuid.uuid4().hex[:8]}"
    inner = port if same_port else 8000
    command = ["docker", "run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:{inner}"]
    if same_port:
        command += ["-e", f"PORT={port}"]
    for key, value in env.items():
        command += ["-e", f"{key}={value}"]
    if volume:
        command += ["-v", f"{volume}:/data"]
    started = subprocess.run([*command, image], capture_output=True, text=True)
    assert started.returncode == 0, started.stderr
    base = f"http://localhost:{port}"
    try:
        for _ in range(100):
            try:
                if get(f"{base}/healthz")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
            raise AssertionError(f"the container did not start:\n{logs.stdout}{logs.stderr}")
        yield base
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
