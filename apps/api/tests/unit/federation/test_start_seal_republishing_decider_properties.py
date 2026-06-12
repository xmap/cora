"""Property-based tests for `start_seal_republishing.decide` (Federation BC).

Complements the example-based `test_start_seal_republishing_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition with actor attribution

    (state, command, now, started_by) -> list[SealRepublishingStarted]

The Seal is a per-facility singleton keyed by `facility_code` (a slug
`FacilityCode`), not a uuid, so identity is threaded and asserted as
the facility code, not an id.

Load-bearing properties:

  - state=None always raises `SealNotFoundError` carrying
    command.facility_code.
  - The source-state partition is total over `SealStatus`: only `Live`
    emits exactly one `SealRepublishingStarted` (facility_code=state's,
    occurred_at=now, started_by threaded); every other status raises
    `SealCannotStartRepublishingError` carrying the current status.
  - The emitted event's facility_code is `state.facility_code`, and the
    injected `started_by` / `now` are threaded onto the event verbatim.
  - Pure: same (state, command, now, started_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealRepublishingStarted,
    SealStatus,
)
from cora.federation.features import start_seal_republishing
from cora.federation.features.start_seal_republishing import StartSealRepublishing
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_FACILITY_CODE = "aps-2bm"
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-000000fec0b1")

_ALLOWED_SOURCES = (SealStatus.LIVE,)
_DISALLOWED_SOURCES = tuple(s for s in SealStatus if s not in frozenset(_ALLOWED_SOURCES))


def _seal(*, status: SealStatus, initialized_by_uuid: UUID, initialized_at: datetime) -> Seal:
    return Seal(
        facility_code=FacilityCode(_FACILITY_CODE),
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by=ActorId(initialized_by_uuid),
        initialized_at=initialized_at,
        status=status,
    )


def _command(*, reason: str | None) -> StartSealRepublishing:
    return StartSealRepublishing(facility_code=_FACILITY_CODE, reason=reason)


@pytest.mark.unit
@given(now=aware_datetimes(), started_by_uuid=st.uuids())
def test_start_seal_republishing_with_none_state_always_raises_not_found(
    now: datetime,
    started_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SealNotFoundError` carrying command.facility_code."""
    with pytest.raises(SealNotFoundError) as exc:
        start_seal_republishing.decide(
            state=None,
            command=_command(reason=None),
            now=now,
            started_by=ActorId(started_by_uuid),
        )
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    started_by_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    reason=st.none() | printable_ascii_text(max_size=64),
)
def test_start_seal_republishing_from_live_emits_single_event(
    now: datetime,
    started_by_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    reason: str | None,
) -> None:
    """Live is the only republishing source; emits one SealRepublishingStarted."""
    started_by = ActorId(started_by_uuid)
    events = start_seal_republishing.decide(
        state=_seal(
            status=SealStatus.LIVE,
            initialized_by_uuid=initialized_by_uuid,
            initialized_at=initialized_at,
        ),
        command=_command(reason=reason),
        now=now,
        started_by=started_by,
    )
    assert events == [
        SealRepublishingStarted(
            facility_code=FacilityCode(_FACILITY_CODE),
            started_by=started_by,
            occurred_at=now,
            reason=reason,
        )
    ]


@pytest.mark.unit
@given(
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
    started_by_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
)
def test_start_seal_republishing_from_disallowed_source_always_raises_cannot_start(
    source: SealStatus,
    now: datetime,
    started_by_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
) -> None:
    """Any source other than Live raises, carrying the current status and facility code."""
    with pytest.raises(SealCannotStartRepublishingError) as exc:
        start_seal_republishing.decide(
            state=_seal(
                status=source,
                initialized_by_uuid=initialized_by_uuid,
                initialized_at=initialized_at,
            ),
            command=_command(reason=None),
            now=now,
            started_by=ActorId(started_by_uuid),
        )
    assert exc.value.current_status is source
    assert exc.value.facility_id == _FACILITY_CODE


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    started_by_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
)
def test_start_seal_republishing_threads_injected_fields_onto_event(
    now: datetime,
    started_by_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
) -> None:
    """Injected started_by / now and the state's facility_code thread onto the event verbatim."""
    started_by = ActorId(started_by_uuid)
    events = start_seal_republishing.decide(
        state=_seal(
            status=SealStatus.LIVE,
            initialized_by_uuid=initialized_by_uuid,
            initialized_at=initialized_at,
        ),
        command=_command(reason=None),
        now=now,
        started_by=started_by,
    )
    event = events[0]
    assert event.facility_code == FacilityCode(_FACILITY_CODE)
    assert event.started_by == started_by
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    started_by_uuid=st.uuids(),
    initialized_by_uuid=st.uuids(),
    initialized_at=aware_datetimes(),
    reason=st.none() | printable_ascii_text(max_size=64),
)
def test_start_seal_republishing_is_pure_same_input_returns_equal_events(
    now: datetime,
    started_by_uuid: UUID,
    initialized_by_uuid: UUID,
    initialized_at: datetime,
    reason: str | None,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _seal(
        status=SealStatus.LIVE,
        initialized_by_uuid=initialized_by_uuid,
        initialized_at=initialized_at,
    )
    command = _command(reason=reason)
    started_by = ActorId(started_by_uuid)
    first = start_seal_republishing.decide(
        state=state, command=command, now=now, started_by=started_by
    )
    second = start_seal_republishing.decide(
        state=state, command=command, now=now, started_by=started_by
    )
    assert first == second
