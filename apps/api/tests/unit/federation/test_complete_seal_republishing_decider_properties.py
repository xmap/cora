"""Property-based tests for `complete_seal_republishing.decide` (Federation BC).

Complements the example-based `test_complete_seal_republishing_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source crypto transition with actor attribution

    (state, command, now, completed_by) -> list[SealRepublishingCompleted]

A Seal is keyed by `facility_code` (a `FacilityCode` slug), not a UUID;
the threaded identity is the slug, not a minted id.

Load-bearing properties:

  - state=None always raises `SealNotFoundError` carrying
    command.facility_code (the bare slug).
  - The source-state partition is total over `SealStatus`: only
    `Republishing` emits exactly one `SealRepublishingCompleted`; every
    other status raises `SealCannotCompleteRepublishingError` carrying
    the current status.
  - Happy path (valid head hash + strictly-greater sequence) emits one
    event whose facility_code == state.facility_code, completed_by is the
    injected actor verbatim, and occurred_at == now.
  - The emitted event's facility_code is `state.facility_code`, never a
    freshly minted identity.
  - Pure: same (state, command, now, completed_by) returns equal events.

Cryptographic / schema-validated values (head hashes, sequence numbers,
the facility slug) use FIXED valid values copied from the example test;
only ids, clock, and (where safe) status are generated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealRepublishingCompleted,
    SealStatus,
)
from cora.federation.features import complete_seal_republishing
from cora.federation.features.complete_seal_republishing import (
    CompleteSealRepublishing,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_FACILITY_CODE = "aps-2bm"
_PRIOR_HEAD_HASH = "a" * 64
_NEW_HEAD_HASH = "b" * 64
_PRIOR_SEQUENCE_NUMBER = 5
_NEW_SEQUENCE_NUMBER = 6

_COMPLETABLE_SOURCES = (SealStatus.REPUBLISHING,)
_DISALLOWED_SOURCES = tuple(s for s in SealStatus if s not in frozenset(_COMPLETABLE_SOURCES))


def _seal(
    *,
    status: SealStatus,
    online_credential_id: UUID,
    offline_credential_id: UUID,
    initialized_by: ActorId,
    initialized_at: datetime,
) -> Seal:
    return Seal(
        facility_code=FacilityCode(_FACILITY_CODE),
        online_credential_id=online_credential_id,
        offline_credential_id=offline_credential_id,
        current_head_hash=_PRIOR_HEAD_HASH,
        current_sequence_number=_PRIOR_SEQUENCE_NUMBER,
        initialized_by=initialized_by,
        initialized_at=initialized_at,
        status=status,
    )


def _command() -> CompleteSealRepublishing:
    return CompleteSealRepublishing(
        facility_code=_FACILITY_CODE,
        new_head_hash=_NEW_HEAD_HASH,
        new_sequence_number=_NEW_SEQUENCE_NUMBER,
    )


@pytest.mark.unit
@given(now=aware_datetimes(), completed_by_uuid=st.uuids())
def test_complete_seal_republishing_with_none_state_raises_not_found(
    now: datetime,
    completed_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SealNotFoundError` carrying the facility slug."""
    with pytest.raises(SealNotFoundError) as exc:
        complete_seal_republishing.decide(
            state=None,
            command=_command(),
            now=now,
            completed_by=ActorId(completed_by_uuid),
        )
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    online_uuid=st.uuids(),
    offline_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    completed_by_uuid=st.uuids(),
)
def test_complete_seal_republishing_from_republishing_emits_single_event(
    now: datetime,
    online_uuid: UUID,
    offline_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    completed_by_uuid: UUID,
) -> None:
    """Republishing is the only completable source; emits one event threading now + actor."""
    completed_by = ActorId(completed_by_uuid)
    events = complete_seal_republishing.decide(
        state=_seal(
            status=SealStatus.REPUBLISHING,
            online_credential_id=online_uuid,
            offline_credential_id=offline_uuid,
            initialized_by=ActorId(initialized_by_uuid),
            initialized_at=initialized_at,
        ),
        command=_command(),
        now=now,
        completed_by=completed_by,
    )
    assert events == [
        SealRepublishingCompleted(
            facility_code=FacilityCode(_FACILITY_CODE),
            new_head_hash=_NEW_HEAD_HASH,
            new_sequence_number=_NEW_SEQUENCE_NUMBER,
            completed_by=completed_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    online_uuid=st.uuids(),
    offline_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    completed_by_uuid=st.uuids(),
)
def test_complete_seal_republishing_from_disallowed_source_raises_cannot_complete(
    source: SealStatus,
    now: datetime,
    online_uuid: UUID,
    offline_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    completed_by_uuid: UUID,
) -> None:
    """Any source other than Republishing raises, carrying the current status + slug."""
    with pytest.raises(SealCannotCompleteRepublishingError) as exc:
        complete_seal_republishing.decide(
            state=_seal(
                status=source,
                online_credential_id=online_uuid,
                offline_credential_id=offline_uuid,
                initialized_by=ActorId(initialized_by_uuid),
                initialized_at=initialized_at,
            ),
            command=_command(),
            now=now,
            completed_by=ActorId(completed_by_uuid),
        )
    assert exc.value.current_status is source
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    online_uuid=st.uuids(),
    offline_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    completed_by_uuid=st.uuids(),
)
def test_complete_seal_republishing_emits_event_with_state_facility_code(
    now: datetime,
    online_uuid: UUID,
    offline_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    completed_by_uuid: UUID,
) -> None:
    """The emitted event's facility_code is state.facility_code; transitions never mint identity."""
    state = _seal(
        status=SealStatus.REPUBLISHING,
        online_credential_id=online_uuid,
        offline_credential_id=offline_uuid,
        initialized_by=ActorId(initialized_by_uuid),
        initialized_at=initialized_at,
    )
    events = complete_seal_republishing.decide(
        state=state,
        command=_command(),
        now=now,
        completed_by=ActorId(completed_by_uuid),
    )
    assert events[0].facility_code == state.facility_code


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    online_uuid=st.uuids(),
    offline_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    completed_by_uuid=st.uuids(),
)
def test_complete_seal_republishing_records_injected_actor_verbatim(
    now: datetime,
    online_uuid: UUID,
    offline_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    completed_by_uuid: UUID,
) -> None:
    """The decider records the handler-injected actor id without synthesising one."""
    completed_by = ActorId(completed_by_uuid)
    events = complete_seal_republishing.decide(
        state=_seal(
            status=SealStatus.REPUBLISHING,
            online_credential_id=online_uuid,
            offline_credential_id=offline_uuid,
            initialized_by=ActorId(initialized_by_uuid),
            initialized_at=initialized_at,
        ),
        command=_command(),
        now=now,
        completed_by=completed_by,
    )
    assert events[0].completed_by == completed_by


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    online_uuid=st.uuids(),
    offline_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    completed_by_uuid=st.uuids(),
)
def test_complete_seal_republishing_is_pure_same_input_same_output(
    now: datetime,
    online_uuid: UUID,
    offline_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    completed_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _seal(
        status=SealStatus.REPUBLISHING,
        online_credential_id=online_uuid,
        offline_credential_id=offline_uuid,
        initialized_by=ActorId(initialized_by_uuid),
        initialized_at=initialized_at,
    )
    command = _command()
    completed_by = ActorId(completed_by_uuid)
    first = complete_seal_republishing.decide(
        state=state, command=command, now=now, completed_by=completed_by
    )
    second = complete_seal_republishing.decide(
        state=state, command=command, now=now, completed_by=completed_by
    )
    assert first == second
