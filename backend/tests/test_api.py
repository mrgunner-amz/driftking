"""HTTP API over the Change Interpreter."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import MAX_PLAN_BYTES, create_app
from tests.helpers import FIXTURE_SECRET, FIXTURES_DIR, load_plan


def test_lists_bundled_fixtures(client: TestClient) -> None:
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    names = [f["name"] for f in response.json()["fixtures"]]
    assert names == sorted(names)
    assert {"app-stack-initial", "app-stack-no-changes", "app-stack-upgrade"} <= set(names)


def test_fixture_changes(client: TestClient) -> None:
    response = client.get("/api/fixtures/app-stack-upgrade")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"create": 2, "update": 3, "replace": 1, "delete": 1, "no_op": 3}
    database = next(r for r in body["resources"] if r["address"] == "terraform_data.database")
    assert database["action"] == "replace"
    assert FIXTURE_SECRET not in response.text


def test_unknown_fixture_is_404(client: TestClient) -> None:
    assert client.get("/api/fixtures/nope").status_code == 404


def test_fixture_names_cannot_escape_the_directory(client: TestClient) -> None:
    for name in ["..%2F..%2Fetc%2Fpasswd", "..", "APP-STACK-UPGRADE"]:
        assert client.get(f"/api/fixtures/{name}").status_code == 404


def test_missing_fixture_directory_lists_nothing(tmp_path: Path) -> None:
    with TestClient(create_app(fixtures_dir=tmp_path / "missing")) as isolated:
        assert isolated.get("/api/fixtures").json() == {"fixtures": []}


def test_post_plan(client: TestClient) -> None:
    plan_bytes = (FIXTURES_DIR / "app-stack-upgrade.json").read_bytes()
    response = client.post(
        "/api/plans", content=plan_bytes, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json() == client.get("/api/fixtures/app-stack-upgrade").json()


def test_post_invalid_json_is_400(client: TestClient) -> None:
    response = client.post("/api/plans", content=b"{not json")
    assert response.status_code == 400


def test_post_non_plan_is_422_with_reason(client: TestClient) -> None:
    response = client.post("/api/plans", json={"hello": "world"})
    assert response.status_code == 422
    assert "terraform show -json" in response.json()["detail"]


def test_post_unsupported_plan_is_422(client: TestClient) -> None:
    plan = load_plan("app-stack-upgrade")
    plan["format_version"] = "9.0"
    response = client.post("/api/plans", content=json.dumps(plan))
    assert response.status_code == 422
    assert "format_version" in response.json()["detail"]


def test_post_oversized_plan_is_413(client: TestClient) -> None:
    response = client.post("/api/plans", content=b" " * (MAX_PLAN_BYTES + 1))
    assert response.status_code == 413
