"""Domain events emitted by the Procedure aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`ProcedureRegistered` is the genesis event. FSM-closure transitions:
  - `ProcedureStarted` -- single-source genesis transition (Defined ->
    Running). Slim payload: procedure_id + occurred_at. Mirrors
    `RunStarted`'s no-status convention; the start fact is what the
    event encodes.
  - `ProcedureCompleted` -- happy-path terminal (Running -> Completed).
    Slim payload by design; substantive completion summary (step count,
    duration, final check pass-rate) deferred until the step logbook
    has accreted real consumer signal.
  - `ProcedureAborted` -- emergency-exit terminal (Running -> Aborted).
    Payload carries `procedure_id` + free-form `reason: str` (1-500
    chars after trimming) + `occurred_at`. Mirrors RunAborted's reason
    shape exactly (free-form by design; structured taxonomy future-
    additive on the same triggers documented at
    `InvalidProcedureAbortReasonError`).

`ProcedureActivitiesLogbookOpened` is the lazy envelope event for the
per-step logbook table. `ProcedureTruncated` mirrors RunTruncated.
`ProcedureHeld` / `ProcedureResumed` are deferred until the pilot
needs the surface.

`ProcedureIterationStarted` / `ProcedureIterationEnded` are the
first-class boundary pair for the convergence-driven iteration loop
(alignment sweeps and the like). They are operator-emitted and
optional: a non-iterative Procedure (bakeout) never emits them and
pays zero tax. Iteration is NOT a `ProcedureStatus` value (Running
stays monolithic); the pair folds onto two additive state fields
(`current_iteration_index`, `iteration_count`). `iteration_index` is
operator-supplied (capture-don't-recompute); the start decider
enforces a strict-successor invariant server-side. `ProcedureIterationEnded`
carries the convergence verdict (`converged: bool | None`, None when an
iteration ends without a verdict) and an optional free-form `reason`.
Naming mirrors `ProcedureActivitiesLogbookOpened` (aggregate +
sub-entity noun + past participle).

## Payload conventions

`target_asset_ids` is stored as `tuple[UUID, ...]` in payloads (events
carry primitives; tuples JSON-serialize cleanly and are immutable
so the fold step can't alias a mutable list into state). The evolver
converts to `frozenset` when folding into Procedure state. The values
are sorted by string form in `to_payload` so the same logical Asset
set serializes deterministically -- important for hash-based
idempotency. Same precedent as Method's needed_family_ids and Plan's
asset_ids.

`parent_run_id` is stored as `str | None` in payloads (UUID
serialized via `str()` when present). Optional binding: standalone
procedures (bakeouts, characterization runs between Runs) have None;
Phase-of-Run procedures have the parent Run's id.

Status is NOT carried in event payloads -- the event type itself
encodes the state change. Same precedent as `RunStarted` /
`SupplyRegistered` / `SubjectMounted`.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.canonical_json import canonical_json_bytes
from cora.shared.logbook import LogbookSchema


@dataclass(frozen=True)
class ProcedureRegistered:
    """A new procedure was registered (lands in `Defined`).

    Status is implicit (`Defined`) -- the evolver sets it.

    `target_asset_ids` carries the Asset ids the procedure acts on;
    eventual-consistency stance, no cross-aggregate verification at
    register time. Existence + Decommissioned-lifecycle gating
    happens at start_procedure time via `ProcedureStartContext`.

    `parent_run_id` carries the optional Run binding (None for
    standalone procedures, set for Phase-of-Run procedures).

    `capability_id` is the optional cross-BC binding to the universal
    Capability template (Recipe BC) this Procedure realizes as a
    Procedure-shaped executor. None for legacy Procedures and for
    ceremony Procedures with no template binding. Same additive shape
    as Method.capability_id.

    `recipe_id` is the optional cross-BC binding to the Recipe whose
    steps were expanded into this Procedure via the
    `register_procedure_from_recipe` slice. None for legacy Procedures
    (registered via `register_procedure` with inline steps) and for
    ceremony Procedures with no Recipe binding. When set,
    `capability_id` carries the Recipe's `capability_id` as a denorm
    for audit-by-Capability read paths without requiring a Recipe
    join. Additive payload field; pre-rewrite streams fold via
    `payload.get("recipe_id")` -> None.
    """

    procedure_id: UUID
    name: str
    kind: str
    target_asset_ids: tuple[UUID, ...]
    parent_run_id: UUID | None
    occurred_at: datetime
    capability_id: UUID | None = None
    recipe_id: UUID | None = None
    max_consecutive_unconverged_iterations: int | None = None
    """Optional operator-supplied 'patience' cap (>= 1, None = no cap):
    max consecutive unconverged iterations before start_iteration refuses
    the next one. Additive payload field; legacy streams fold via
    `payload.get("max_consecutive_unconverged_iterations")` -> None."""


@dataclass(frozen=True)
class RecipeExpansionRecorded:
    """Provenance event: a Recipe's steps were expanded into this Procedure.

    Emitted alongside `ProcedureRegistered` by the
    `register_procedure_from_recipe` slice, NOT by `register_procedure`.
    Captures the template-invocation grain provenance per the design
    lock ([[project-recipe-aggregate-design]]): one event per Recipe
    invocation, NOT one per expanded step. Per-step records live in
    `entries_operation_procedure_activities` via the existing
    `append_activities` handler; this event lifts the binding
    context above the per-step granularity so PROV-O / 21 CFR Part 11
    audit trails point at the activity that produced the entity, not
    at every intermediate state.

    `recipe_id` is the Recipe whose steps were expanded. `recipe_version`
    pins which Recipe-version's steps were active at expansion time
    (without this, replay after a `version_recipe` call would resolve
    to different steps and lose determinism).

    `capability_id` + `capability_version` are denormalized for
    audit-by-Capability read paths (find all Procedures expanded from
    this Capability) without requiring a Recipe join. Recipe.capability_id
    is the source of truth; the denorm here mirrors the Procedure
    aggregate state pin per anti-hook 15 of [[project-recipe-aggregate-design]].

    `bindings` carries the operator-supplied parameter values verbatim
    for replay (serialized via `json.dumps(..., sort_keys=True)` for
    canonical-JSON content hashing). `expansion_port_version` records
    which expander emitted the steps (the design memo's "non-determinism
    captured via port injection" principle). `steps_hash` (renamed from
    the worktree's `template_hash`) + `bindings_hash` are content-hashes
    enabling cheap equality checks at projection time; `step_count` is
    the number of expanded Steps the slice paginated through.

    Provenance-only: the evolver leaves `Procedure` state unchanged
    when this event arrives. Replay of `(recipe_id, recipe_version,
    bindings, expansion_port_version)` reconstructs the step sequence
    deterministically by re-loading Recipe at the recorded version and
    re-running expand.
    """

    procedure_id: UUID
    recipe_id: UUID
    recipe_version: str | None
    capability_id: UUID
    capability_version: str | None
    bindings: Mapping[str, Any]
    expansion_port_version: str
    steps_hash: str
    bindings_hash: str
    step_count: int
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureStarted:
    """A Procedure transitioned out of Defined into Running (10c-b).

    Slim payload by design: the start fact is what the event encodes.
    Status is implicit (`Running`); the evolver sets it. No reason
    field (mirrors RunStarted; the operator already supplied name +
    kind + targets at register time).

    The `start_procedure` handler pre-loads each target Asset before
    reaching the decider; Decommissioned-state guarding lives in the
    decider via `ProcedureStartContext` (mirror of `RunStartContext`).
    """

    procedure_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureCompleted:
    """A Procedure reached its happy-path terminal (Running -> Completed).

    Slim payload by design (mirrors RunCompleted): substantive
    completion summary (step count, final check pass-rate, duration)
    deferred until the step logbook consumer signal surfaces. Today
    consumers needing post-completion read state should fold the
    Procedure stream (short and bounded for terminal-by-design
    Lifecycle Aggregates).

    `actuation_kind` is the raw `ActuationKind` value (Physical /
    Simulated / Hybrid) the Conductor observed during this conduct, or
    None when nothing instrumented was actuated (no routing table, no
    control-port write) or the complete was issued outside a conduct.
    Additive payload field: legacy streams fold via
    `payload.get("actuation_kind")` -> None. This is the gate carrier
    the Data BC reads back at Dataset registration.
    """

    procedure_id: UUID
    occurred_at: datetime
    actuation_kind: str | None = None


@dataclass(frozen=True)
class ProcedureActivitiesLogbookOpened:
    """A steps logbook was attached to this Procedure.

    Naming note: this event carries the entry-noun (`Steps`) in its name,
    vs. Conduit/Decision's bare `<Aggregate>LogbookOpened`. Same rationale
    as Run BC's `RunObservationLogbookOpened`: Procedure is planned to host
    multiple logbook kinds in the future (operator-action audit, hazard
    observations are likely future additions), so the event name carries
    the entry-noun discriminator upfront. Per
    [[project_logbook_entry_storage]] cross-BC family table.

    Lazy open-on-first-write: emitted by the `append_activities`
    handler the first time a step is appended for this Procedure, NOT by
    `start_procedure` (mirrors Decision BC's precedent for
    `DecisionLogbookOpened` and Run BC's precedent for
    `RunObservationLogbookOpened`). Subsequent appends find the logbook
    already attached and skip the open-event emission.

    `kind` discriminates the logbook category. Today only
    `LOGBOOK_KIND_ACTIVITY` from state.py; future per-Procedure logbook
    kinds (operator-action audit, hazard) would use distinct constants
    and distinct state fields, not additional values for `kind` here.

    `schema` declares the row shape of `entries_operation_procedure_activities`,
    documenting the polymorphic `(step_kind, payload, sampled_at,
    occurred_at, recorded_at)` shape for downstream projections.

    No `ProcedureStepsLogbookClosed` event today: Procedure.status
    terminals (Completed | Aborted | Truncated) are the implicit close
    signal; `append_activities` rejects writes when status is not
    Running via `ProcedureStepsLogbookClosedError`. Audit fidelity is
    preserved: the open event timestamps the logbook lifecycle start;
    the terminal ProcedureCompleted / ProcedureAborted / etc. event
    timestamps the lifecycle end.
    """

    procedure_id: UUID
    logbook_id: UUID
    kind: str
    schema: LogbookSchema
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureTruncated:
    """A Procedure reached its partial-data terminal (Running -> Truncated, 10c-c).

    Cleanup terminal for a Procedure that became de-facto dead through
    interruption (power loss, process crash, hardware fault, weekend
    interruption) and is being closed retroactively by an operator.
    The Procedure was already over before the operator could mark it;
    truncation captures that fact.

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Same shape and future-additive
    structured-taxonomy posture as ProcedureAborted's reason.

    `interrupted_at` is the operator's best guess at when the actual
    interruption occurred (None when unknown). Distinct from
    `occurred_at`, which is when the truncate command was processed.
    The two timestamps can be hours or days apart for weekend /
    overnight interruptions; the explicit field saves auditors from
    parsing the free-text reason for a date.

    Truncated vs Aborted (lifecycle-layer distinction): Aborted is an
    emergency exit while the system is still responsive; Truncated is
    a cleanup mechanism for known-dead Procedures. The system itself
    does not detect de-facto-dead Procedures (separate liveness
    concern, out of scope for 10c-c); operators must invoke truncate
    explicitly. Mirrors `RunTruncated` from Run BC's 6f-4.
    """

    procedure_id: UUID
    reason: str
    interrupted_at: datetime | None
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureAborted:
    """A Procedure reached its emergency-exit terminal (Running -> Aborted).

    `reason` is a free-form string (1-500 chars after trimming),
    captured verbatim from the operator. Mirror of RunAborted.reason
    shape; same future-additive structured-taxonomy posture parked
    at `InvalidProcedureAbortReasonError`.

    `actuation_kind` is the raw `ActuationKind` value the Conductor
    observed before the abort (routes attempted before the failing step
    still taint it), or None. Additive payload field: legacy streams
    fold via `payload.get("actuation_kind")` -> None. Carries honest
    provenance for a Dataset produced by an aborted conduct.

    Single-source guard at the decider (Running only). Held/Resumed
    deferred to 10c-c per pilot need; if Held lands, the abort source
    set widens to `Running | Held` to match Run BC's precedent.
    """

    procedure_id: UUID
    reason: str
    occurred_at: datetime
    actuation_kind: str | None = None


@dataclass(frozen=True)
class ProcedureIterationStarted:
    """One convergence-loop iteration began on a Running Procedure.

    Operator-emitted boundary event (optional; non-iterative Procedures
    never emit it). `iteration_index` is operator-supplied per the
    capture-don't-recompute principle; the `start_iteration` decider
    enforces the strict-successor invariant (`iteration_index ==
    iteration_count + 1`) and rejects starting while another iteration
    is still open. The evolver bumps `iteration_count` and records the
    open index in `current_iteration_index`.

    Status is NOT carried (iteration is orthogonal to the lifecycle FSM;
    the Procedure stays Running across iterations). Slim payload:
    procedure_id + iteration_index + occurred_at.
    """

    procedure_id: UUID
    iteration_index: int
    occurred_at: datetime


@dataclass(frozen=True)
class ProcedureIterationEnded:
    """The currently-open convergence-loop iteration closed.

    `iteration_index` must match the open `current_iteration_index`
    (validated at the `end_iteration` decider). `converged` carries the
    convergence verdict: True (the iteration met its target), False (it
    did not), or None (the iteration ended without a verdict, for
    example an inconclusive or interrupted pass). `reason` is an
    optional free-form note; when present it is trimmed and bounded
    1-500 chars at the decider (matching abort / truncate), so the
    persisted value is post-trim and whitespace-only is rejected. The
    evolver clears `current_iteration_index` back to None;
    `iteration_count` is unchanged (the count tracks iterations begun).

    `converged` / `reason` are stream-only for now: the convergence-rate
    projection is a deferred watch item per
    [[project_iteration_first_class_research]]. Status is NOT carried.
    """

    procedure_id: UUID
    iteration_index: int
    converged: bool | None
    reason: str | None
    occurred_at: datetime


# Discriminated union of every event the Procedure aggregate emits.
# The FSM is closed by the three transition events; the per-step
# logbook envelope event `ProcedureActivitiesLogbookOpened` opens lazily
# on first append; the iteration boundary pair
# (`ProcedureIterationStarted` / `ProcedureIterationEnded`) folds onto
# the iteration denorm without touching the lifecycle status.
ProcedureEvent = (
    ProcedureRegistered
    | ProcedureStarted
    | ProcedureCompleted
    | ProcedureAborted
    | ProcedureTruncated
    | ProcedureActivitiesLogbookOpened
    | ProcedureIterationStarted
    | ProcedureIterationEnded
    | RecipeExpansionRecorded
)


def event_type_name(event: ProcedureEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ProcedureEvent) -> dict[str, Any]:
    """Serialize a Procedure event to a JSON-friendly dict for jsonb storage.

    `target_asset_ids` is sorted by UUID string form so the persisted
    payload is deterministic -- same logical Asset set, same payload
    bytes, same idempotency hash. Same precedent as Method's
    PolicyDefined / MethodDefined.
    """
    match event:
        case ProcedureRegistered(
            procedure_id=procedure_id,
            name=name,
            kind=kind,
            target_asset_ids=target_asset_ids,
            parent_run_id=parent_run_id,
            occurred_at=occurred_at,
            capability_id=capability_id,
            recipe_id=recipe_id,
            max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
        ):
            return {
                "procedure_id": str(procedure_id),
                "name": name,
                "kind": kind,
                "target_asset_ids": sorted(str(a) for a in target_asset_ids),
                "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
                # None when register_procedure omits capability_id.
                # Pre-10d streams fold via `.get("capability_id")` in
                # from_stored. Mirrors Method.capability_id (6l-additive).
                "capability_id": str(capability_id) if capability_id is not None else None,
                # None when register_procedure (legacy slice) omits
                # recipe_id. register_procedure_from_recipe sets both
                # `recipe_id` and the denorm `capability_id` to the
                # Recipe's capability_id. Pre-rewrite streams fold via
                # `.get("recipe_id")` in from_stored.
                "recipe_id": str(recipe_id) if recipe_id is not None else None,
                # Optional patience cap (None = no cap). Legacy streams fold
                # via `.get("max_consecutive_unconverged_iterations")` -> None.
                "max_consecutive_unconverged_iterations": max_consecutive_unconverged_iterations,
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureStarted(procedure_id=procedure_id, occurred_at=occurred_at):
            return {
                "procedure_id": str(procedure_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureCompleted(
            procedure_id=procedure_id,
            occurred_at=occurred_at,
            actuation_kind=actuation_kind,
        ):
            return {
                "procedure_id": str(procedure_id),
                "occurred_at": occurred_at.isoformat(),
                # Raw ActuationKind value or None. Pre-activation streams
                # fold via `.get("actuation_kind")` -> None in from_stored.
                "actuation_kind": actuation_kind,
            }
        case ProcedureAborted(
            procedure_id=procedure_id,
            reason=reason,
            occurred_at=occurred_at,
            actuation_kind=actuation_kind,
        ):
            return {
                "procedure_id": str(procedure_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
                "actuation_kind": actuation_kind,
            }
        case ProcedureTruncated(
            procedure_id=procedure_id,
            reason=reason,
            interrupted_at=interrupted_at,
            occurred_at=occurred_at,
        ):
            interrupted_at_iso = interrupted_at.isoformat() if interrupted_at is not None else None
            return {
                "procedure_id": str(procedure_id),
                "reason": reason,
                "interrupted_at": interrupted_at_iso,
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureActivitiesLogbookOpened(
            procedure_id=procedure_id,
            logbook_id=logbook_id,
            kind=kind,
            schema=schema,
            occurred_at=occurred_at,
        ):
            return {
                "procedure_id": str(procedure_id),
                "logbook_id": str(logbook_id),
                "kind": kind,
                "schema": schema.to_dict(),
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureIterationStarted(
            procedure_id=procedure_id,
            iteration_index=iteration_index,
            occurred_at=occurred_at,
        ):
            return {
                "procedure_id": str(procedure_id),
                "iteration_index": iteration_index,
                "occurred_at": occurred_at.isoformat(),
            }
        case ProcedureIterationEnded(
            procedure_id=procedure_id,
            iteration_index=iteration_index,
            converged=converged,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "procedure_id": str(procedure_id),
                "iteration_index": iteration_index,
                "converged": converged,
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case RecipeExpansionRecorded(
            procedure_id=procedure_id,
            recipe_id=recipe_id,
            recipe_version=recipe_version,
            capability_id=capability_id,
            capability_version=capability_version,
            bindings=bindings,
            expansion_port_version=expansion_port_version,
            steps_hash=steps_hash,
            bindings_hash=bindings_hash,
            step_count=step_count,
            occurred_at=occurred_at,
        ):
            # Canonical-JSON bytes via the shared `canonical_json_bytes`
            # helper, then `json.loads` to keep the persisted `bindings`
            # field a dict (matches `from_stored`'s `dict(payload['bindings'])`
            # consumer at line 528). The single-source canonicalizer keeps
            # `sha256(payload['bindings'])` reproducible against the
            # decider's at-write `bindings_hash`. Recipe.steps wire-format
            # is JSON-friendly by construction (no UUID values inside).
            return {
                "procedure_id": str(procedure_id),
                "recipe_id": str(recipe_id),
                "recipe_version": recipe_version,
                "capability_id": str(capability_id),
                "capability_version": capability_version,
                "bindings": json.loads(canonical_json_bytes(dict(bindings))),
                "expansion_port_version": expansion_port_version,
                "steps_hash": steps_hash,
                "bindings_hash": bindings_hash,
                "step_count": step_count,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ProcedureEvent:
    """Rebuild a Procedure event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    NOTE: today this uses strict `payload[...]` indexing because every
    key in `ProcedureRegistered` is required at the schema level. When
    future iterations add optional facets to the genesis payload (for
    example `expected_step_count`, `trigger_source`,
    `requested_supply_kinds`), those new keys MUST use
    `payload.get("k", default)` so legacy streams fold cleanly without
    backfill. Same additive-evolution pattern as
    `recipe/aggregates/method/events.py:from_stored`
    (`needed_supplies` was added that way).
    """
    payload = stored.payload
    match stored.event_type:
        case "ProcedureRegistered":

            def _build_registered() -> ProcedureRegistered:
                raw_parent = payload["parent_run_id"]
                # capability_id and recipe_id are OPTIONAL on the payload.
                # Pre-binding streams omit capability_id; pre-Recipe-rewrite
                # streams omit recipe_id. Fold via `.get` -> None default.
                # Mirrors Method.capability_id additive-evolution pattern.
                raw_capability = payload.get("capability_id")
                raw_recipe = payload.get("recipe_id")
                return ProcedureRegistered(
                    procedure_id=UUID(payload["procedure_id"]),
                    name=payload["name"],
                    kind=payload["kind"],
                    target_asset_ids=tuple(UUID(a) for a in payload["target_asset_ids"]),
                    parent_run_id=UUID(raw_parent) if raw_parent is not None else None,
                    capability_id=UUID(raw_capability) if raw_capability is not None else None,
                    recipe_id=UUID(raw_recipe) if raw_recipe is not None else None,
                    # Optional patience cap; legacy streams omit the key.
                    max_consecutive_unconverged_iterations=payload.get(
                        "max_consecutive_unconverged_iterations"
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("ProcedureRegistered", _build_registered)
        case "ProcedureStarted":
            return deserialize_or_raise(
                "ProcedureStarted",
                lambda: ProcedureStarted(
                    procedure_id=UUID(payload["procedure_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ProcedureCompleted":
            return deserialize_or_raise(
                "ProcedureCompleted",
                lambda: ProcedureCompleted(
                    procedure_id=UUID(payload["procedure_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    # Additive: pre-activation streams omit the key -> None.
                    actuation_kind=payload.get("actuation_kind"),
                ),
            )
        case "ProcedureAborted":
            return deserialize_or_raise(
                "ProcedureAborted",
                lambda: ProcedureAborted(
                    procedure_id=UUID(payload["procedure_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    actuation_kind=payload.get("actuation_kind"),
                ),
            )
        case "ProcedureTruncated":

            def _build_truncated() -> ProcedureTruncated:
                raw_interrupted_at = payload["interrupted_at"]
                return ProcedureTruncated(
                    procedure_id=UUID(payload["procedure_id"]),
                    reason=payload["reason"],
                    interrupted_at=(
                        datetime.fromisoformat(raw_interrupted_at)
                        if raw_interrupted_at is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("ProcedureTruncated", _build_truncated)
        case "ProcedureActivitiesLogbookOpened":
            return deserialize_or_raise(
                "ProcedureActivitiesLogbookOpened",
                lambda: ProcedureActivitiesLogbookOpened(
                    procedure_id=UUID(payload["procedure_id"]),
                    logbook_id=UUID(payload["logbook_id"]),
                    kind=payload["kind"],
                    schema=LogbookSchema.from_dict(payload["schema"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ProcedureIterationStarted":
            return deserialize_or_raise(
                "ProcedureIterationStarted",
                lambda: ProcedureIterationStarted(
                    procedure_id=UUID(payload["procedure_id"]),
                    iteration_index=int(payload["iteration_index"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ProcedureIterationEnded":
            return deserialize_or_raise(
                "ProcedureIterationEnded",
                lambda: ProcedureIterationEnded(
                    procedure_id=UUID(payload["procedure_id"]),
                    iteration_index=int(payload["iteration_index"]),
                    converged=payload["converged"],
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "RecipeExpansionRecorded":
            return deserialize_or_raise(
                "RecipeExpansionRecorded",
                lambda: RecipeExpansionRecorded(
                    procedure_id=UUID(payload["procedure_id"]),
                    recipe_id=UUID(payload["recipe_id"]),
                    recipe_version=payload.get("recipe_version"),
                    capability_id=UUID(payload["capability_id"]),
                    capability_version=payload.get("capability_version"),
                    bindings=dict(payload["bindings"]),
                    expansion_port_version=payload["expansion_port_version"],
                    steps_hash=payload["steps_hash"],
                    bindings_hash=payload["bindings_hash"],
                    step_count=int(payload["step_count"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown ProcedureEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ProcedureAborted",
    "ProcedureActivitiesLogbookOpened",
    "ProcedureCompleted",
    "ProcedureEvent",
    "ProcedureIterationEnded",
    "ProcedureIterationStarted",
    "ProcedureRegistered",
    "ProcedureStarted",
    "ProcedureTruncated",
    "RecipeExpansionRecorded",
    "event_type_name",
    "from_stored",
    "to_payload",
]
