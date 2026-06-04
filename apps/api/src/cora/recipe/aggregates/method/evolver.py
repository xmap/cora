"""Evolver: replay events to reconstruct Method state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `MethodEvent` without a matching match arm here.

Status mapping per event type:
  - `MethodDefined`              -> DEFINED   (genesis; version=None,
                                                parameters_schema=None)
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
`needed_supplies`, `capability_id`, AND `needed_assembly_ids` through
from prior state. Constructing
`Method(id=..., name=..., status=...)` without explicitly passing
the additive frozenset/optional fields would silently WIPE them to
defaults. Pinned by `test_evolve_<transition>_preserves_needed_family_ids`,
the existing `version` preservation tests, the
`test_evolve_<transition>_preserves_parameters_schema`,
`test_evolve_<transition>_preserves_needed_supplies`,
`test_evolve_<transition>_preserves_capability_id`, and the
`test_evolve_<transition>_preserves_needed_assembly_ids` cases.

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

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodEvent,
    MethodParametersSchemaUpdated,
    MethodVersioned,
)
from cora.recipe.aggregates.method.state import (
    Method,
    MethodName,
    MethodStatus,
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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[MethodEvent]) -> Method | None:
    """Replay a stream of events from the empty initial state."""
    state: Method | None = None
    for event in events:
        state = evolve(state, event)
    return state
