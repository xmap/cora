"""Unit tests for the `deprecate_clearance_template` slice's pure decider.

Pins the `Active -> Deprecated` strict-not-idempotent transition: only an
Active state deprecates; missing state raises
`ClearanceTemplateNotFoundError`; any other status raises
`ClearanceTemplateCannotDeprecateError` carrying the current status. The
decider is a pure function over `(state, command, now, deprecated_by)` and
threads the deprecator's ActorId onto the emitted event.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotDeprecateError,
    ClearanceTemplateCode,
    ClearanceTemplateDeprecated,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.features.deprecate_clearance_template import (
    DeprecateClearanceTemplate,
    decide,
)
from cora.shared.deprecation import DeprecationReason
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_DEFINED_AT = datetime(2026, 6, 9, 9, 0, 0, tzinfo=UTC)
_DEFINER_ID = ActorId(UUID("00000000-0000-0000-0000-000000000011"))
_DEPRECATOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))


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
def test_decide_emits_deprecated_event_on_happy_path() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.ACTIVE)
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        deprecated_by=_DEPRECATOR_ID,
    )

    assert events == [
        ClearanceTemplateDeprecated(
            reason="Superseded",
            template_id=template_id,
            occurred_at=_NOW,
            deprecated_by=_DEPRECATOR_ID,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    template_id = uuid4()
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            deprecated_by=_DEPRECATOR_ID,
        )
    assert exc_info.value.template_id == template_id


@pytest.mark.unit
def test_decide_rejects_when_status_is_draft() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DRAFT)
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateCannotDeprecateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            deprecated_by=_DEPRECATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.DRAFT


@pytest.mark.unit
def test_decide_rejects_when_status_is_deprecated() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.DEPRECATED)
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateCannotDeprecateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            deprecated_by=_DEPRECATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.DEPRECATED


@pytest.mark.unit
def test_decide_rejects_when_status_is_withdrawn() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.WITHDRAWN)
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )

    with pytest.raises(ClearanceTemplateCannotDeprecateError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            deprecated_by=_DEPRECATOR_ID,
        )
    assert exc_info.value.template_id == template_id
    assert exc_info.value.current_status == ClearanceTemplateStatus.WITHDRAWN


@pytest.mark.unit
def test_decide_threads_deprecated_by_onto_event() -> None:
    template_id = uuid4()
    state = _template(template_id=template_id, status=ClearanceTemplateStatus.ACTIVE)
    command = DeprecateClearanceTemplate(
        reason=DeprecationReason.SUPERSEDED, template_id=template_id
    )
    distinct_actor = ActorId(UUID("00000000-0000-0000-0000-0000000000aa"))

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        deprecated_by=distinct_actor,
    )

    assert events[0].deprecated_by == distinct_actor
