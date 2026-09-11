"""Unit tests for the `version_clearance_template` slice's pure decider.

Pins the Active-only invariant (L4), the same-facility parent-chain
handshake (L5; handler-loads + decider-rejects mirror of
`define_clearance_template`'s Facility binding), and the monotonic
`new_version == state.version + 1` rule. The decider is a pure
function over `(state, command, now, versioned_by, parent_lookup_result)`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
    ClearanceTemplateStatusValue,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateCode,
    ClearanceTemplateFacilityMismatchError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    ClearanceTemplateVersioned,
)
from cora.safety.features.version_clearance_template import (
    VersionClearanceTemplate,
    decide,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))
_CHILD_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce201")
_PARENT_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce200")


def _lookup_result(
    template_id: UUID,
    facility_code: str,
    version: int,
    status: ClearanceTemplateStatusValue = "Active",
    code: str = "esaf",
) -> ClearanceTemplateLookupResult:
    return ClearanceTemplateLookupResult(
        id=template_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )


def _template(
    template_id: UUID,
    *,
    facility_code: str = "aps",
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.ACTIVE,
    version: int = 1,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode(facility_code),
        code=ClearanceTemplateCode("esaf"),
        title=ClearanceTemplateTitle("ESAF Form"),
        defined_at=_NOW,
        defined_by=_TEST_ACTOR_ID,
        status=status,
        version=ClearanceTemplateVersion(version),
    )


@pytest.mark.unit
def test_decide_emits_versioned_event_on_happy_path() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        versioned_by=_TEST_ACTOR_ID,
        parent_lookup_result=parent,
    )

    assert events == [
        ClearanceTemplateVersioned(
            template_id=_CHILD_TEMPLATE_ID,
            new_version=2,
            supersedes_template_id=_PARENT_TEMPLATE_ID,
            occurred_at=_NOW,
            versioned_by=_TEST_ACTOR_ID,
        )
    ]


@pytest.mark.unit
def test_decide_rejects_when_template_state_is_none() -> None:
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID


@pytest.mark.unit
def test_decide_rejects_when_status_is_draft() -> None:
    state = _template(_CHILD_TEMPLATE_ID, status=ClearanceTemplateStatus.DRAFT, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.current_status == ClearanceTemplateStatus.DRAFT


@pytest.mark.unit
def test_decide_rejects_when_status_is_deprecated() -> None:
    state = _template(_CHILD_TEMPLATE_ID, status=ClearanceTemplateStatus.DEPRECATED, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.current_status == ClearanceTemplateStatus.DEPRECATED


@pytest.mark.unit
def test_decide_rejects_when_status_is_withdrawn() -> None:
    state = _template(_CHILD_TEMPLATE_ID, status=ClearanceTemplateStatus.WITHDRAWN, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.current_status == ClearanceTemplateStatus.WITHDRAWN


@pytest.mark.unit
def test_decide_rejects_when_parent_lookup_result_is_none() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )

    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=None,
        )
    assert exc_info.value.template_id == _PARENT_TEMPLATE_ID


@pytest.mark.unit
def test_decide_rejects_when_parent_facility_does_not_match() -> None:
    state = _template(_CHILD_TEMPLATE_ID, facility_code="aps", version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="maxiv", version=1)

    with pytest.raises(ClearanceTemplateFacilityMismatchError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.template_facility_code == FacilityCode("aps")
    assert exc_info.value.parent_facility_code == FacilityCode("maxiv")


@pytest.mark.unit
def test_decide_rejects_non_monotonic_new_version() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=3,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            versioned_by=_TEST_ACTOR_ID,
            parent_lookup_result=parent,
        )
    assert exc_info.value.template_id == _CHILD_TEMPLATE_ID
    assert exc_info.value.current_status == ClearanceTemplateStatus.ACTIVE


@pytest.mark.unit
def test_decide_threads_versioned_by_onto_event() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_PARENT_TEMPLATE_ID, facility_code="aps", version=1)
    other_actor = ActorId(uuid4())

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        versioned_by=other_actor,
        parent_lookup_result=parent,
    )

    assert events[0].versioned_by == other_actor
