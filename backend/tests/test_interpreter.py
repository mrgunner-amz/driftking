"""Change Interpreter behavior against real Terraform plan fixtures."""

import pytest
from pydantic import JsonValue

from app.change_model import (
    AbsentValue,
    ChangeSet,
    KnownValue,
    Resource,
    SensitiveValue,
    UnknownValue,
)
from app.interpreter import PlanError, parse_plan
from tests.helpers import FIXTURE_SECRET, load_plan, resource_change


def _parse(name: str) -> ChangeSet:
    return parse_plan(load_plan(name))


def _resource(changeset: ChangeSet, address: str) -> Resource:
    matches = [r for r in changeset.resources if r.address == address]
    assert len(matches) == 1, f"expected exactly one {address}, got {len(matches)}"
    return matches[0]


def _change_at(resource: Resource, *path: str | int) -> tuple[object, object]:
    for change in resource.changes:
        if change.path == list(path):
            return change.before, change.after
    raise AssertionError(f"no change at {path} for {resource.address}")


# --- Parsing ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["app-stack-initial", "app-stack-upgrade", "app-stack-no-changes"])
def test_real_fixtures_parse(name: str) -> None:
    changeset = _parse(name)
    assert changeset.format_version.startswith("1.")
    assert changeset.terraform_version
    assert changeset.complete is True


def test_counts_match_terraform_actions() -> None:
    counts = _parse("app-stack-upgrade").counts
    assert (counts.create, counts.update, counts.replace, counts.delete, counts.no_op) == (
        2,
        3,
        1,
        1,
        3,
    )


def test_output_is_deterministic() -> None:
    assert _parse("app-stack-upgrade").model_dump_json() == (
        _parse("app-stack-upgrade").model_dump_json()
    )


# --- Actions -----------------------------------------------------------------


def test_create_is_detected() -> None:
    changeset = _parse("app-stack-upgrade")
    cache = _resource(changeset, "terraform_data.cache")
    assert cache.action == "create"
    assert _change_at(cache, "input", "engine") == (
        AbsentValue(),
        KnownValue(value="redis"),
    )
    assert _resource(changeset, "terraform_data.api[2]").action == "create"


def test_update_is_detected() -> None:
    lb = _resource(_parse("app-stack-upgrade"), "terraform_data.load_balancer")
    assert lb.action == "update"
    assert lb.replace_order is None
    # A new target whose ID Terraform only learns during apply.
    assert _change_at(lb, "input", "targets", 2) == (AbsentValue(), UnknownValue())


def test_delete_is_detected() -> None:
    worker = _resource(_parse("app-stack-upgrade"), "terraform_data.legacy_worker")
    assert worker.action == "delete"
    assert worker.action_reason == "delete_because_no_resource_config"
    assert _change_at(worker, "input", "image") == (
        KnownValue(value="worker:0.9.2"),
        AbsentValue(),
    )


def test_replace_is_one_resource_transition() -> None:
    changeset = _parse("app-stack-upgrade")
    database = _resource(changeset, "terraform_data.database")
    assert database.action == "replace"
    assert database.replace_order == "delete_before_create"
    assert database.replace_paths == [["triggers_replace"]]
    assert database.action_reason == "replace_because_cannot_update"

    forcing = [c.path for c in database.changes if c.forces_replacement]
    assert forcing == [["triggers_replace", "engine_version"]]
    assert _change_at(database, "input", "engine_version") == (
        KnownValue(value="15"),
        KnownValue(value="16"),
    )


def test_create_before_destroy_replace_order() -> None:
    plan = load_plan("app-stack-upgrade")
    change = resource_change(plan, "terraform_data.database")["change"]
    assert isinstance(change, dict)
    change["actions"] = ["create", "delete"]
    database = _resource(parse_plan(plan), "terraform_data.database")
    assert (database.action, database.replace_order) == ("replace", "create_before_destroy")


def test_no_op_resources_carry_no_changes() -> None:
    network = _resource(_parse("app-stack-upgrade"), "terraform_data.network")
    assert network.action == "no-op"
    assert network.changes == []


# --- Identity ------------------------------------------------------------------


def test_addresses_are_unique_and_match_terraform() -> None:
    plan = load_plan("app-stack-upgrade")
    changeset = parse_plan(plan)
    addresses = [r.address for r in changeset.resources]
    assert len(addresses) == len(set(addresses))

    changes = plan["resource_changes"]
    assert isinstance(changes, list)
    terraform_addresses = {rc["address"] for rc in changes if isinstance(rc, dict)}
    assert set(addresses) <= terraform_addresses


def test_identity_is_stable_across_plans() -> None:
    """The same resource has the same identity whatever the plan does to it."""
    initial = {r.address: r for r in _parse("app-stack-initial").resources}
    upgrade = {r.address: r for r in _parse("app-stack-upgrade").resources}
    for address in ["terraform_data.database", "terraform_data.api[0]"]:
        assert (initial[address].type, initial[address].name) == (
            upgrade[address].type,
            upgrade[address].name,
        )
    assert upgrade["terraform_data.api[0]"].index == 0
    assert upgrade["terraform_data.api[2]"].index == 2


def test_replacement_keeps_identity_in_relationships() -> None:
    changeset = _parse("app-stack-upgrade")
    edges = {(r.source, r.target) for r in changeset.relationships}
    # api[0] keeps its edge to *the* database, not to an old and a new copy.
    assert ("terraform_data.api[0]", "terraform_data.database") in edges
    assert sum(1 for r in changeset.resources if r.name == "database") == 1


def test_module_address_is_preserved() -> None:
    health = _resource(_parse("app-stack-upgrade"), "module.monitoring.terraform_data.health_check")
    assert health.module_address == "module.monitoring"
    assert (health.type, health.name, health.index) == ("terraform_data", "health_check", None)


# --- Unknown and sensitive values ------------------------------------------------


def test_unknown_values_stay_unknown() -> None:
    changeset = _parse("app-stack-upgrade")
    api = _resource(changeset, "terraform_data.api[0]")
    # database is replaced, so its new ID is unknown until apply.
    before, after = _change_at(api, "input", "database_id")
    assert isinstance(before, KnownValue)
    assert after == UnknownValue()

    created = _resource(changeset, "terraform_data.api[2]")
    assert _change_at(created, "id") == (AbsentValue(), UnknownValue())


def _unknown_leaf_paths(marker: JsonValue, path: list[str | int]) -> list[list[str | int]]:
    if marker is True:
        return [path]
    if isinstance(marker, dict):
        return [p for k, v in marker.items() for p in _unknown_leaf_paths(v, [*path, k])]
    if isinstance(marker, list):
        return [p for i, v in enumerate(marker) for p in _unknown_leaf_paths(v, [*path, i])]
    return []


def test_every_terraform_unknown_is_reported_as_unknown() -> None:
    """Each path Terraform marks unknown maps to an ``unknown`` after-value."""
    plan = load_plan("app-stack-upgrade")
    changeset = parse_plan(plan)
    checked = 0
    changes = plan["resource_changes"]
    assert isinstance(changes, list)
    for rc in changes:
        assert isinstance(rc, dict) and isinstance(rc["change"], dict)
        address = rc["address"]
        resource = next((r for r in changeset.resources if r.address == address), None)
        if resource is None or resource.action == "delete":
            continue
        for path in _unknown_leaf_paths(rc["change"].get("after_unknown"), []):
            covering = [c for c in resource.changes if path[: len(c.path)] == c.path]
            assert covering, f"{address}: unknown {path} missing from changes"
            assert all(c.after == UnknownValue() for c in covering), (address, path)
            checked += 1
    assert checked > 10


def test_sensitive_values_are_marked_not_exposed() -> None:
    changeset = _parse("app-stack-upgrade")
    created = _resource(changeset, "terraform_data.api[2]")
    assert _change_at(created, "input", "db_password") == (AbsentValue(), SensitiveValue())
    assert FIXTURE_SECRET not in changeset.model_dump_json()


def test_unmarked_copies_of_sensitive_values_are_redacted() -> None:
    """Terraform does not mark ``terraform_data.output``; the secret is there anyway."""
    plan = load_plan("app-stack-upgrade")
    api = resource_change(plan, "terraform_data.api[0]")["change"]
    assert isinstance(api, dict)
    before_sensitive = api["before_sensitive"]
    assert isinstance(before_sensitive, dict)
    assert before_sensitive["output"] == {}  # Terraform's own markers, unchanged.

    resource = _resource(parse_plan(plan), "terraform_data.api[0]")
    before, _ = _change_at(resource, "output")
    assert before == SensitiveValue()


def test_sensitive_changes_are_reported_without_values() -> None:
    plan = load_plan("app-stack-upgrade")
    change = resource_change(plan, "terraform_data.api[0]")["change"]
    assert isinstance(change, dict)
    after = change["after"]
    assert isinstance(after, dict) and isinstance(after["input"], dict)
    after["input"]["db_password"] = "rotated-placeholder"
    changeset = parse_plan(plan)
    resource = _resource(changeset, "terraform_data.api[0]")
    assert _change_at(resource, "input", "db_password") == (SensitiveValue(), SensitiveValue())
    assert "rotated-placeholder" not in changeset.model_dump_json()


def test_plan_variables_are_never_exposed() -> None:
    assert FIXTURE_SECRET not in _parse("app-stack-initial").model_dump_json()


# --- Optional and missing fields ---------------------------------------------------


_OPTIONAL_CHANGE_FIELDS = [
    "after_unknown",
    "before_sensitive",
    "after_sensitive",
    "replace_paths",
]


@pytest.mark.parametrize("field", _OPTIONAL_CHANGE_FIELDS)
def test_missing_optional_change_fields_do_not_crash(field: str) -> None:
    plan = load_plan("app-stack-upgrade")
    changes = plan["resource_changes"]
    assert isinstance(changes, list)
    for rc in changes:
        assert isinstance(rc, dict) and isinstance(rc["change"], dict)
        rc["change"].pop(field, None)
    assert len(parse_plan(plan).resources) == 9


@pytest.mark.parametrize("field", ["module_address", "index", "action_reason", "previous_address"])
def test_missing_optional_resource_fields_do_not_crash(field: str) -> None:
    plan = load_plan("app-stack-upgrade")
    changes = plan["resource_changes"]
    assert isinstance(changes, list)
    for rc in changes:
        assert isinstance(rc, dict)
        rc.pop(field, None)
    parse_plan(plan)


@pytest.mark.parametrize(
    "section", ["configuration", "prior_state", "planned_values", "relevant_attributes"]
)
def test_missing_top_level_sections_do_not_crash(section: str) -> None:
    plan = load_plan("app-stack-upgrade")
    plan.pop(section)
    changeset = parse_plan(plan)
    assert changeset.counts.replace == 1
    if section == "configuration":
        # Without configuration there is nothing to derive edges from, and
        # none are invented.
        assert all(r.status == "removed" for r in changeset.relationships)


def test_no_resource_changes() -> None:
    changeset = _parse("app-stack-no-changes")
    assert changeset.resources == []
    assert changeset.relationships == []
    assert changeset.counts.no_op == 8
    assert changeset.hidden_unchanged == 8


def test_plan_without_resource_changes_key() -> None:
    plan = load_plan("app-stack-no-changes")
    plan.pop("resource_changes")
    assert parse_plan(plan).resources == []


def test_data_sources_are_not_infrastructure_changes() -> None:
    plan = load_plan("app-stack-upgrade")
    rc = resource_change(plan, "terraform_data.network")
    rc["mode"] = "data"
    rc["change"] = {"actions": ["read"], "before": None, "after": {}}
    addresses = {r.address for r in parse_plan(plan).resources}
    assert "terraform_data.network" not in addresses


# --- Clear failures ------------------------------------------------------------------


def _expect_error(document: JsonValue, match: str) -> None:
    with pytest.raises(PlanError, match=match):
        parse_plan(document)


def test_rejects_non_plan_json() -> None:
    _expect_error([1, 2, 3], "JSON object")
    _expect_error({"hello": "world"}, "does not look like a Terraform plan")


def test_rejects_unsupported_format_version() -> None:
    plan = load_plan("app-stack-upgrade")
    plan["format_version"] = "2.0"
    _expect_error(plan, "format_version")


def test_rejects_errored_plan() -> None:
    plan = load_plan("app-stack-upgrade")
    plan["errored"] = True
    _expect_error(plan, "errored")


@pytest.mark.parametrize("actions", [["forget"], ["create", "update"], ["read"], []])
def test_rejects_unknown_action_sequences(actions: list[str]) -> None:
    plan = load_plan("app-stack-upgrade")
    change = resource_change(plan, "terraform_data.cache")["change"]
    assert isinstance(change, dict)
    change["actions"] = list(actions)
    _expect_error(plan, "terraform_data.cache: action")


def test_rejects_deposed_objects() -> None:
    plan = load_plan("app-stack-upgrade")
    resource_change(plan, "terraform_data.database")["deposed"] = "00000001"
    _expect_error(plan, "deposed")


def test_malformed_plan_reports_location_not_values() -> None:
    plan = load_plan("app-stack-upgrade")
    rc = resource_change(plan, "terraform_data.api[0]")
    rc["mode"] = FIXTURE_SECRET
    with pytest.raises(PlanError, match="Malformed plan JSON") as raised:
        parse_plan(plan)
    assert FIXTURE_SECRET not in str(raised.value)
