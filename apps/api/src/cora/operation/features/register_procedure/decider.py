"""Pure decider for the `RegisterProcedure` command.

Pure function: given the current Procedure state (None for a fresh
stream) and a `RegisterProcedure` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) -> `ProcedureAlreadyExistsError`
  - `kind` is bare `str`; validated 1-50 chars via the shared
    `validate_bounded_text` helper -> `InvalidProcedureKindError`.
    Per the Supply.kind iter-1 lock precedent, kind is NOT a VO; the
    validator is invoked here at the decider, not in `__post_init__`.
  - `name` is wrapped via `ProcedureName(...)` which validates
    1-200 chars in `__post_init__` -> `InvalidProcedureNameError`.

`target_asset_ids` and `parent_run_id` are NOT validated for
existence here per the eventual-consistency stance (precedent: Trust
Conduit zone refs, Asset parent refs, Method's needed_family_ids).
Existence + Decommissioned-lifecycle gating happens at
start_procedure time via `ProcedureStartContext` (mirrors
`RunStartContext` from the Run BC).

Initial status is implicit `Defined` (event type IS the state-
change indicator; the genesis evolver hardcodes the mapping). Per
universal industrial + cloud-native consensus, registration produces
a "configured but not running" state.
"""

from datetime import datetime
from uuid import UUID

from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    InvalidProcedureKindError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureName,
    ProcedureRegistered,
)
from cora.operation.features.register_procedure.command import RegisterProcedure
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.shared.bounded_text import validate_bounded_text


def decide(
    state: Procedure | None,
    command: RegisterProcedure,
    *,
    capability: Capability | None = None,
    now: datetime,
    new_id: UUID,
) -> list[ProcedureRegistered]:
    """Decide the events produced by registering a new procedure.

    Invariants:
      - State must be None (genesis-only)
        -> ProcedureAlreadyExistsError
      - When capability_id is set, Capability stream must exist
        -> CapabilityNotFoundError
      - When capability_id is set, Capability.executor_shapes must
        contain PROCEDURE
        -> ProcedureCapabilityExecutorMismatchError
      - kind must be valid -> InvalidProcedureKindError
      - Name must be valid -> InvalidProcedureNameError
        (via ProcedureName VO)

    Optional `capability` parameter (additive): the loaded
    Capability state for `command.capability_id` (loaded by
    the handler via the cross-BC port; None when command.capability_id
    is None). When command.capability_id is supplied, the decider
    validates:
      1. capability is not None (Capability stream exists)
         -> CapabilityNotFoundError
      2. capability.executor_shapes contains ExecutorShape.PROCEDURE
         (this Capability accepts Procedure-shaped executors)
         -> ProcedureCapabilityExecutorMismatchError

    Pre-10d test fixtures may omit capability_id entirely; the
    decider skips both guards in that case. Same shape as
    Method.capability_id (6l-additive).
    """
    if state is not None:
        raise ProcedureAlreadyExistsError(state.id)

    if command.capability_id is not None:
        if capability is None:
            raise CapabilityNotFoundError(command.capability_id)
        if ExecutorShape.PROCEDURE not in capability.executor_shapes:
            raise ProcedureCapabilityExecutorMismatchError(new_id, command.capability_id)

    # validate + trim kind (bare str; not a VO per Supply.kind precedent)
    kind = validate_bounded_text(
        command.kind,
        max_length=PROCEDURE_KIND_MAX_LENGTH,
        error_class=InvalidProcedureKindError,
    )
    # validate + trim name via VO
    name = ProcedureName(command.name)

    return [
        ProcedureRegistered(
            procedure_id=new_id,
            name=name.value,
            kind=kind,
            target_asset_ids=tuple(command.target_asset_ids),
            parent_run_id=command.parent_run_id,
            capability_id=command.capability_id,
            occurred_at=now,
        )
    ]
