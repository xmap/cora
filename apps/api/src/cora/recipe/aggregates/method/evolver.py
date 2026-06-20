"""Evolver: replay events to reconstruct Method state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `MethodEvent` without a matching match arm here.

Status mapping per event type:
  - `MethodDefined`              -> DEFINED   (genesis; version=None,
                                                parameters_schema=None,
                                                required_roles=empty)
  - `MethodVersioned`            -> VERSIONED (version=event.version_tag;
                                                multi-source: Defined |
                                                Versioned; parameters_schema
                                                preserved)
  - `MethodDeprecated`           -> DEPRECATED (version preserved;
                                                multi-source: Defined |
                                                Versioned; parameters_schema
                                                preserved)
  - `MethodParametersSchemaUpdated` -> status preserved (orthogonal to
                                                lifecycle; updates the
                                                parameters_schema field
                                                only)
  - `MethodRequiredRoleAdded`    -> status preserved (positional
                                                role-tagging workstream;
                                                appends a
                                                RoleRequirement to
                                                required_roles; decider
                                                restricts to Defined)
  - `MethodRequiredRoleRemoved`  -> status preserved (mirror of Added;
                                                removes the role
                                                identified by role_name;
                                                decider restricts to
                                                Defined)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `FamilyDefined → DEFINED` / `SubjectMounted →
MOUNTED`. Mirrors Family's transition evolver shape from
Equipment BC.

`needed_family_ids` is converted from `list[UUID]` (event payload)
to `frozenset[UUID]` (state) here. Order doesn't matter at the state
layer (set semantics for Plan-binding superset checks); the payload
already sorted in `to_payload` for persistence determinism.

`version` is mutated by MethodVersioned (set to the new tag) and
PRESERVED by MethodDeprecated. MethodDefined-only streams fold
cleanly with version=None (the additive-state pattern).

**Critical invariant**: every transition arm MUST carry
`needed_family_ids`, `version`, `parameters_schema`,
`needed_supplies`, `capability_id`, `needed_assembly_ids`, AND the
compute-classification fields (`execution_pattern`,
`monotone_quality`, `resumable_from_checkpoint`), AND `launch_spec`
through from prior state. Constructing
`Method(id=..., name=..., status=...)` without explicitly passing
the additive frozenset/optional fields would silently WIPE them to
defaults. Pinned by `test_evolve_<transition>_preserves_needed_family_ids`,
the existing `version` preservation tests, the
`test_evolve_<transition>_preserves_parameters_schema`,
`test_evolve_<transition>_preserves_needed_supplies`,
`test_evolve_<transition>_preserves_capability_id`, the
`test_evolve_<transition>_preserves_needed_assembly_ids`, and the
`test_evolve_<transition>_preserves_compute_classification` cases.

`needed_supplies` is converted from `list[str]` (event
payload) to `frozenset[str]` (state) here. Order doesn't matter at
the state layer (set semantics); the payload sorted lexically in
`to_payload` for persistence determinism.

Transition events applied to empty state raise ValueError: they can
never appear before `MethodDefined` in a well-formed stream. The
`require_state` helper keeps per-arm bodies short (precedent locked
by Subject's evolver).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.asset import PortDirection
from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodEvent,
    MethodLaunchSpecUpdated,
    MethodParametersSchemaUpdated,
    MethodRequiredRoleAdded,
    MethodRequiredRoleRemoved,
    MethodVersioned,
)
from cora.recipe.aggregates.method.launch_spec import launch_spec_from_dict
from cora.recipe.aggregates.method.state import (
    Method,
    MethodName,
    MethodStatus,
    PortRequirement,
    RoleName,
    RoleRequirement,
)


def evolve(state: Method | None, event: MethodEvent) -> Method:
    """Apply one event to the current state."""
    match event:
        case MethodDefined(
            method_id=method_id,
            name=name,
            needed_family_ids=needed_family_ids,
            needed_supplies=needed_supplies,
            capability_id=capability_id,
            needed_assembly_ids=needed_assembly_ids,
            execution_pattern=execution_pattern,
            monotone_quality=monotone_quality,
            resumable_from_checkpoint=resumable_from_checkpoint,
        ):
            _ = state  # MethodDefined is the genesis event; prior state ignored
            return Method(
                id=method_id,
                name=MethodName(name),
                needed_family_ids=frozenset(needed_family_ids),
                status=MethodStatus.DEFINED,
                # version defaults to None.
                needed_supplies=frozenset(needed_supplies),
                # capability_id flows through genesis. None for
                # legacy streams without the field (additive-state default).
                capability_id=capability_id,
                # needed_assembly_ids flows through genesis. Empty for
                # legacy streams without the field (additive-state default).
                needed_assembly_ids=frozenset(needed_assembly_ids),
                # compute classification flows through genesis. None/False
                # for legacy streams without the fields (additive-state).
                execution_pattern=execution_pattern,
                monotone_quality=monotone_quality,
                resumable_from_checkpoint=resumable_from_checkpoint,
                # required_roles defaults empty at genesis; populated
                # only by subsequent MethodRequiredRoleAdded events.
                # Same additive-state posture as needed_assembly_ids.
            )
        case MethodVersioned(version_tag=version_tag, content_hash=content_hash):
            prior = require_state(state, "MethodVersioned")
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=MethodStatus.VERSIONED,
                version=version_tag,
                # content_hash loaded from event payload (captured by
                # decider per non-determinism principle). None for
                # pre-rollout legacy events.
                content_hash=content_hash,
                parameters_schema=prior.parameters_schema,
                needed_supplies=prior.needed_supplies,
                # capability_id PRESERVED across versioning (Method
                # operates as the same Capability executor across
                # revisions; rebinding would mean a new Method).
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                # compute classification PRESERVED across every transition
                # (part of content identity; omitting it would silently wipe
                # the fields to defaults, the critical invariant the
                # evolver docstring warns about).
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                # launch_spec PRESERVED across every transition (part of
                # content identity; omitting it would silently wipe the
                # recipe to None, the critical invariant below).
                launch_spec=prior.launch_spec,
                # required_roles PRESERVED across versioning; the
                # role declarations are part of the content the
                # version_tag attests to (Method.content_subset
                # includes required_roles).
                required_roles=prior.required_roles,
            )
        case MethodDeprecated():
            prior = require_state(state, "MethodDeprecated")
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=MethodStatus.DEPRECATED,
                # version preserved across deprecation.
                version=prior.version,
                # content_hash preserved across deprecation; represents
                # the LAST ATTESTED revision and remains a valid
                # equivalence anchor for the deprecated definition.
                content_hash=prior.content_hash,
                parameters_schema=prior.parameters_schema,
                needed_supplies=prior.needed_supplies,
                # capability_id PRESERVED across deprecation; audit-
                # critical (the historical Capability binding stays
                # visible).
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                # compute classification PRESERVED across every transition
                # (part of content identity; omitting it would silently wipe
                # the fields to defaults, the critical invariant the
                # evolver docstring warns about).
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                # launch_spec PRESERVED across every transition (part of
                # content identity; omitting it would silently wipe the
                # recipe to None, the critical invariant below).
                launch_spec=prior.launch_spec,
                # required_roles PRESERVED across deprecation; the
                # declared roles remain part of the historical record.
                required_roles=prior.required_roles,
            )
        case MethodParametersSchemaUpdated(parameters_schema=parameters_schema):
            prior = require_state(state, "MethodParametersSchemaUpdated")
            # Shallow-copy parameters_schema so payload mutation can't alias state (B1).
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=prior.status,
                version=prior.version,
                # content_hash preserved: schema updates between
                # MethodVersioned events leave the hash pointing at the
                # prior attested revision. The drift between
                # current parameters_schema and the hashed snapshot is
                # the intended signal that the Method has uncommitted
                # changes (Bazel input/output split semantics, see
                # [[project_content_addressed_identity_design]]).
                content_hash=prior.content_hash,
                parameters_schema=(
                    dict(parameters_schema) if parameters_schema is not None else None
                ),
                needed_supplies=prior.needed_supplies,
                # capability_id PRESERVED across schema updates;
                # parameters_schema and capability binding evolve
                # independently.
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                # compute classification PRESERVED across every transition
                # (part of content identity; omitting it would silently wipe
                # the fields to defaults, the critical invariant the
                # evolver docstring warns about).
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                # launch_spec PRESERVED across every transition (part of
                # content identity; omitting it would silently wipe the
                # recipe to None, the critical invariant below).
                launch_spec=prior.launch_spec,
                # required_roles PRESERVED across schema updates; the
                # two fields evolve independently.
                required_roles=prior.required_roles,
            )
        case MethodLaunchSpecUpdated(launch_spec=launch_spec):
            prior = require_state(state, "MethodLaunchSpecUpdated")
            # Orthogonal to lifecycle (like the parameters_schema arm):
            # status / version / content_hash preserved; only launch_spec
            # changes (None clears it).
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=prior.status,
                version=prior.version,
                content_hash=prior.content_hash,
                parameters_schema=prior.parameters_schema,
                needed_supplies=prior.needed_supplies,
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                launch_spec=(
                    launch_spec_from_dict(launch_spec) if launch_spec is not None else None
                ),
                required_roles=prior.required_roles,
            )
        case MethodRequiredRoleAdded(
            role_name=role_name,
            role_kind=role_kind,
            family_id=family_id,
            required_ports=required_ports,
            optional=optional,
        ):
            prior = require_state(state, "MethodRequiredRoleAdded")
            # Reconstruct the RoleRequirement VO from the payload dicts.
            # XOR invariant enforced by RoleRequirement.__post_init__:
            # exactly one of role_kind / family_id is set (3D Lock 5).
            ports = frozenset(
                PortRequirement(
                    port_name=p["port_name"],
                    direction=PortDirection(p["direction"]),
                    signal_type=p["signal_type"],
                )
                for p in required_ports
            )
            new_role = RoleRequirement(
                role_name=RoleName(role_name),
                role_kind=role_kind,
                family_id=family_id,
                required_ports=ports,
                optional=optional,
            )
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=prior.status,
                version=prior.version,
                content_hash=prior.content_hash,
                parameters_schema=prior.parameters_schema,
                needed_supplies=prior.needed_supplies,
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                # compute classification PRESERVED across every transition
                # (part of content identity; omitting it would silently wipe
                # the fields to defaults, the critical invariant the
                # evolver docstring warns about).
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                # launch_spec PRESERVED across every transition (part of
                # content identity; omitting it would silently wipe the
                # recipe to None, the critical invariant below).
                launch_spec=prior.launch_spec,
                required_roles=prior.required_roles | {new_role},
            )
        case MethodRequiredRoleRemoved(role_name=role_name):
            prior = require_state(state, "MethodRequiredRoleRemoved")
            # Identity-by-role_name: drop the unique entry whose
            # role_name matches. Decider rejects unknown role_names so
            # the filtered set is always strictly smaller by one.
            target = RoleName(role_name)
            remaining = frozenset(role for role in prior.required_roles if role.role_name != target)
            return Method(
                id=prior.id,
                name=prior.name,
                needed_family_ids=prior.needed_family_ids,
                status=prior.status,
                version=prior.version,
                content_hash=prior.content_hash,
                parameters_schema=prior.parameters_schema,
                needed_supplies=prior.needed_supplies,
                capability_id=prior.capability_id,
                needed_assembly_ids=prior.needed_assembly_ids,
                # compute classification PRESERVED across every transition
                # (part of content identity; omitting it would silently wipe
                # the fields to defaults, the critical invariant the
                # evolver docstring warns about).
                execution_pattern=prior.execution_pattern,
                monotone_quality=prior.monotone_quality,
                resumable_from_checkpoint=prior.resumable_from_checkpoint,
                # launch_spec PRESERVED across every transition (part of
                # content identity; omitting it would silently wipe the
                # recipe to None, the critical invariant below).
                launch_spec=prior.launch_spec,
                required_roles=remaining,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[MethodEvent]) -> Method | None:
    """Replay a stream of events from the empty initial state."""
    state: Method | None = None
    for event in events:
        state = evolve(state, event)
    return state
