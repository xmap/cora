"""Pure decider for the `DeprecateClearanceTemplate` command.

Single-source transition: `Active -> Deprecated`. Strict-not-idempotent.

## Validation

  - State must not be None -> `ClearanceTemplateNotFoundError`
  - Current status must be `Active` -> `ClearanceTemplateCannotDeprecateError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotDeprecateError,
    ClearanceTemplateDeprecated,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
)
from cora.safety.features.deprecate_clearance_template.command import (
    DeprecateClearanceTemplate,
)
from cora.shared.identity import ActorId

_DEPRECATABLE_STATUSES: tuple[ClearanceTemplateStatus, ...] = (ClearanceTemplateStatus.ACTIVE,)


def decide(
    state: ClearanceTemplate | None,
    command: DeprecateClearanceTemplate,
    *,
    now: datetime,
    deprecated_by: ActorId,
) -> list[ClearanceTemplateDeprecated]:
    """Decide the events produced by deprecating an Active clearance template.

    Invariants:
      - State must not be None -> ClearanceTemplateNotFoundError
      - Current status must be Active
        -> ClearanceTemplateCannotDeprecateError
    """
    if state is None:
        raise ClearanceTemplateNotFoundError(command.template_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise ClearanceTemplateCannotDeprecateError(state.id, state.status)

    return [
        ClearanceTemplateDeprecated(
            template_id=state.id,
            reason=command.reason.value,
            occurred_at=now,
            deprecated_by=deprecated_by,
        )
    ]
