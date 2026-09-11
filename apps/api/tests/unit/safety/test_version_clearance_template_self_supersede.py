"""Unit tests for the self-supersede invariant on `version_clearance_template`.

Pins the decider-side rejection when `supersedes_template_id` equals the
child's own `template_id`. A self-loop in the supersedes lineage is
non-sensical (a template cannot version itself) and would corrupt the
parent-chain projection downstream. The decider raises
`ClearanceTemplateCannotVersionError` carrying the offending template id
and its current status.

The happy-path companion test guards against an over-broad guard that
would also reject distinct-parent versioning.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
    ClearanceTemplateStatusValue,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateCode,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    ClearanceTemplateVersioned,
)
from cora.safety.features.version_clearance_template.command import (
    VersionClearanceTemplate,
)
from cora.safety.features.version_clearance_template.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))
_CHILD_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce201")
_DISTINCT_PARENT_TEMPLATE_ID = UUID("01900000-0000-7000-8000-0000000ce200")


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
def test_version_decider_rejects_supersede_self_loop_with_cannot_version_error() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_CHILD_TEMPLATE_ID,
    )
    parent = _lookup_result(_CHILD_TEMPLATE_ID, facility_code="aps", version=1)

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
def test_version_decider_accepts_distinct_parent_with_same_invariants_otherwise() -> None:
    state = _template(_CHILD_TEMPLATE_ID, version=1)
    command = VersionClearanceTemplate(
        template_id=_CHILD_TEMPLATE_ID,
        new_version=2,
        supersedes_template_id=_DISTINCT_PARENT_TEMPLATE_ID,
    )
    parent = _lookup_result(_DISTINCT_PARENT_TEMPLATE_ID, facility_code="aps", version=1)

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
            supersedes_template_id=_DISTINCT_PARENT_TEMPLATE_ID,
            occurred_at=_NOW,
            versioned_by=_TEST_ACTOR_ID,
        )
    ]
