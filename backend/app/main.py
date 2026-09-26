"""DriftKing API entry point.

Scaffolding only. The Terraform input, change interpretation and visualization
layers described in ``docs/architecture.md`` are intentionally not implemented.
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__


class HealthResponse(BaseModel):
    """Liveness payload returned by ``GET /health``."""

    status: Literal["ok"]


def create_app() -> FastAPI:
    """Build the FastAPI application.

    A factory rather than a bare module-level object so that tests can build an
    isolated instance, and so later layers can be wired in explicitly.
    """
    application = FastAPI(
        title="DriftKing API",
        description="A visual explorer for Terraform infrastructure changes and drift.",
        version=__version__,
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """Report that the API process is up and serving requests."""
        return HealthResponse(status="ok")

    return application


# ASGI entry point for ``uvicorn app.main:app``.
app = create_app()
