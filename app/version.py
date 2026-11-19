"""The app's version (design.md, "Versions and releases"). `pyproject.toml` is the one source:
the installed package's metadata carries it, and a checkout without an install reads the file."""

import tomllib
from importlib import metadata
from pathlib import Path


def _version() -> str:
    try:
        return metadata.version("scrum-poker")
    except metadata.PackageNotFoundError:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        return tomllib.loads(pyproject.read_text())["project"]["version"]


VERSION = _version()
