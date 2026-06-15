"""The `RegisterProcedure` command -- intent dataclass for this slice.

Carries the caller-controlled fields:
  - `name` -- operator-readable display name
  - `kind` -- free-form ISA-106 procedure kind discriminator (1-50
    chars after trim; bare str per the Supply.kind lock
    precedent; future StrEnum promotion deferred per
    [[project_operation_design]] Watch item 7)
  - `target_asset_ids` -- frozenset of Asset ids this procedure acts
    on (eventual-consistency: existence not verified at register
    time; gating happens at start_procedure via
    ProcedureStartContext)
  - `parent_run_id` -- optional Run binding (None = standalone
    procedure, set = Phase-of-Run; resolves the Phase aggregate
    question from [[project_run_parameters_design]])

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust / Subject / Equipment / Recipe /
Run / Data / Decision / Supply.

`target_asset_ids` is `frozenset[UUID]` (not `list`) so the command
itself is hashable for `with_idempotency`'s SHA256 hash; the
cross-BC `_normalize_for_hash` helper sorts frozensets for
deterministic hashing across worker processes (locked precedent).

Status is implicit at registration (`Defined`) and not part of the
command -- see Procedure aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class RegisterProcedure:
    """Register a new episodic operational procedure (lands in `Defined`).

    `capability_id` is the optional cross-BC
    binding to the universal Capability template (Recipe BC 6k)
    this Procedure realizes. OPTIONAL by design: many ceremony
    Procedures (bakeouts, sample cleaning, characterization runs) have
    no matching Capability template. When supplied, the handler
    loads the bound Capability + the decider validates that
    `Capability.executor_shapes` contains `Procedure`; otherwise
    raises `ProcedureCapabilityExecutorMismatchError`. Same
    additive shape as Method.capability_id (6l-additive). No
    10d-strict follow-up planned today — Procedure binding stays
    optional unless pilot demand justifies REQUIRED enforcement.
    """

    name: str
    kind: str
    target_asset_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    parent_run_id: UUID | None = None
    capability_id: UUID | None = None
    max_consecutive_unconverged_iterations: int | None = None
    """Optional "patience" cap (>= 1 when set; None = no cap): max
    consecutive unconverged iterations before `start_iteration` refuses
    the next one. Folds onto Procedure state at register time and is read
    by the start_iteration decider; never auto-aborts (mirrors
    Agent.budget). Capability-default inheritance is a deferred follow-up."""
