"""Property-based tests for `activate_permit.decide` (Federation BC).

Complements the example-based `test_activate_permit_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, *, now, activated_by) -> list[PermitActivated]

Load-bearing properties:

  - state=None always raises `PermitNotFoundError` carrying
    command.permit_id (existence/genesis guard).
  - The source-state partition is total over `PermitStatus`: only
    `Defined` emits exactly one `PermitActivated` (permit_id=state.id,
    activated_by=injected, occurred_at=now); every other status raises
    `PermitCannotActivateError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's permit_id is `state.id`, never command.permit_id;
    `activated_by` is the handler-injected principal threaded verbatim.
  - Pure: same (state, command, now, activated_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    Permit,
    PermitActivated,
    PermitCannotActivateError,
    PermitNotFoundError,
    PermitStatus,
    ReadScope,
    ScopeRef,
)
from cora.federation.features import activate_permit
from cora.federation.features.activate_permit import ActivatePermit
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PEER_FACILITY_CODE = FacilityCode("aps-2bm")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_DEFINED_BY_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed003"))

_ACTIVATABLE_SOURCES = (PermitStatus.DEFINED,)
_DISALLOWED_SOURCES = tuple(s for s in PermitStatus if s not in frozenset(_ACTIVATABLE_SOURCES))


def _terms() -> OutboundTerms:
    return OutboundTerms(
        scopes=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


def _permit(*, permit_id: UUID, status: PermitStatus, defined_at: datetime) -> Permit:
    return Permit(
        id=permit_id,
        peer_facility_code=_PEER_FACILITY_CODE,
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=defined_at,
        defined_by=_DEFINED_BY_ACTOR_ID,
        defined_at=defined_at,
        status=status,
        terms=_terms(),
    )


@pytest.mark.unit
@given(permit_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_with_none_state_always_raises_not_found(
    permit_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PermitNotFoundError` carrying command.permit_id."""
    with pytest.raises(PermitNotFoundError) as exc:
        activate_permit.decide(
            state=None,
            command=ActivatePermit(permit_id=permit_id),
            now=now,
            activated_by=activated_by,
        )
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(permit_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_from_defined_emits_single_event(
    permit_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Defined is the only activatable source; emits one PermitActivated."""
    events = activate_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.DEFINED, defined_at=now),
        command=ActivatePermit(permit_id=permit_id),
        now=now,
        activated_by=activated_by,
    )
    assert events == [
        PermitActivated(permit_id=permit_id, activated_by=activated_by, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    activated_by=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_activate_from_disallowed_source_always_raises_cannot_activate(
    permit_id: UUID,
    activated_by: UUID,
    source: PermitStatus,
    now: datetime,
) -> None:
    """Any source other than Defined raises, carrying the current status and id."""
    with pytest.raises(PermitCannotActivateError) as exc:
        activate_permit.decide(
            state=_permit(permit_id=permit_id, status=source, defined_at=now),
            command=ActivatePermit(permit_id=permit_id),
            now=now,
            activated_by=activated_by,
        )
    assert exc.value.current_status is source
    assert exc.value.permit_id == permit_id


@pytest.mark.unit
@given(
    state_permit_id=st.uuids(),
    command_permit_id=st.uuids(),
    activated_by=st.uuids(),
    now=aware_datetimes(),
)
def test_activate_uses_state_id_not_command_permit_id(
    state_permit_id: UUID,
    command_permit_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """The emitted event's permit_id is state.id, not command.permit_id."""
    assume(state_permit_id != command_permit_id)
    events = activate_permit.decide(
        state=_permit(permit_id=state_permit_id, status=PermitStatus.DEFINED, defined_at=now),
        command=ActivatePermit(permit_id=command_permit_id),
        now=now,
        activated_by=activated_by,
    )
    assert events[0].permit_id == state_permit_id


@pytest.mark.unit
@given(permit_id=st.uuids(), activated_by=st.uuids(), now=aware_datetimes())
def test_activate_threads_injected_principal_verbatim(
    permit_id: UUID,
    activated_by: UUID,
    now: datetime,
) -> None:
    """Handler-injected `activated_by` is denormed onto the event unchanged."""
    events = activate_permit.decide(
        state=_permit(permit_id=permit_id, status=PermitStatus.DEFINED, defined_at=now),
        command=ActivatePermit(permit_id=permit_id),
        now=now,
        activated_by=activated_by,
    )
    assert events[0].activated_by == activated_by


@pytest.mark.unit
@given(
    permit_id=st.uuids(),
    activated_by=st.uuids(),
    now=aware_datetimes(),
    label=printable_ascii_text(max_size=16),
)
def test_activate_is_pure_same_input_same_output(
    permit_id: UUID,
    activated_by: UUID,
    now: datetime,
    label: str,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    _ = label
    state = _permit(permit_id=permit_id, status=PermitStatus.DEFINED, defined_at=now)
    command = ActivatePermit(permit_id=permit_id)
    first = activate_permit.decide(state=state, command=command, now=now, activated_by=activated_by)
    second = activate_permit.decide(
        state=state, command=command, now=now, activated_by=activated_by
    )
    assert first == second
