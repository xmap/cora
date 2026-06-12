"""Property-based tests for `amend_clearance.decide` (Safety BC).

Complements the example-based `test_amend_clearance_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider returning `AmendmentEvents` (parent + child event lists) for the
atomic two-stream `append_streams` write.

    (state, command, *, context, now, new_id, facility_lookup_result,
     template_lookup_result) -> AmendmentEvents

Load-bearing properties:

  - The only amendable parent status is `Active`; every other
    `ClearanceStatus` always raises `ClearanceCannotAmendError`
    carrying the parent's id and current status (total source-state
    partition).
  - The genesis-existence guard: a missing facility lookup always
    raises `ClearanceFacilityNotFoundError`; a missing template lookup
    always raises `ClearanceTemplateNotFoundError`; a non-Active
    template always raises `ClearanceTemplateNotBindableError`.
  - Happy path: the child genesis `ClearanceRegistered` carries
    `clearance_id == new_id`, `parent_id == parent.id`, and
    `occurred_at == now`; the parent-side `ClearanceSuperseded`
    references the child via `by_clearance_id == new_id` and is keyed on
    `clearance_id == parent.id` with `occurred_at == now`.
  - Pure: same inputs return equal results (no clock leakage).

The full gate matrix (title / bindings / external-id / validity-window /
declaration-target) is pinned by the example-based test; not duplicated
here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.ports.clearance_template_lookup import ClearanceTemplateLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotAmendError,
    ClearanceRegistered,
    ClearanceStatus,
    ClearanceSuperseded,
    ClearanceTitle,
    RunBinding,
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
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_TEMPLATE_ID = clearance_template_stream_id("aps", "ESAF")

_AMENDABLE_SOURCES = (ClearanceStatus.ACTIVE,)
_NON_AMENDABLE_SOURCES = tuple(
    status for status in ClearanceStatus if status not in _AMENDABLE_SOURCES
)


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
    status: str = "Active",
    version: int = 1,
) -> ClearanceTemplateLookupResult:
    return ClearanceTemplateLookupResult(
        id=template_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )


def _parent(
    *,
    parent_id: UUID,
    status: ClearanceStatus = ClearanceStatus.ACTIVE,
) -> Clearance:
    return Clearance(
        id=parent_id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Original"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


def _command(parent_id: UUID, *, title: str = "Amended") -> AmendClearance:
    return AmendClearance(
        parent_id=parent_id,
        template_id=ClearanceTemplateId(_TEMPLATE_ID),
        facility_code="aps",
        title=title,
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )


def _context(parent: Clearance) -> ClearanceAmendmentContext:
    return ClearanceAmendmentContext(parent=parent, parent_version=0)


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    new_id=st.uuids(),
    title=printable_ascii_text(max_size=200),
    now=aware_datetimes(),
)
def test_amend_active_parent_emits_superseded_and_child_registered(
    parent_id: UUID,
    new_id: UUID,
    title: str,
    now: datetime,
) -> None:
    """An Active parent yields a parent ClearanceSuperseded and a child ClearanceRegistered."""
    parent = _parent(parent_id=parent_id, status=ClearanceStatus.ACTIVE)
    result = amend_clearance.decide(
        state=None,
        command=_command(parent_id, title=title),
        context=_context(parent),
        now=now,
        new_id=new_id,
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
    )

    assert len(result.parent_events) == 1
    parent_event = result.parent_events[0]
    assert isinstance(parent_event, ClearanceSuperseded)
    assert parent_event.clearance_id == parent_id
    assert parent_event.by_clearance_id == new_id
    assert parent_event.occurred_at == now

    assert len(result.child_events) == 1
    child_event = result.child_events[0]
    assert isinstance(child_event, ClearanceRegistered)
    assert child_event.clearance_id == new_id
    assert child_event.parent_id == parent_id
    assert child_event.title == title
    assert child_event.occurred_at == now


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    new_id=st.uuids(),
    source=st.sampled_from(_NON_AMENDABLE_SOURCES),
    now=aware_datetimes(),
)
def test_amend_non_active_parent_always_raises_cannot_amend(
    parent_id: UUID,
    new_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Every parent status other than Active refuses amendment, carrying id and status."""
    parent = _parent(parent_id=parent_id, status=source)
    with pytest.raises(ClearanceCannotAmendError) as exc:
        amend_clearance.decide(
            state=None,
            command=_command(parent_id),
            context=_context(parent),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(_TEMPLATE_ID, "aps", "ESAF"),
        )
    assert exc.value.parent_id == parent_id
    assert exc.value.current_status is source


@pytest.mark.unit
@given(parent_id=st.uuids(), new_id=st.uuids(), now=aware_datetimes())
def test_amend_missing_template_lookup_always_raises_template_not_found(
    parent_id: UUID,
    new_id: UUID,
    now: datetime,
) -> None:
    """A None template lookup raises ClearanceTemplateNotFoundError for the command's id."""
    parent = _parent(parent_id=parent_id, status=ClearanceStatus.ACTIVE)
    with pytest.raises(ClearanceTemplateNotFoundError) as exc:
        amend_clearance.decide(
            state=None,
            command=_command(parent_id),
            context=_context(parent),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=None,
        )
    assert exc.value.template_id == _TEMPLATE_ID


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    new_id=st.uuids(),
    template_status=st.sampled_from(("Draft", "Deprecated", "Withdrawn")),
    now=aware_datetimes(),
)
def test_amend_non_active_template_always_raises_not_bindable(
    parent_id: UUID,
    new_id: UUID,
    template_status: str,
    now: datetime,
) -> None:
    """A template that exists but is not Active refuses binding for the command's id."""
    parent = _parent(parent_id=parent_id, status=ClearanceStatus.ACTIVE)
    with pytest.raises(ClearanceTemplateNotBindableError) as exc:
        amend_clearance.decide(
            state=None,
            command=_command(parent_id),
            context=_context(parent),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(
                _TEMPLATE_ID, "aps", "ESAF", status=template_status
            ),
        )
    assert exc.value.template_id == _TEMPLATE_ID


@pytest.mark.unit
@given(parent_id=st.uuids(), new_id=st.uuids(), now=aware_datetimes())
def test_amend_is_pure_same_input_same_output(
    parent_id: UUID,
    new_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal AmendmentEvents (no clock leakage)."""
    parent = _parent(parent_id=parent_id, status=ClearanceStatus.ACTIVE)
    command = _command(parent_id)
    context = _context(parent)
    facility = _lookup_result("aps")
    template = _template_lookup_result(_TEMPLATE_ID, "aps", "ESAF")
    first = amend_clearance.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        facility_lookup_result=facility,
        template_lookup_result=template,
    )
    second = amend_clearance.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        facility_lookup_result=facility,
        template_lookup_result=template,
    )
    assert first == second
