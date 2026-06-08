"""Unit tests for the `complete_seal_republishing` slice's pure decider.

Pin the FSM single-source guard (Republishing is the only legal
source), the not-found branch, the optional head-pointer pairing
invariant, the sequence-number monotonicity invariant when the head
pointer is supplied, the no-prior-head guard when omitted, purity,
and the handler-injected `completed_by` / `now` capture per
the non-determinism principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import (
    InvalidSealHeadHashError,
    Seal,
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealRepublishingCompleted,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features import complete_seal_republishing
from cora.federation.features.complete_seal_republishing import (
    CompleteSealRepublishing,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fec001"))
_OTHER_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000fec002"))
_INITIALIZED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fec099"))
_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_FACILITY_ID = "aps-2bm"
_PRIOR_HEAD_HASH = "a" * 64
_NEW_HEAD_HASH = "b" * 64


def _seal(
    status: SealStatus,
    *,
    current_head_hash: str | None = _PRIOR_HEAD_HASH,
    current_sequence_number: int = 5,
) -> Seal:
    return Seal(
        facility_id=_FACILITY_ID,
        online_credential_id=_ONLINE_KEY,
        offline_credential_id=_OFFLINE_KEY,
        current_head_hash=current_head_hash,
        current_sequence_number=current_sequence_number,
        initialized_by=_INITIALIZED_BY,
        initialized_at=_NOW,
        status=status,
    )


def _command(
    *,
    new_head_hash: str | None = _NEW_HEAD_HASH,
    new_sequence_number: int | None = 6,
) -> CompleteSealRepublishing:
    return CompleteSealRepublishing(
        facility_id=_FACILITY_ID,
        new_head_hash=new_head_hash,
        new_sequence_number=new_sequence_number,
    )


@pytest.mark.unit
def test_complete_seal_republishing_emits_event_when_state_is_republishing() -> None:
    state = _seal(SealStatus.REPUBLISHING)
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=_PRINCIPAL_ID,
    )
    assert events == [
        SealRepublishingCompleted(
            facility_id=_FACILITY_ID,
            new_head_hash=_NEW_HEAD_HASH,
            new_sequence_number=6,
            completed_by=_PRINCIPAL_ID,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_complete_seal_republishing_raises_not_found_when_state_is_none() -> None:
    with pytest.raises(SealNotFoundError):
        complete_seal_republishing.decide(
            state=None,
            command=_command(),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )


@pytest.mark.unit
def test_complete_seal_republishing_raises_cannot_complete_when_live() -> None:
    """Single-source: completing a republish on a Live Seal rejects."""
    state = _seal(SealStatus.LIVE)
    with pytest.raises(SealCannotCompleteRepublishingError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.current_status is SealStatus.LIVE


@pytest.mark.unit
def test_complete_seal_republishing_reuses_prior_head_when_pair_omitted() -> None:
    """Republish-only-shape: omitting both pair fields keeps prior head/seq."""
    state = _seal(SealStatus.REPUBLISHING)
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(new_head_hash=None, new_sequence_number=None),
        now=_NOW,
        completed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].new_head_hash == _PRIOR_HEAD_HASH
    assert events[0].new_sequence_number == 5


@pytest.mark.unit
def test_complete_seal_republishing_rejects_head_without_sequence() -> None:
    """Pairing invariant: head supplied alone -> InvalidSealHeadHashError."""
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(InvalidSealHeadHashError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(new_head_hash=_NEW_HEAD_HASH, new_sequence_number=None),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert "together or omitted together" in exc.value.reason


@pytest.mark.unit
def test_complete_seal_republishing_rejects_sequence_without_head() -> None:
    """Pairing invariant: sequence supplied alone -> InvalidSealHeadHashError."""
    state = _seal(SealStatus.REPUBLISHING)
    with pytest.raises(InvalidSealHeadHashError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(new_head_hash=None, new_sequence_number=6),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert "together or omitted together" in exc.value.reason


@pytest.mark.unit
def test_complete_seal_republishing_raises_sequence_regression_on_equal_sequence() -> None:
    """Monotonicity: new sequence must be strictly greater than prior."""
    state = _seal(SealStatus.REPUBLISHING, current_sequence_number=6)
    with pytest.raises(SealSequenceNumberRegressionError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(new_head_hash=_NEW_HEAD_HASH, new_sequence_number=6),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.prior_sequence_number == 6
    assert exc.value.proposed_sequence_number == 6


@pytest.mark.unit
def test_complete_seal_republishing_raises_sequence_regression_on_lower_sequence() -> None:
    """Monotonicity: a lower proposed sequence number is rejected."""
    state = _seal(SealStatus.REPUBLISHING, current_sequence_number=10)
    with pytest.raises(SealSequenceNumberRegressionError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(new_head_hash=_NEW_HEAD_HASH, new_sequence_number=4),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert exc.value.prior_sequence_number == 10
    assert exc.value.proposed_sequence_number == 4


@pytest.mark.unit
def test_complete_seal_republishing_rejects_omission_when_prior_head_is_none() -> None:
    """Omitting head requires a prior signing to have established a head."""
    state = _seal(SealStatus.REPUBLISHING, current_head_hash=None, current_sequence_number=0)
    with pytest.raises(InvalidSealHeadHashError) as exc:
        complete_seal_republishing.decide(
            state=state,
            command=_command(new_head_hash=None, new_sequence_number=None),
            now=_NOW,
            completed_by=_PRINCIPAL_ID,
        )
    assert "current_head_hash is None" in exc.value.reason


@pytest.mark.unit
def test_complete_seal_republishing_is_pure_same_inputs_same_outputs() -> None:
    state = _seal(SealStatus.REPUBLISHING)
    first = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=_PRINCIPAL_ID,
    )
    second = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_complete_seal_republishing_uses_handler_injected_actor_id_verbatim() -> None:
    """The decider records the handler-injected actor id without synthesising."""
    state = _seal(SealStatus.REPUBLISHING)
    injected = uuid4()
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=ActorId(injected),
    )
    assert events[0].completed_by == injected


@pytest.mark.unit
def test_complete_seal_republishing_uses_handler_injected_now_verbatim() -> None:
    """`now` is injected from the handler's clock; decider records it verbatim."""
    state = _seal(SealStatus.REPUBLISHING)
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=custom_now,
        completed_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now


@pytest.mark.unit
def test_complete_seal_republishing_actor_id_independent_of_initialized_by() -> None:
    """The completing actor need NOT be the Seal's genesis-initializing actor."""
    state = _seal(SealStatus.REPUBLISHING)
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=_OTHER_ACTOR_ID,
    )
    assert events[0].completed_by == _OTHER_ACTOR_ID
    assert state.initialized_by == _INITIALIZED_BY


@pytest.mark.unit
def test_complete_seal_republishing_reuses_facility_id_from_state() -> None:
    """Transitions reuse the aggregate identity from state; only genesis mints."""
    state = _seal(SealStatus.REPUBLISHING)
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=_NOW,
        completed_by=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == state.facility_id
