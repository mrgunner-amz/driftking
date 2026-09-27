"""Dependency relationships between resources, from Terraform's own data.

Sources, in order of preference:

1. ``configuration``: the references and ``depends_on`` of each resource
   block in the configuration being planned. These are *direct*
   dependencies. References through ``var.*`` and module outputs are
   followed; references through ``local.*`` cannot be (Terraform does not
   export local values' expressions) and are skipped rather than guessed.
2. ``prior_state`` dependencies, only for resources that are being destroyed
   and therefore have no configuration left. Terraform records these as a
   transitive closure, so they are reduced to the edges not implied by other
   recorded edges. Every edge kept is still a recorded dependency.

Terraform does not export the *previous* configuration, and the dependencies
in ``prior_state`` are refreshed against the new configuration during
planning. An edge between two resources that exist on both sides is
therefore reported as ``present``, not as unchanged or added.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from pydantic import JsonValue

from app.change_model import Action, Relationship, RelationshipStatus
from app.terraform_plan import ConfigModule, Plan, StateModule

# An index key such as [0] or ["blue"], including brackets inside quoted keys.
_INDEX = re.compile(r'\[(?:"(?:[^"\\]|\\.)*"|[^\]]*)\]')
_NON_RESOURCE_ROOTS = frozenset({"local", "count", "each", "path", "terraform", "self", "data"})


def config_address(instance_address: str) -> str:
    """``module.a[0].aws_instance.web["x"]`` -> ``module.a.aws_instance.web``."""
    return _INDEX.sub("", instance_address)


def _module_instances(instance_address: str) -> list[str]:
    """The ``module.name[key]`` segments of an instance address."""
    segments: list[str] = []
    rest = instance_address
    while rest.startswith("module."):
        match = re.match(r'module\.[^.\[]+(?:\[(?:"(?:[^"\\]|\\.)*"|[^\]]*)\])?\.', rest)
        if match is None:
            break
        segments.append(match.group(0)[:-1])
        rest = rest[match.end() :]
    return segments


@dataclass
class _Scope:
    """A module in the configuration tree."""

    prefix: str  # "" for root, "module.a." / "module.a.module.b." otherwise
    module: ConfigModule
    parent: "_Scope | None" = None
    call_name: str | None = None
    children: dict[str, "_Scope"] = field(default_factory=dict)


def _build_scopes(
    module: ConfigModule,
    prefix: str = "",
    parent: _Scope | None = None,
    call_name: str | None = None,
) -> _Scope:
    scope = _Scope(prefix=prefix, module=module, parent=parent, call_name=call_name)
    for name, call in sorted(module.module_calls.items()):
        scope.children[name] = _build_scopes(call.module, f"{prefix}module.{name}.", scope, name)
    return scope


def _iter_scopes(scope: _Scope) -> Iterator[_Scope]:
    yield scope
    for child in scope.children.values():
        yield from _iter_scopes(child)


def _references(expression: JsonValue) -> Iterator[str]:
    """Every ``references`` entry anywhere inside an expression tree."""
    if isinstance(expression, dict):
        refs = expression.get("references")
        if isinstance(refs, list):
            yield from (ref for ref in refs if isinstance(ref, str))
        for key, child in expression.items():
            if key not in ("references", "constant_value"):
                yield from _references(child)
    elif isinstance(expression, list):
        for child in expression:
            yield from _references(child)


class _Resolver:
    """Resolves configuration references to managed-resource config addresses."""

    def __init__(self, root: _Scope) -> None:
        self._managed = {
            scope.prefix + resource.address
            for scope in _iter_scopes(root)
            for resource in scope.module.resources
            if resource.mode == "managed"
        }

    @property
    def managed(self) -> set[str]:
        return self._managed

    def resolve(
        self, ref: str, scope: _Scope, seen: frozenset[tuple[str, str]] = frozenset()
    ) -> set[str]:
        key = (scope.prefix, ref)
        if key in seen:
            return set()
        seen = seen | {key}
        parts = [_INDEX.sub("", part) for part in ref.split(".")]
        root = parts[0]

        if root == "var" and len(parts) >= 2:
            if scope.parent is None or scope.call_name is None:
                return set()
            call = scope.parent.module.module_calls[scope.call_name]
            expression = (
                call.expressions.get(parts[1]) if isinstance(call.expressions, dict) else None
            )
            return self.resolve_all(_references(expression), scope.parent, seen)

        if root == "module" and len(parts) >= 2:
            child = scope.children.get(parts[1])
            if child is None:
                return set()
            outputs = child.module.outputs
            names = [parts[2]] if len(parts) >= 3 else sorted(outputs)
            found: set[str] = set()
            for name in names:
                output = outputs.get(name)
                if output is not None:
                    found |= self.resolve_all(_references(output.expression), child, seen)
            return found

        if root in _NON_RESOURCE_ROOTS or len(parts) < 2:
            return set()
        candidate = f"{scope.prefix}{parts[0]}.{parts[1]}"
        return {candidate} if candidate in self._managed else set()

    def resolve_all(
        self, refs: Iterator[str], scope: _Scope, seen: frozenset[tuple[str, str]]
    ) -> set[str]:
        found: set[str] = set()
        for ref in refs:
            found |= self.resolve(ref, scope, seen)
        return found

    def depends_on(self, entry: str, scope: _Scope) -> set[str]:
        """A ``depends_on`` entry: a resource, or a whole module."""
        parts = [_INDEX.sub("", part) for part in entry.split(".")]
        if parts[0] == "module" and len(parts) == 2:
            child = scope.children.get(parts[1])
            if child is None:
                return set()
            prefix = child.prefix
            return {address for address in self._managed if address.startswith(prefix)}
        return self.resolve(entry, scope)


def _config_dependencies(plan: Plan) -> dict[str, set[str]]:
    """Config address -> config addresses it directly depends on."""
    if plan.configuration is None:
        return {}
    root = _build_scopes(plan.configuration.root_module)
    resolver = _Resolver(root)
    dependencies: dict[str, set[str]] = {}
    for scope in _iter_scopes(root):
        for resource in scope.module.resources:
            if resource.mode != "managed":
                continue
            address = scope.prefix + resource.address
            refs = [
                *_references(resource.expressions),
                *_references(resource.count_expression),
                *_references(resource.for_each_expression),
            ]
            deps = resolver.resolve_all(iter(refs), scope, frozenset())
            for entry in resource.depends_on:
                deps |= resolver.depends_on(entry, scope)
            # Module-level depends_on applies to everything inside the module.
            ancestor: _Scope | None = scope
            while ancestor is not None and ancestor.parent is not None and ancestor.call_name:
                call = ancestor.parent.module.module_calls[ancestor.call_name]
                for entry in call.depends_on:
                    deps |= resolver.depends_on(entry, ancestor.parent)
                ancestor = ancestor.parent
            deps.discard(address)
            dependencies[address] = deps
    return dependencies


def _state_dependencies(plan: Plan) -> dict[str, list[str]]:
    """Instance address -> recorded (transitive) config-address dependencies."""
    if plan.prior_state is None or plan.prior_state.values is None:
        return {}
    recorded: dict[str, list[str]] = {}

    def walk(module: StateModule) -> None:
        for resource in module.resources:
            if resource.mode == "managed":
                recorded[resource.address] = list(resource.depends_on)
        for child in module.child_modules:
            walk(child)

    walk(plan.prior_state.values.root_module)
    return recorded


def build_relationships(plan: Plan, actions: dict[str, Action]) -> list[Relationship]:
    """Edges between the managed resources in ``actions`` (address -> action)."""
    instances_by_config: dict[str, list[str]] = {}
    for address in actions:
        instances_by_config.setdefault(config_address(address), []).append(address)

    def expand(source: str, target_config: str) -> list[str]:
        """Instances of ``target_config`` visible from ``source``.

        Within the same module call, an instance of ``module.a[0]`` only
        depends on resources in ``module.a[0]``, not in ``module.a[1]``.
        """
        source_modules = _module_instances(source)
        shared = 0
        target_parts = target_config.split(".")
        for i, segment in enumerate(_module_instances_config(source)):
            if target_parts[2 * i : 2 * i + 2] == segment.split("."):
                shared = i + 1
            else:
                break
        return [
            target
            for target in instances_by_config.get(target_config, [])
            if _module_instances(target)[:shared] == source_modules[:shared]
        ]

    config_deps = _config_dependencies(plan)
    state_deps = _state_dependencies(plan)
    edges: dict[tuple[str, str], RelationshipStatus] = {}

    for source, action in actions.items():
        source_config = config_address(source)
        if source_config in config_deps:
            for target_config in config_deps[source_config]:
                for target in expand(source, target_config):
                    status = _status(action, actions[target])
                    if status is not None:
                        edges[(source, target)] = status
        elif action == "delete" and source in state_deps:
            for target_config in _reduce_transitive(
                state_deps[source], state_deps, instances_by_config
            ):
                for target in expand(source, target_config):
                    if actions[target] != "create":
                        edges[(source, target)] = "removed"

    return [
        Relationship(source=source, target=target, status=status)
        for (source, target), status in sorted(edges.items())
    ]


def _module_instances_config(instance_address: str) -> list[str]:
    return [_INDEX.sub("", segment) for segment in _module_instances(instance_address)]


def _status(source_action: Action, target_action: Action) -> RelationshipStatus | None:
    created = "create" in (source_action, target_action)
    deleted = "delete" in (source_action, target_action)
    if created and deleted:
        return None  # The edge exists on neither side.
    if created:
        return "added"
    if deleted:
        return "removed"
    return "present"


def _reduce_transitive(
    deps: list[str],
    state_deps: dict[str, list[str]],
    instances_by_config: dict[str, list[str]],
) -> list[str]:
    """Drop recorded dependencies that are implied by another recorded one."""

    def recorded(config: str) -> set[str]:
        found: set[str] = set()
        for instance in instances_by_config.get(config, []):
            found.update(state_deps.get(instance, []))
        return found

    unique = sorted(set(deps))
    implied = set().union(*(recorded(dep) for dep in unique)) if unique else set()
    return [dep for dep in unique if dep not in implied]
