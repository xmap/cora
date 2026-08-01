"""Unit tests for the `withdraw_clearance_template` slice's pure decider.

Pins the terminal `Draft | Active | Deprecated -> Withdrawn` transition
and the strict-not-idempotent rule on the already-Withdrawn terminal:
missing state raises `ClearanceTemplateNotFoundError`; an
already-Withdrawn state raises
`ClearanceTemplateCannotWithdrawError` carrying the current status.
The decider is a pure function over
`(state, command, now, withdrawn_by)` and threads the withdrawer's
ActorId onto the emitted event.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotWithdrawError,
    ClearanceTemplateCode,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    ClearanceTemplateWithdrawn,
)
from cora.safety.features.withdraw_clearance_template import (
    WithdrawClearanceTemplate,
    decide,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_DEFINED_AT = datetime(2026, 6, 9, 9, 0, 0, tzinfo=UTC)
_DEFINER_ID = ActorId(UUID("00000000-0000-0000-0000-000000000011"))
_WITHDRAWER_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))


def _template(
    *,
    template_id: UUID,
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.ACTIVE,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode("aps"),
        code=ClearanceTemplateCode("esaf"),
        title=ClearanceTemplateTitle("ESAF Form"),
        defined_at=_DEFINED_AT,
        defined_by=_DEFINER_ID,
        status=status,
        version=ClearanceTemplateVersion(1),
    )


@pytest.mark.unit
def test_decide_emits_withdrawn_event_when_status_is_draft() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DRAFT)
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        withdrawn_by=_WITHDRAWER_ID,
    )

    assert events == [
        ClearanceTemplateWithdrawn(
            reason="policy change",
            template_id=template_id,
            occurred_at=_NOW,
            withdrawn_by=_WITHDRAWER_ID,
        )
    ]


@pytest.mark.unit
def test_decide_emits_withdrawn_event_when_status_is_active() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.ACTIVE)
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        withdrawn_by=_WITHDRAWER_ID,
    )

    assert events == [
        ClearanceTemplateWithdrawn(
            reason="policy change",
            template_id=template_id,
            occurred_at=_NOW,
            withdrawn_by=_WITHDRAWER_ID,
        )
    ]


@pytest.mark.unit
def test_decide_emits_withdrawn_event_when_status_is_deprecated() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DEPRECATED)
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        withdrawn_by=_WITHDRAWER_ID,
    )

    assert events == [
        ClearanceTemplateWithdrawn(
            reason="policy change",
            template_id=template_id,
            occurred_at=_NOW,
            withdrawn_by=_WITHDRAWER_ID,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    template_id = uuid4()
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            withdrawn_by=_WITHDRAWER_ID,
        )
    assert exc_info.value.template_id == template_id


@pytest.mark.unit
def test_decide_rejects_when_status_is_withdrawn() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.WITHDRAWN)
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    with pytest.raises(ClearanceTemplateCannotWithdrawError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            withdrawn_by=_WITHDRAWER_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.WITHDRAWN


@pytest.mark.unit
def test_decide_threads_withdrawn_by_onto_event() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.ACTIVE)
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)
    distinct_actor = ActorId(UUID("00000000-0000-0000-0000-0000000000aa"))

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        withdrawn_by=distinct_actor,
    )

    assert events[0].withdrawn_by == distinct_actor
