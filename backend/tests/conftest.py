"""Pytest fixtures shared across the test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import FIXTURES_DIR


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(fixtures_dir=FIXTURES_DIR)) as test_client:
        yield test_client
