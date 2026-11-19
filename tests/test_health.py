"""/healthz, and the version it reports. Case VR-01 (design.md, "Versions and releases")."""

import tomllib
from pathlib import Path

VERSION = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())["project"][
    "version"
]


def test_healthz_reports_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_vr01_healthz_reports_the_version_in_pyproject(client):
    assert client.get("/healthz").json() == {"status": "ok", "version": VERSION}
    assert VERSION.count(".") == 2 and all(part.isdigit() for part in VERSION.split("."))
