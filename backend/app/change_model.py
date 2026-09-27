"""DriftKing's Change Model: the contract between the backend and the UI.

It describes *what* Terraform plans to change, in DriftKing's own vocabulary.
It contains no layout or animation instructions; how to present a change is
the frontend's decision.

See docs/change-model.md for the rationale behind each field.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

Action = Literal["create", "update", "replace", "delete", "no-op"]
"""Lifecycle action for one resource.

``replace`` is a single transition of one resource (Terraform's
``["delete", "create"]`` or ``["create", "delete"]``), never a separate
delete plus create.
"""


ReplaceOrder = Literal["delete_before_create", "create_before_destroy"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class KnownValue(_Model):
    kind: Literal["known"] = "known"
    value: JsonValue


class UnknownValue(_Model):
    """Terraform will only know this value after apply ("known after apply")."""

    kind: Literal["unknown"] = "unknown"


class SensitiveValue(_Model):
    """A value that must not be displayed. The value itself is never included."""

    kind: Literal["sensitive"] = "sensitive"


class AbsentValue(_Model):
    """The attribute does not exist on this side (e.g. before a create)."""

    kind: Literal["absent"] = "absent"


Value = Annotated[
    KnownValue | UnknownValue | SensitiveValue | AbsentValue,
    Field(discriminator="kind"),
]


class AttributeChange(_Model):
    """One changed leaf attribute of a resource."""

    path: list[str | int]
    before: Value
    after: Value
    forces_replacement: bool = False


class Resource(_Model):
    """One resource instance and what happens to it.

    ``address`` is the identity. Terraform uses the same address for the
    object before and after, including across a replacement, so the frontend
    can treat BEFORE and AFTER nodes with equal addresses as the same thing.
    """

    address: str
    module_address: str | None
    type: str
    name: str
    index: int | str | None
    provider_name: str
    action: Action
    action_reason: str | None = None
    replace_order: ReplaceOrder | None = None
    replace_paths: list[list[str | int]] = Field(default_factory=list)
    previous_address: str | None = None
    importing: bool = False
    changes: list[AttributeChange] = Field(default_factory=list)


RelationshipStatus = Literal["added", "removed", "present"]
"""How a dependency edge relates to the change.

* ``added``   - an endpoint is being created, so the edge cannot exist before.
* ``removed`` - an endpoint is being destroyed, so the edge cannot exist after.
* ``present`` - both endpoints exist before and after. Terraform's plan does
  not record the previous configuration, so whether this particular edge is
  new is unknown; it is shown on both sides.
"""


class Relationship(_Model):
    """``source`` depends on ``target`` (e.g. api -> database)."""

    source: str
    target: str
    status: RelationshipStatus


class ActionCounts(_Model):
    create: int = 0
    update: int = 0
    replace: int = 0
    delete: int = 0
    no_op: int = 0


class ChangeSet(_Model):
    """The planned transition, focused on the change neighborhood."""

    terraform_version: str | None
    format_version: str
    complete: bool
    counts: ActionCounts
    """Counts over *all* managed resources in the plan, not only those shown."""
    resources: list[Resource]
    """Changed resources plus their direct, unchanged neighbors."""
    relationships: list[Relationship]
    hidden_unchanged: int
    """Unchanged resources left out because they are not adjacent to a change."""
    drifted_resources: int
    """Resources Terraform reports as changed outside Terraform (not visualized in V1)."""
