"""Unit tests for the `start_seal_republishing` slice's pure decider.

Pin the FSM single-source guard (Live is the only legal source),
the not-found branch, purity (same inputs -> same outputs), the
handler-injected `started_by` / `now` capture per the
non-determinism principle (capture, don't recompute), and that
`reason` flows from the command through the decider onto the
emitted `SealRepublishingStarted` event payload.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealRepublishingStarted,
    SealStatus,
)
from cora.federation.features import start_seal_republishing
from cora.federation.features.start_seal_republishing import (
    StartSealRepublishing,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fec001"))
_INITIALIZED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0b1")


def _seal(status: SealStatus) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=_INITIALIZED_BY,
        initialized_at=_NOW,
        status=status,
    )


def _command(*, reason: str | None = "root rotation drill") -> StartSealRepublishing:
    return StartSealRepublishing(facility_id=_FACILITY_ID, reason=reason)


@pytest.mark.unit
def test_start_seal_republishing_emits_event_when_state_is_live() -> None:
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by=_PRINCIPAL_ID,
    )
    assert events == [
        SealRepublishingStarted(
            facility_id=_FACILITY_ID,
            started_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
            reason="root rotation drill",
        )
    ]


@pytest.mark.unit
def test_start_seal_republishing_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError):
        start_seal_republishing.decide(
            state=None,
            command=_command(),
            now=_NOW,
            started_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_start_seal_republishing_raises_cannot_start_when_already_republishing() -> None:
    """Single-source: starting against an already-Republishing Seal rejects."""
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(SealCannotStartRepublishingError) as exc:
        start_seal_republishing.decide(
            state=state,
            command=_command(),
            now=_NOW,
            started_by=_PRINCIPAL_ID,
        )
    assert exc.value.current_status is SealStatus.REPUBLISHING
    assert exc.value.facility_id == _FACILITY_ID


@pytest.mark.unit
def test_start_seal_republishing_defaults_reason_to_none_when_omitted() -> None:
    """Reason is optional on the command; absent reason still emits
    the event with reason None on the payload."""
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(reason=None),
        now=_NOW,
        started_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SealRepublishingStarted)
    assert event.facility_id == _FACILITY_ID
    assert event.reason is None


@pytest.mark.unit
def test_start_seal_republishing_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.LIVE)
    first = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by=_PRINCIPAL_ID,
    )
    second = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_start_seal_republishing_uses_handler_injected_actor_id_verbatim() -> None:
    state = _seal(SealStatus.LIVE)
    injected = uuid4()
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        started_by=ActorId(injected),
    )
    assert events[0].started_by == injected


@pytest.mark.unit
def test_start_seal_republishing_uses_handler_injected_now_verbatim() -> None:
    state = _seal(SealStatus.LIVE)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(),
        now=custom_now,
        started_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_start_seal_republishing_flows_reason_onto_event_payload() -> None:
    """`reason` is captured on the command and flows through to the
    emitted `SealRepublishingStarted` event so operator context
    survives on the immutable event log."""
    state = _seal(SealStatus.LIVE)
    events = start_seal_republishing.decide(
        state=state,
        command=_command(reason="key compromise drill"),
        now=_NOW,
        started_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SealRepublishingStarted)
    assert event.reason == "key compromise drill"
