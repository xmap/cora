"""Property-based tests for `withdraw_clearance_template.decide`.

Pins the terminal transition (`Draft | Active | Deprecated -> Withdrawn`)
decider invariants with Hypothesis:

  - Happy path (state in {Draft, Active, Deprecated}): exactly one
    `ClearanceTemplateWithdrawn` event is emitted, keyed by `state.id`,
    carrying the injected `withdrawn_by` actor and `occurred_at == now`.
  - Already-Withdrawn status ALWAYS raises
    `ClearanceTemplateCannotWithdrawError` regardless of payload.
  - A None state ALWAYS raises `ClearanceTemplateNotFoundError`.

Also pins (architecture) that the decider module exposes a `decide`
callable at the canonical slice path.
"""

from datetime import datetime
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotWithdrawError,
    ClearanceTemplateCode,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.features.withdraw_clearance_template import decider as decider_module
from cora.safety.features.withdraw_clearance_template.command import (
    WithdrawClearanceTemplate,
)
from cora.safety.features.withdraw_clearance_template.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_DEFINED_BY = ActorId(UUID("00000000-0000-0000-0000-000000000099"))
_DEFINED_AT = datetime.fromisoformat("2026-01-01T00:00:00+00:00")

_FACILITY_CODES = st.sampled_from(["aps", "maxiv", "esrf", "diamond"])

_WITHDRAWABLE_STATUSES = st.sampled_from(
    [
        ClearanceTemplateStatus.DRAFT,
        ClearanceTemplateStatus.ACTIVE,
        ClearanceTemplateStatus.DEPRECATED,
    ]
)


def _template(
    template_id: UUID,
    facility_code: str,
    status: ClearanceTemplateStatus,
    version: int,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode(facility_code),
        code=ClearanceTemplateCode("preexisting"),
        title=ClearanceTemplateTitle("Preexisting Template"),
        defined_at=_DEFINED_AT,
        defined_by=_TEST_DEFINED_BY,
        status=status,
        version=ClearanceTemplateVersion(version),
    )


@pytest.mark.architecture
@pytest.mark.unit
def test_decider_module_exposes_decide_callable() -> None:
    """The `decide` symbol must live at the canonical slice path."""
    assert callable(decider_module.decide)


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    template_id=st.uuids(),
    facility_code=_FACILITY_CODES,
    version=st.integers(min_value=1, max_value=50),
    status=_WITHDRAWABLE_STATUSES,
    now=aware_datetimes(),
    withdrawn_by=st.uuids(),
)
def test_decide_emits_single_withdrawn_event_on_non_terminal_state(
    template_id: UUID,
    facility_code: str,
    version: int,
    status: ClearanceTemplateStatus,
    now: datetime,
    withdrawn_by: UUID,
) -> None:
    """Happy path: any non-terminal status yields exactly one Withdrawn event keyed by state.id."""
    state = _template(
        template_id=template_id,
        facility_code=facility_code,
        status=status,
        version=version,
    )
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)
    actor = ActorId(withdrawn_by)

    events = decide(
        state=state,
        command=command,
        now=now,
        withdrawn_by=actor,
    )

    assert len(events) == 1
    event = events[0]
    assert event.template_id == state.id
    assert event.withdrawn_by == actor
    assert event.occurred_at == now


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    template_id=st.uuids(),
    facility_code=_FACILITY_CODES,
    version=st.integers(min_value=1, max_value=50),
    now=aware_datetimes(),
    withdrawn_by=st.uuids(),
)
def test_decide_rejects_already_withdrawn_status(
    template_id: UUID,
    facility_code: str,
    version: int,
    now: datetime,
    withdrawn_by: UUID,
) -> None:
    """Already-Withdrawn status raises CannotWithdraw, strict-not-idempotent."""
    state = _template(
        template_id=template_id,
        facility_code=facility_code,
        status=ClearanceTemplateStatus.WITHDRAWN,
        version=version,
    )
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    with pytest.raises(ClearanceTemplateCannotWithdrawError):
        decide(
            state=state,
            command=command,
            now=now,
            withdrawn_by=ActorId(withdrawn_by),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    template_id=st.uuids(),
    now=aware_datetimes(),
    withdrawn_by=st.uuids(),
)
def test_decide_rejects_when_state_is_none(
    template_id: UUID,
    now: datetime,
    withdrawn_by: UUID,
) -> None:
    """A None state ALWAYS raises NotFound."""
    command = WithdrawClearanceTemplate(reason="policy change", template_id=template_id)

    with pytest.raises(ClearanceTemplateNotFoundError):
        decide(
            state=None,
            command=command,
            now=now,
            withdrawn_by=ActorId(withdrawn_by),
        )
