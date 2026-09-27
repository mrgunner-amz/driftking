"""Attribute diffing, independent of any plan fixture."""

from pydantic import JsonValue

from app.change_model import (
    AbsentValue,
    AttributeChange,
    KnownValue,
    SensitiveValue,
    UnknownValue,
)
from app.values import MISSING, Node, collect_sensitive_scalars, diff_attributes


def _diff(
    before: Node,
    after: Node,
    *,
    unknown: JsonValue = None,
    before_sensitive: JsonValue = None,
    after_sensitive: JsonValue = None,
    replace_paths: list[list[str | int]] | None = None,
    secrets: set[str] | None = None,
) -> list[AttributeChange]:
    return diff_attributes(
        before,
        after,
        after_unknown=unknown,
        before_sensitive=before_sensitive,
        after_sensitive=after_sensitive,
        replace_paths=replace_paths or [],
        secrets=secrets or set(),
    )


def test_identical_values_have_no_changes() -> None:
    assert _diff({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}) == []


def test_nested_scalar_change() -> None:
    [change] = _diff({"tags": {"env": "dev"}}, {"tags": {"env": "prod"}})
    assert change.path == ["tags", "env"]
    assert (change.before, change.after) == (KnownValue(value="dev"), KnownValue(value="prod"))


def test_wholly_unknown_container_is_one_change() -> None:
    [change] = _diff({"output": {"a": 1}}, {}, unknown={"output": True})
    assert change.path == ["output"]
    assert change.after == UnknownValue()


def test_unknown_list_element() -> None:
    [change] = _diff({"ids": ["a"]}, {"ids": ["a"]}, unknown={"ids": [False, True]})
    assert change.path == ["ids", 1]
    assert (change.before, change.after) == (AbsentValue(), UnknownValue())


def test_null_and_absent_are_not_a_change() -> None:
    assert _diff(MISSING, {"store": None}) == []


def test_sensitive_value_is_never_copied() -> None:
    [change] = _diff(
        {"pw": "old"}, {"pw": "new"}, before_sensitive={"pw": True}, after_sensitive={"pw": True}
    )
    assert (change.before, change.after) == (SensitiveValue(), SensitiveValue())
    assert "old" not in change.model_dump_json() and "new" not in change.model_dump_json()


def test_unchanged_sensitive_value_is_not_reported() -> None:
    assert (
        _diff(
            {"pw": "same"},
            {"pw": "same"},
            before_sensitive={"pw": True},
            after_sensitive={"pw": True},
        )
        == []
    )


def test_wholly_sensitive_object() -> None:
    [change] = _diff(MISSING, {"secret": {"k": "v"}}, after_sensitive={"secret": True})
    assert change.after == SensitiveValue()


def test_known_secrets_are_redacted_even_without_markers() -> None:
    secrets = collect_sensitive_scalars([({"pw": "hunter2"}, {"pw": True})])
    [change] = _diff({"copy": {"pw": "hunter2"}}, {}, unknown={"copy": True}, secrets=secrets)
    assert change.before == SensitiveValue()


def test_booleans_are_not_collected_as_secrets() -> None:
    assert collect_sensitive_scalars([(True, True), (None, True), ("", True)]) == set()


def test_forces_replacement_matches_path_prefix() -> None:
    changes = _diff(
        {"triggers": {"v": "1"}, "name": "a"},
        {"triggers": {"v": "2"}, "name": "b"},
        replace_paths=[["triggers"]],
    )
    assert {tuple(c.path): c.forces_replacement for c in changes} == {
        ("name",): False,
        ("triggers", "v"): True,
    }


def test_type_change_is_reported_whole() -> None:
    [change] = _diff({"v": [1]}, {"v": {"a": 1}})
    assert change.path == ["v"]
