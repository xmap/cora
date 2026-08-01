"""Property-based tests for `deprecate_clearance_template.decide`.

Pins the single-source transition (`Active -> Deprecated`) decider
invariants with Hypothesis:

  - Happy path (state is `Active`): exactly one
    `ClearanceTemplateDeprecated` event is emitted, keyed by
    `state.id`, carrying the injected `deprecated_by` actor and
    `occurred_at == now`.
  - Non-Active status (`Draft`, `Deprecated`, `Withdrawn`) ALWAYS
    raises `ClearanceTemplateCannotDeprecateError` regardless of
    payload.
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
    ClearanceTemplateCannotDeprecateError,
    ClearanceTemplateCode,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.features.deprecate_clearance_template import decider as decider_module
from cora.safety.features.deprecate_clearance_template.command import (
    DeprecateClearanceTemplate,
)
from cora.safety.features.deprecate_clearance_template.decider import decide
from cora.shared.deprecation import DeprecationReason
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_DEFINED_BY = ActorId(UUID("00000000-0000-0000-0000-000000000099"))
_DEFINED_AT = datetime.fromisoformat("2026-01-01T00:00:00+00:00")

_FACILITY_CODES = st.sampled_from(["aps", "maxiv", "esrf", "diamond"])

_NON_ACTIVE_STATUSES = st.sampled_from(
    [
        ClearanceTemplateStatus.DRAFT,
        ClearanceTemplateStatus.DEPRECATED,
        ClearanceTemplateStatus.WITHDRAWN,
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
    now=aware_datetimes(),
    deprecated_by=st.uuids(),
)
def test_decide_emits_single_deprecated_event_on_active_state(
    template_id: UUID,
    facility_code: str,
    version: int,
    now: datetime,
    deprecated_by: UUID,
) -> None:
    """Happy path: Active state yields exactly one Deprecated event keyed by state.id."""
    state = _template(
        template_id=template_id,
        facility_code=facility_code,
        status=ClearanceTemplateStatus.ACTIVE,
        version=version,
    )
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )
    actor = ActorId(deprecated_by)

    events = decide(
        state=state,
        command=command,
        now=now,
        deprecated_by=actor,
    )

    assert len(events) == 1
    event = events[0]
    assert event.template_id == state.id
    assert event.deprecated_by == actor
    assert event.occurred_at == now


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    template_id=st.uuids(),
    facility_code=_FACILITY_CODES,
    version=st.integers(min_value=1, max_value=50),
    status=_NON_ACTIVE_STATUSES,
    now=aware_datetimes(),
    deprecated_by=st.uuids(),
)
def test_decide_rejects_non_active_status(
    template_id: UUID,
    facility_code: str,
    version: int,
    status: ClearanceTemplateStatus,
    now: datetime,
    deprecated_by: UUID,
) -> None:
    """Any non-Active status raises CannotDeprecate, strict-not-idempotent."""
    state = _template(
        template_id=template_id,
        facility_code=facility_code,
        status=status,
        version=version,
    )
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateCannotDeprecateError):
        decide(
            state=state,
            command=command,
            now=now,
            deprecated_by=ActorId(deprecated_by),
        )


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    template_id=st.uuids(),
    now=aware_datetimes(),
    deprecated_by=st.uuids(),
)
def test_decide_rejects_when_state_is_none(
    template_id: UUID,
    now: datetime,
    deprecated_by: UUID,
) -> None:
    """A None state ALWAYS raises NotFound."""
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateNotFoundError):
        decide(
            state=None,
            command=command,
            now=now,
            deprecated_by=ActorId(deprecated_by),
        )
