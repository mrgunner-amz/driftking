"""Attribute-level diffs of a resource's before/after values.

Walks Terraform's ``before``/``after`` values together with the
``after_unknown`` / ``*_sensitive`` marker trees and produces one
``AttributeChange`` per changed leaf. Two rules are absolute:

* An unknown value stays unknown. It is never replaced by a placeholder such
  as ``null`` or ``""``.
* A sensitive value is never copied into the output, only its ``sensitive``
  marker.
"""

from collections.abc import Iterable, Iterator

from pydantic import JsonValue

from app.change_model import (
    AbsentValue,
    AttributeChange,
    KnownValue,
    SensitiveValue,
    UnknownValue,
    Value,
)
from app.terraform_plan import AttributePath


class _Missing:
    """Marks a key that does not exist on one side of a diff."""


MISSING = _Missing()
Node = JsonValue | _Missing


def _child(node: Node, key: str | int) -> Node:
    if isinstance(node, dict) and isinstance(key, str):
        return node.get(key, MISSING)
    if isinstance(node, list) and isinstance(key, int) and key < len(node):
        return node[key]
    return MISSING


def _marker_child(marker: Node, key: str | int) -> Node:
    """Descend a marker tree. ``true`` applies to every descendant."""
    return True if marker is True else _child(marker, key)


def _is_composite(node: Node) -> bool:
    return isinstance(node, dict | list)


def _keys(*nodes: Node) -> list[str | int]:
    """Union of child keys, in a stable order."""
    str_keys: set[str] = set()
    length = 0
    for node in nodes:
        if isinstance(node, dict):
            str_keys.update(node)
        elif isinstance(node, list):
            length = max(length, len(node))
    return [*sorted(str_keys), *range(length)]


def collect_sensitive_scalars(markers_and_values: Iterable[tuple[Node, Node]]) -> set[str]:
    """Return every scalar value Terraform marks sensitive, as canonical strings.

    Terraform does not always propagate sensitivity markers (for example into
    ``terraform_data.output``), so the same secret can appear unmarked
    elsewhere in a plan. Any value equal to one of these is redacted too.
    Booleans and nulls are ignored: they carry no secret on their own and
    redacting them would hide unrelated values.
    """
    found: set[str] = set()

    def walk(value: Node, marker: Node) -> None:
        if marker is True:
            for scalar in _scalars(value):
                found.add(scalar)
            return
        if _is_composite(marker) or _is_composite(value):
            for key in _keys(value, marker):
                walk(_child(value, key), _marker_child(marker, key))

    for value, marker in markers_and_values:
        walk(value, marker)
    return found


def _scalars(value: Node) -> Iterator[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from _scalars(child)
    elif isinstance(value, str) and value:
        yield f"s:{value}"
    elif isinstance(value, int | float) and not isinstance(value, bool):
        yield f"n:{value}"


def _contains_secret(value: Node, secrets: set[str]) -> bool:
    return any(scalar in secrets for scalar in _scalars(value))


def diff_attributes(
    before: Node,
    after: Node,
    *,
    after_unknown: Node,
    before_sensitive: Node,
    after_sensitive: Node,
    replace_paths: list[AttributePath],
    secrets: set[str],
) -> list[AttributeChange]:
    """Diff one resource's values. Pass ``MISSING`` for a side that doesn't exist."""
    changes: list[AttributeChange] = []

    def walk(
        path: list[str | int], b: Node, a: Node, unknown: Node, b_sens: Node, a_sens: Node
    ) -> None:
        # Each side is either a container we can descend into, absent, or a
        # terminal (scalar, wholly unknown, or wholly sensitive).
        b_container = b_sens is not True and _is_composite(b)
        a_container = (
            unknown is not True
            and a_sens is not True
            and (_is_composite(a) or (a is MISSING and _is_composite(unknown)))
        )
        b_absent = b is MISSING
        a_absent = a is MISSING and unknown is not True

        same_shape = not (
            _is_composite(b) and _is_composite(a) and isinstance(b, dict) != isinstance(a, dict)
        )
        descend = (
            same_shape
            and (b_container or a_container)
            and (b_container or b_absent)
            and (a_container or a_absent)
        )
        if not descend:
            _emit(path, b, a, unknown, b_sens, a_sens)
            return
        for key in _keys(b, a, unknown):
            walk(
                [*path, key],
                _child(b, key),
                _child(a, key),
                _marker_child(unknown, key),
                _marker_child(b_sens, key),
                _marker_child(a_sens, key),
            )

    def _emit(
        path: list[str | int], b: Node, a: Node, unknown: Node, b_sens: Node, a_sens: Node
    ) -> None:
        before_value = _side(b, sensitive=b_sens is True, unknown=False, secrets=secrets)
        after_value = _side(a, sensitive=a_sens is True, unknown=unknown is True, secrets=secrets)
        if not _changed(b, a, before_value, after_value):
            return
        changes.append(
            AttributeChange(
                path=path,
                before=before_value,
                after=after_value,
                forces_replacement=any(path[: len(rp)] == rp for rp in replace_paths),
            )
        )

    walk([], before, after, after_unknown, before_sensitive, after_sensitive)
    return changes


def _side(node: Node, *, sensitive: bool, unknown: bool, secrets: set[str]) -> Value:
    if unknown:
        return UnknownValue()
    if node is MISSING:
        return AbsentValue()
    if sensitive or _contains_secret(node, secrets):
        return SensitiveValue()
    assert not isinstance(node, _Missing)
    return KnownValue(value=node)


def _changed(b: Node, a: Node, before_value: Value, after_value: Value) -> bool:
    if isinstance(after_value, UnknownValue):
        return True
    # "absent" and "null" both mean "no value"; don't report that as a change.
    b_empty = b is MISSING or b is None
    a_empty = a is MISSING or a is None
    if b_empty and a_empty:
        return False
    # Compare the raw values even when sensitive: Terraform includes them in
    # the plan, and "a sensitive value changed" is itself safe to report.
    return b != a or type(before_value) is not type(after_value)
