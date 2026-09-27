"""Bundled Terraform plan fixtures (``fixtures/plans/*.json``)."""

import json
import os
import re
from pathlib import Path

from pydantic import JsonValue

# backend/app/fixtures.py -> <repo>/fixtures/plans
_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "plans"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FixtureNotFoundError(LookupError):
    pass


def default_fixtures_dir() -> Path:
    """``$DRIFTKING_FIXTURES_DIR`` if set (used in Docker), else the repo copy."""
    configured = os.environ.get("DRIFTKING_FIXTURES_DIR")
    return Path(configured) if configured else _DEFAULT_DIR


def list_fixtures(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        path.stem
        for path in directory.glob("*.json")
        if path.is_file() and _NAME.fullmatch(path.stem)
    )


def load_fixture(directory: Path, name: str) -> JsonValue:
    # Only names returned by list_fixtures are ever turned into paths.
    if name not in list_fixtures(directory):
        raise FixtureNotFoundError(name)
    document: JsonValue = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
    return document
