"""Pure decider for the `DeprecateAssembly` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_assembly but the target is terminal.
Re-deprecating an already-Deprecated Assembly raises
AssemblyCannotDeprecateError (strict-not-idempotent, mirrors
deprecate_family precedent).

Source-state guard uses tuple-membership (same precedent as
deprecate_family / decommission_asset).
"""

from datetime import datetime

from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotDeprecateError,
    AssemblyDeprecated,
    AssemblyNotFoundError,
    AssemblyStatus,
)
from cora.equipment.features.deprecate_assembly.command import DeprecateAssembly

_DEPRECATABLE_STATUSES: tuple[AssemblyStatus, ...] = (
    AssemblyStatus.DEFINED,
    AssemblyStatus.VERSIONED,
)


def decide(
    state: Assembly | None,
    command: DeprecateAssembly,
    *,
    now: datetime,
) -> list[AssemblyDeprecated]:
    """Decide the events produced by deprecating an existing Assembly.

    Invariants:
      - State must not be None -> AssemblyNotFoundError carrying the
        target assembly_id.
      - state.status must be in {Defined, Versioned}
        -> AssemblyCannotDeprecateError carrying the current status.
        Re-deprecating a Deprecated Assembly is strict-not-idempotent.
    """
    if state is None:
        raise AssemblyNotFoundError(command.assembly_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise AssemblyCannotDeprecateError(
            state.id,
            (
                f"current status is {state.status.value}; expected one of "
                f"{', '.join(s.value for s in _DEPRECATABLE_STATUSES)}"
            ),
        )
    return [
        AssemblyDeprecated(
            assembly_id=state.id,
            reason=command.reason.value,
            occurred_at=now,
        )
    ]
