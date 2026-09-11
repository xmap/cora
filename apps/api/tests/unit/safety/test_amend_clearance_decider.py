"""Pure-decider tests for `amend_clearance` slice.

Pins the cross-aggregate two-stream output shape:
  - parent_events == [ClearanceSuperseded(parent.id, by_clearance_id=new_id)]
  - child_events == [ClearanceRegistered(clearance_id=new_id,
                                         parent_id=parent.id, ...)]
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
    ClearanceTemplateStatusValue,
)
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceBinding,
    ClearanceCannotAmendError,
    ClearanceRegistered,
    ClearanceStatus,
    ClearanceSuperseded,
    ClearanceTitle,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    ClearanceTemplateNotBindableError,
    ClearanceTemplateNotFoundError,
    clearance_template_stream_id,
)
from cora.safety.features import amend_clearance
from cora.safety.features.amend_clearance import (
    AmendClearance,
    ClearanceAmendmentContext,
)
from cora.shared.facility_code import FacilityCode

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _lookup_result(code: str = "aps") -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


def _template_lookup_result(
    template_id: UUID,
    facility_code: str = "aps",
    code: str = "ESAF",
    *,
    status: ClearanceTemplateStatusValue = "Active",
    version: int = 1,
) -> ClearanceTemplateLookupResult:
    return ClearanceTemplateLookupResult(
        id=template_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )


_TEMPLATE_ID = clearance_template_stream_id("aps", "ESAF")


def _parent(status: ClearanceStatus = ClearanceStatus.ACTIVE) -> Clearance:
    return Clearance(
        id=uuid4(),
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Original"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


def _command(
    parent_id: UUID,
    *,
    title: str = "Amended",
    bindings: frozenset[ClearanceBinding] | None = None,
) -> AmendClearance:
    return AmendClearance(
        parent_id=parent_id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code="aps",
        title=title,
        bindings=bindings if bindings is not None else frozenset({RunBinding(run_id=uuid4())}),
    )


@pytest.mark.unit
def test_decide_emits_parent_superseded_and_child_registered() -> None:
    parent = _parent()
    new_id = uuid4()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=3)
    cmd = _command(parent.id, title="Amended pilot")

    result = amend_clearance.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
    )

    assert len(result.parent_events) == 1
    assert isinstance(result.parent_events[0], ClearanceSuperseded)
    assert result.parent_events[0].clearance_id == parent.id
    assert result.parent_events[0].by_clearance_id == new_id
    assert result.parent_events[0].occurred_at == _NOW

    assert len(result.child_events) == 1
    assert isinstance(result.child_events[0], ClearanceRegistered)
    assert result.child_events[0].clearance_id == new_id
    assert result.child_events[0].parent_id == parent.id
    assert result.child_events[0].title == "Amended pilot"
    assert result.child_events[0].template_id == _TEMPLATE_ID
    assert result.child_events[0].template_code == "ESAF"


@pytest.mark.unit
def test_decide_child_carries_validity_window_when_provided() -> None:
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    valid_until = datetime(2026, 9, 1, tzinfo=UTC)
    cmd = AmendClearance(
        parent_id=parent.id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code="aps",
        title="Amended",
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        valid_from=valid_from,
        valid_until=valid_until,
    )
    result = amend_clearance.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
    )
    assert result.child_events[0].valid_from == valid_from
    assert result.child_events[0].valid_until == valid_until


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ClearanceStatus.DEFINED,
        ClearanceStatus.SUBMITTED,
        ClearanceStatus.UNDER_REVIEW,
        ClearanceStatus.APPROVED,
        ClearanceStatus.EXPIRED,
        ClearanceStatus.REJECTED,
        ClearanceStatus.SUPERSEDED,
    ],
)
def test_decide_rejects_when_parent_not_active(status: ClearanceStatus) -> None:
    parent = _parent(status)
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = _command(parent.id)
    with pytest.raises(ClearanceCannotAmendError):
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_unknown_template_id() -> None:
    """When the handler's ClearanceTemplateLookup miss surfaces as
    template_lookup_result=None, the amend decider raises
    ClearanceTemplateNotFoundError carrying the command's template_id.
    Mirrors the register_clearance decider precedent."""
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = _command(parent.id)
    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=None,
        )
    assert exc_info.value.template_id == _TEMPLATE_ID


@pytest.mark.unit
def test_decide_rejects_non_active_template() -> None:
    """A template exists but is not Active (Draft / Deprecated /
    Withdrawn): the amend decider raises ClearanceTemplateNotBindableError
    so operators can only bind amendments to live templates. Mirrors the
    register_clearance decider precedent."""
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = _command(parent.id)
    with pytest.raises(ClearanceTemplateNotBindableError) as exc_info:
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(
                _TEMPLATE_ID, "aps", "ESAF", status="Deprecated"
            ),
        )
    assert exc_info.value.template_id == _TEMPLATE_ID


@pytest.mark.unit
def test_decide_rejects_empty_child_title() -> None:
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, title="   ")
    with pytest.raises(InvalidClearanceTitleError):
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_empty_child_bindings() -> None:
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, bindings=frozenset())
    with pytest.raises(InvalidClearanceBindingsError):
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_inverted_child_validity_window() -> None:
    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    cmd = AmendClearance(
        parent_id=parent.id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code="aps",
        title="Amended",
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        valid_from=datetime(2026, 9, 1, tzinfo=UTC),
        valid_until=datetime(2026, 6, 1, tzinfo=UTC),
    )
    with pytest.raises(InvalidClearanceValidityWindowError):
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_child_declaration_target_outside_bindings() -> None:
    """Subset semantic: a declaration's target binding MUST be in child's
    bindings (same invariant as register_clearance)."""
    from cora.safety.aggregates.clearance import HazardDeclaration

    parent = _parent()
    ctx = ClearanceAmendmentContext(parent=parent, parent_version=1)
    in_scope = SubjectBinding(subject_id=uuid4())
    out_of_scope = SubjectBinding(subject_id=uuid4())
    cmd = AmendClearance(
        parent_id=parent.id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code="aps",
        title="Amended",
        bindings=frozenset({in_scope}),
        declarations=frozenset({HazardDeclaration(target=out_of_scope)}),
    )
    with pytest.raises(InvalidClearanceDeclarationTargetError):
        amend_clearance.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )
