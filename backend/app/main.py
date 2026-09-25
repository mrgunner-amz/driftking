"""DriftKing API.

Minimal FastAPI application. Scaffolding only: the Terraform plan parsing,
change model and graph layers are intentionally not implemented yet.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__

# Development default. The frontend runs on :3000 both on the host and in
# Docker Compose, so a single fixed list is enough for now.
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(
    title="DriftKing API",
    description="Visual Terraform drift and change explorer.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Liveness payload returned by ``GET /health``."""

    status: str


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Report that the API process is up and serving requests."""
    return HealthResponse(status="ok")
