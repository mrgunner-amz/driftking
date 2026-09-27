"""Dependency relationships derived from Terraform's plan JSON."""

import pytest

from app.change_model import ChangeSet
from app.interpreter import parse_plan
from app.relationships import config_address
from tests.helpers import load_plan


def _edges(changeset: ChangeSet) -> dict[tuple[str, str], str]:
    return {(r.source, r.target): r.status for r in changeset.relationships}


@pytest.fixture(scope="module")
def upgrade() -> ChangeSet:
    return parse_plan(load_plan("app-stack-upgrade"))


@pytest.mark.parametrize(
    ("instance", "expected"),
    [
        ("aws_instance.web", "aws_instance.web"),
        ("aws_instance.web[0]", "aws_instance.web"),
        ('module.a["x"].aws_instance.web["b]lue"]', "module.a.aws_instance.web"),
        ("module.a[1].module.b.terraform_data.c", "module.a.module.b.terraform_data.c"),
    ],
)
def test_config_address(instance: str, expected: str) -> None:
    assert config_address(instance) == expected


def test_edges_to_created_resources_are_added(upgrade: ChangeSet) -> None:
    edges = _edges(upgrade)
    assert edges[("terraform_data.cache", "terraform_data.network")] == "added"
    assert edges[("terraform_data.api[0]", "terraform_data.cache")] == "added"
    # The load balancer gains the new api instance as a target.
    assert edges[("terraform_data.load_balancer", "terraform_data.api[2]")] == "added"


def test_edges_from_destroyed_resources_are_removed(upgrade: ChangeSet) -> None:
    edges = _edges(upgrade)
    assert edges[("terraform_data.legacy_worker", "terraform_data.database")] == "removed"


def test_recorded_transitive_dependencies_are_reduced(upgrade: ChangeSet) -> None:
    """State records worker -> {database, network}; network is implied via database."""
    edges = _edges(upgrade)
    assert ("terraform_data.legacy_worker", "terraform_data.network") not in edges


def test_edges_between_surviving_resources_are_present(upgrade: ChangeSet) -> None:
    edges = _edges(upgrade)
    assert edges[("terraform_data.api[0]", "terraform_data.database")] == "present"
    assert edges[("terraform_data.load_balancer", "terraform_data.api[0]")] == "present"


def test_references_are_direct_not_transitive(upgrade: ChangeSet) -> None:
    edges = _edges(upgrade)
    # api reaches network only through database/cache; no direct edge is claimed.
    assert ("terraform_data.api[0]", "terraform_data.network") not in edges


def test_module_variables_resolve_to_the_referenced_resource(upgrade: ChangeSet) -> None:
    edges = _edges(upgrade)
    assert (
        edges[("module.monitoring.terraform_data.health_check", "terraform_data.load_balancer")]
        == "present"
    )


def test_every_edge_connects_shown_resources(upgrade: ChangeSet) -> None:
    shown = {r.address for r in upgrade.resources}
    for rel in upgrade.relationships:
        assert {rel.source, rel.target} <= shown


def test_neighborhood_hides_unrelated_unchanged_resources(upgrade: ChangeSet) -> None:
    shown = {r.address for r in upgrade.resources}
    assert "terraform_data.audit_log_bucket" not in shown
    # Unchanged, but directly connected to a change: kept as context.
    assert "terraform_data.network" in shown
    assert "module.monitoring.terraform_data.health_check" in shown
    assert upgrade.hidden_unchanged == 1


def test_resources_with_no_dependencies_are_still_shown() -> None:
    plan = load_plan("app-stack-upgrade")
    plan.pop("configuration")
    plan.pop("prior_state")
    changeset = parse_plan(plan)
    assert changeset.relationships == []
    assert {r.address for r in changeset.resources} >= {
        "terraform_data.cache",
        "terraform_data.database",
    }
