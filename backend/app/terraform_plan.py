"""Typed view of the parts of ``terraform show -json`` output DriftKing reads.

These models mirror Terraform's documented JSON plan format
(https://developer.hashicorp.com/terraform/internals/json-format). They are
deliberately partial and lenient: unknown fields are ignored so newer
Terraform versions keep working, and every field Terraform may omit is
optional. Interpretation happens in ``app.interpreter``; nothing here knows
about DriftKing's own model.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

# A path into a resource object, e.g. ["input", "engine_version"] or ["tags", 0].
AttributePath = list[str | int]


class _TerraformModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Change(_TerraformModel):
    """``resource_changes[].change``.

    ``before``/``after`` hold attribute values. ``after_unknown``,
    ``before_sensitive`` and ``after_sensitive`` are *marker* trees with the
    same shape: ``true`` at a node means "this whole value is unknown /
    sensitive", nested objects and arrays mark individual children.
    """

    actions: list[str]
    before: JsonValue = None
    after: JsonValue = None
    after_unknown: JsonValue = None
    before_sensitive: JsonValue = None
    after_sensitive: JsonValue = None
    replace_paths: list[AttributePath] | None = None
    importing: dict[str, JsonValue] | None = None


class ResourceChange(_TerraformModel):
    """One entry of ``resource_changes`` (or ``resource_drift``)."""

    address: str
    module_address: str | None = None
    mode: Literal["managed", "data"]
    type: str
    name: str
    index: int | str | None = None
    provider_name: str
    deposed: str | None = None
    previous_address: str | None = None
    action_reason: str | None = None
    change: Change


class StateResource(_TerraformModel):
    address: str
    mode: Literal["managed", "data"]
    depends_on: list[str] = Field(default_factory=list)


class StateModule(_TerraformModel):
    resources: list[StateResource] = Field(default_factory=list)
    child_modules: list["StateModule"] = Field(default_factory=list)


class StateValues(_TerraformModel):
    root_module: StateModule = Field(default_factory=StateModule)


class PriorState(_TerraformModel):
    values: StateValues | None = None


class ConfigResource(_TerraformModel):
    """A resource block in ``configuration``. Addresses are module-relative."""

    address: str
    mode: Literal["managed", "data"]
    expressions: JsonValue = None
    count_expression: JsonValue = None
    for_each_expression: JsonValue = None
    depends_on: list[str] = Field(default_factory=list)


class ConfigOutput(_TerraformModel):
    expression: JsonValue = None


class ModuleCall(_TerraformModel):
    expressions: JsonValue = None
    count_expression: JsonValue = None
    for_each_expression: JsonValue = None
    depends_on: list[str] = Field(default_factory=list)
    module: "ConfigModule" = Field(default_factory=lambda: ConfigModule())


class ConfigModule(_TerraformModel):
    resources: list[ConfigResource] = Field(default_factory=list)
    module_calls: dict[str, ModuleCall] = Field(default_factory=dict)
    outputs: dict[str, ConfigOutput] = Field(default_factory=dict)


class Configuration(_TerraformModel):
    root_module: ConfigModule = Field(default_factory=ConfigModule)


class Plan(_TerraformModel):
    """Top level of ``terraform show -json <planfile>``."""

    format_version: str
    terraform_version: str | None = None
    resource_changes: list[ResourceChange] = Field(default_factory=list)
    resource_drift: list[ResourceChange] = Field(default_factory=list)
    prior_state: PriorState | None = None
    configuration: Configuration | None = None
    errored: bool = False
    complete: bool = True
