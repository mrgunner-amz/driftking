"""DriftKing API entry point.

Read-only: the API interprets Terraform plan JSON and returns DriftKing's
Change Model. It never runs Terraform and never touches infrastructure.
"""

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, JsonValue
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.change_model import ChangeSet
from app.fixtures import (
    FixtureNotFoundError,
    default_fixtures_dir,
    list_fixtures,
    load_fixture,
)
from app.interpreter import PlanError, parse_plan

MAX_PLAN_BYTES = 10 * 1024 * 1024


class HealthResponse(BaseModel):
    """Liveness payload returned by ``GET /health``."""

    status: Literal["ok"]


class Fixture(BaseModel):
    name: str


class FixtureList(BaseModel):
    fixtures: list[Fixture]


def _interpret(document: JsonValue) -> ChangeSet:
    try:
        return parse_plan(document)
    except PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


def create_app(fixtures_dir: Path | None = None) -> FastAPI:
    """Build the FastAPI application.

    ``fixtures_dir`` defaults to ``$DRIFTKING_FIXTURES_DIR`` or the repository's
    ``fixtures/plans``; tests pass their own.
    """
    directory = fixtures_dir if fixtures_dir is not None else default_fixtures_dir()
    application = FastAPI(
        title="DriftKing API",
        description="A visual explorer for Terraform infrastructure changes and drift.",
        version=__version__,
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """Report that the API process is up and serving requests."""
        return HealthResponse(status="ok")

    @application.get("/api/fixtures", response_model=FixtureList, tags=["plans"])
    def fixtures() -> FixtureList:
        """List the bundled plan fixtures."""
        return FixtureList(fixtures=[Fixture(name=name) for name in list_fixtures(directory)])

    @application.get("/api/fixtures/{name}", response_model=ChangeSet, tags=["plans"])
    def fixture_changes(name: str) -> ChangeSet:
        """Interpret a bundled plan fixture."""
        try:
            document = load_fixture(directory, name)
        except FixtureNotFoundError:
            raise HTTPException(status_code=404, detail=f"No fixture named {name!r}.") from None
        return _interpret(document)

    @application.post("/api/plans", response_model=ChangeSet, tags=["plans"])
    async def interpret_plan(request: Request) -> ChangeSet:
        """Interpret an uploaded ``terraform show -json`` document (request body)."""
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > MAX_PLAN_BYTES:
            raise HTTPException(status_code=413, detail="Plan JSON is larger than 10 MiB.")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_PLAN_BYTES:
                raise HTTPException(status_code=413, detail="Plan JSON is larger than 10 MiB.")
        try:
            document = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="Request body is not valid JSON.") from None
        return await run_in_threadpool(_interpret, document)

    return application


# ASGI entry point for ``uvicorn app.main:app``.
app = create_app()
