"""Property-based tests for `register_clearance.decide` (Safety BC).

Complements the example-based `test_register_clearance_decider.py` with
universal claims across generated inputs. `register_clearance` is a gated
genesis returning a single `ClearanceRegistered`. The full gate matrix
(title / bindings / external_id / validity-window / declaration-target)
is pinned by the example tests; the PBT asserts the universal claims that
hold across the whole input space:

  - Any non-None state always raises `ClearanceAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of status,
    command, or lookup context.
  - A missing facility lookup (facility_lookup_result=None) always raises
    `ClearanceFacilityNotFoundError` carrying command.facility_code.
  - A missing template lookup (template_lookup_result=None) always raises
    `ClearanceTemplateNotFoundError` carrying command.template_id.
  - A non-Active resolved template always raises
    `ClearanceTemplateNotBindableError` carrying command.template_id.
  - On the happy path (state None, facility + Active template resolve)
    the single `ClearanceRegistered` carries the injected fields:
    clearance_id=new_id, template_id/template_code from the template
    lookup, facility_code from the facility lookup, title (trimmed),
    parent_id=None, occurred_at=now.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
)
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceAlreadyExistsError,
    ClearanceFacilityNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    ClearanceTemplateNotBindableError,
    ClearanceTemplateNotFoundError,
    clearance_template_stream_id,
)
from cora.safety.features import register_clearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.shared.facility_code import FacilityCode

if TYPE_CHECKING:
    from datetime import datetime

from tests._strategies import aware_datetimes, printable_ascii_text

_TITLE = printable_ascii_text(min_size=1, max_size=200)
_NON_ACTIVE_STATUSES = ("Draft", "Deprecated", "Withdrawn")


def _template_id(facility_code: str = "aps", code: str = "ESAF") -> ClearanceTemplateId:
    """Deterministic ClearanceTemplateId matching the auto-seed namespace."""
    return ClearanceTemplateId(clearance_template_stream_id(facility_code, code))


def _lookup_result(code: str = "aps") -> FacilityLookupResult:
    """Build a stub FacilityLookupResult for the given facility slug."""
    return FacilityLookupResult(
        id=UUID(int=1),
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
    """Build a stub ClearanceTemplateLookupResult for decider tests."""
    return ClearanceTemplateLookupResult(
        id=template_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )


def _state(*, state_id: UUID, status: ClearanceStatus) -> Clearance:
    """Build a non-None Clearance state for the existence-guard property."""
    return Clearance(
        id=state_id,
        template_id=_template_id("aps", "ESAF"),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("existing"),
        bindings=frozenset({RunBinding(run_id=UUID(int=2))}),
        status=status,
    )


def _command(*, title: str, facility_code: str = "aps", run_id: UUID) -> RegisterClearance:
    return RegisterClearance(
        template_id=_template_id("aps", "ESAF"),
        facility_code=facility_code,
        title=title,
        bindings=frozenset({RunBinding(run_id=run_id)}),
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(ClearanceStatus)),
    title=_TITLE,
    run_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: ClearanceStatus,
    title: str,
    run_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises ClearanceAlreadyExistsError carrying state.id."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceAlreadyExistsError) as exc:
        register_clearance.decide(
            state=_state(state_id=existing_id, status=existing_status),
            command=_command(title=title, run_id=run_id),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )
    assert exc.value.clearance_id == existing_id


@pytest.mark.unit
@given(title=_TITLE, run_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_register_without_facility_lookup_always_raises_facility_not_found(
    title: str,
    run_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """A missing facility lookup always raises ClearanceFacilityNotFoundError."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceFacilityNotFoundError) as exc:
        register_clearance.decide(
            state=None,
            command=_command(title=title, facility_code="aps", run_id=run_id),
            now=now,
            new_id=new_id,
            facility_lookup_result=None,
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )
    assert exc.value.facility_code == "aps"


@pytest.mark.unit
@given(title=_TITLE, run_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_register_without_template_lookup_always_raises_template_not_found(
    title: str,
    run_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """A missing template lookup always raises ClearanceTemplateNotFoundError."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceTemplateNotFoundError) as exc:
        register_clearance.decide(
            state=None,
            command=_command(title=title, run_id=run_id),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=None,
        )
    assert exc.value.template_id == tid


@pytest.mark.unit
@given(
    title=_TITLE,
    run_id=st.uuids(),
    template_status=st.sampled_from(_NON_ACTIVE_STATUSES),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_with_non_active_template_always_raises_not_bindable(
    title: str,
    run_id: UUID,
    template_status: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """A non-Active resolved template always raises ClearanceTemplateNotBindableError."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceTemplateNotBindableError) as exc:
        register_clearance.decide(
            state=None,
            command=_command(title=title, run_id=run_id),
            now=now,
            new_id=new_id,
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(
                tid, "aps", "ESAF", status=template_status
            ),
        )
    assert exc.value.template_id == tid


@pytest.mark.unit
@given(title=_TITLE, run_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_register_happy_path_emits_single_clearance_registered_with_injected_fields(
    title: str,
    run_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """The happy path emits one ClearanceRegistered with new_id + injected fields."""
    tid = _template_id("aps", "ESAF")
    template_lookup = _template_lookup_result(tid, "aps", "ESAF")
    events = register_clearance.decide(
        state=None,
        command=_command(title=title, run_id=run_id),
        now=now,
        new_id=new_id,
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=template_lookup,
    )
    assert len(events) == 1
    event = events[0]
    assert event.clearance_id == new_id
    assert event.template_id == template_lookup.id
    assert event.template_code == template_lookup.code
    assert event.facility_code == "aps"
    assert event.title == title.strip()
    assert event.parent_id is None
    assert event.occurred_at == now


@pytest.mark.unit
@given(title=_TITLE, run_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_register_is_pure_same_input_same_output(
    title: str,
    run_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    tid = _template_id("aps", "ESAF")
    command = _command(title=title, run_id=run_id)
    facility_lookup = _lookup_result("aps")
    template_lookup = _template_lookup_result(tid, "aps", "ESAF")
    first = register_clearance.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        facility_lookup_result=facility_lookup,
        template_lookup_result=template_lookup,
    )
    second = register_clearance.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        facility_lookup_result=facility_lookup,
        template_lookup_result=template_lookup,
    )
    assert first == second
