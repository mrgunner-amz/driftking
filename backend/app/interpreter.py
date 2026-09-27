"""Change Interpreter: ``terraform show -json`` output -> DriftKing ChangeSet.

The interpreter uses the plan JSON as its only source of truth. It never
evaluates Terraform configuration or guesses at what Terraform will do, and it
refuses plans containing features it cannot represent faithfully instead of
silently mis-describing them.
"""

from collections import Counter

from pydantic import JsonValue, ValidationError

from app.change_model import (
    Action,
    ActionCounts,
    ChangeSet,
    Relationship,
    ReplaceOrder,
    Resource,
)
from app.relationships import build_relationships
from app.terraform_plan import Plan, ResourceChange
from app.values import MISSING, collect_sensitive_scalars, diff_attributes

SUPPORTED_FORMAT_MAJOR = "1"


class PlanError(ValueError):
    """The input is not a plan DriftKing can describe faithfully."""


# Terraform's documented action lists and what each one means for a resource.
# https://developer.hashicorp.com/terraform/internals/json-format#change-representation
_ACTIONS: dict[tuple[str, ...], tuple[Action, ReplaceOrder | None]] = {
    ("no-op",): ("no-op", None),
    ("create",): ("create", None),
    ("update",): ("update", None),
    ("delete",): ("delete", None),
    ("delete", "create"): ("replace", "delete_before_create"),
    ("create", "delete"): ("replace", "create_before_destroy"),
}


def parse_plan(document: JsonValue) -> ChangeSet:
    """Validate and interpret a decoded ``terraform show -json`` document."""
    if not isinstance(document, dict):
        raise PlanError("Expected a JSON object produced by `terraform show -json <planfile>`.")
    if "resource_changes" not in document and "planned_values" not in document:
        raise PlanError(
            "This JSON does not look like a Terraform plan. Generate one with "
            "`terraform plan -out=tfplan && terraform show -json tfplan`."
        )
    try:
        plan = Plan.model_validate(document)
    except ValidationError as error:
        # Report where the structure is wrong, never the offending values.
        locations = sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})
        raise PlanError(f"Malformed plan JSON at: {', '.join(locations[:5])}") from None
    return interpret(plan)


def interpret(plan: Plan) -> ChangeSet:
    major = plan.format_version.split(".", 1)[0]
    if major != SUPPORTED_FORMAT_MAJOR:
        raise PlanError(
            f"Unsupported plan format_version {plan.format_version!r}; "
            f"DriftKing understands {SUPPORTED_FORMAT_MAJOR}.x."
        )
    if plan.errored:
        raise PlanError(
            "Terraform reported that this plan errored; there is no valid plan to show."
        )

    managed = [rc for rc in plan.resource_changes if rc.mode == "managed"]
    secrets = collect_sensitive_scalars(
        pair
        for rc in managed
        for pair in (
            (rc.change.before, rc.change.before_sensitive),
            (rc.change.after, rc.change.after_sensitive),
        )
    )

    resources: list[Resource] = []
    seen: set[str] = set()
    for rc in managed:
        if rc.deposed is not None:
            raise PlanError(
                f"{rc.address} has a deposed object (left over from an interrupted "
                "create_before_destroy). Deposed objects are not supported yet."
            )
        if rc.address in seen:
            raise PlanError(f"Resource address {rc.address} appears more than once.")
        seen.add(rc.address)
        resources.append(_resource(rc, secrets))

    actions = {resource.address: resource.action for resource in resources}
    relationships = build_relationships(plan, actions)
    shown, shown_relationships = _neighborhood(resources, relationships)

    return ChangeSet(
        terraform_version=plan.terraform_version,
        format_version=plan.format_version,
        complete=plan.complete,
        counts=_count(resources),
        resources=shown,
        relationships=shown_relationships,
        hidden_unchanged=len(resources) - len(shown),
        drifted_resources=len([rc for rc in plan.resource_drift if rc.mode == "managed"]),
    )


def _resource(rc: ResourceChange, secrets: set[str]) -> Resource:
    mapped = _ACTIONS.get(tuple(rc.change.actions))
    if mapped is None:
        raise PlanError(
            f"{rc.address}: action {rc.change.actions} is not supported yet "
            "(DriftKing understands create, update, delete, replace and no-op)."
        )
    action, replace_order = mapped
    change = rc.change
    replace_paths = change.replace_paths or []
    changes = diff_attributes(
        MISSING if action == "create" else change.before,
        MISSING if action == "delete" else change.after,
        after_unknown=change.after_unknown,
        before_sensitive=change.before_sensitive,
        after_sensitive=change.after_sensitive,
        replace_paths=replace_paths,
        secrets=secrets,
    )
    return Resource(
        address=rc.address,
        module_address=rc.module_address,
        type=rc.type,
        name=rc.name,
        index=rc.index,
        provider_name=rc.provider_name,
        action=action,
        action_reason=rc.action_reason,
        replace_order=replace_order,
        replace_paths=replace_paths,
        previous_address=rc.previous_address,
        importing=change.importing is not None,
        changes=[] if action == "no-op" else changes,
    )


def _count(resources: list[Resource]) -> ActionCounts:
    counts = Counter(resource.action for resource in resources)
    return ActionCounts(
        create=counts["create"],
        update=counts["update"],
        replace=counts["replace"],
        delete=counts["delete"],
        no_op=counts["no-op"],
    )


def _neighborhood(
    resources: list[Resource], relationships: list[Relationship]
) -> tuple[list[Resource], list[Relationship]]:
    """Changed resources plus the resources directly connected to them.

    Rendering every resource in a real configuration would bury the change,
    so unchanged resources are only kept when they share an edge with a
    changed one.
    """
    changed = {r.address for r in resources if r.action != "no-op"}
    keep = set(changed)
    for rel in relationships:
        if rel.source in changed or rel.target in changed:
            keep.update((rel.source, rel.target))
    return (
        [r for r in resources if r.address in keep],
        [rel for rel in relationships if rel.source in keep and rel.target in keep],
    )
