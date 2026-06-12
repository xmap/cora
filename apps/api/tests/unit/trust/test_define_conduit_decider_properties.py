"""Property-based tests for `define_conduit.decide` (Trust BC).

Complements the example-based `test_define_conduit_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, verdict_logbook_id)
        -> list[ConduitDefined | ConduitLogbookOpened]

and auto-opens the per-Conduit verdict logbook, so the happy path
always returns TWO events.

Load-bearing properties:

  - Any non-None state always raises `ConduitAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the empty stream the call emits exactly two events: a
    `ConduitDefined` genesis followed by a `ConduitLogbookOpened`.
  - Both events thread the injected ids: conduit_id == new_id on each,
    logbook_id == verdict_logbook_id on the logbook-open, and
    occurred_at == now on both.
  - The `ConduitDefined` carries the command's endpoint zone ids and
    the trimmed name verbatim.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_VERDICT,
    Conduit,
    ConduitAlreadyExistsError,
    ConduitDefined,
    ConduitLogbookOpened,
    ConduitName,
)
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

# ConduitName trims and bounds to 1-200 chars; whitespace-free ASCII
# survives the `.strip()` round-trip so the generated value equals the
# emitted name verbatim.
_NAME = printable_ascii_text(min_size=1, max_size=200)
_FIXED_EXISTING_NAME = ConduitName("Existing")


def _state(
    *,
    state_id: UUID,
    source_zone_id: UUID,
    target_zone_id: UUID,
) -> Conduit:
    return Conduit(
        id=state_id,
        name=_FIXED_EXISTING_NAME,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
    )


def _command(*, name: str, source_zone_id: UUID, target_zone_id: UUID) -> DefineConduit:
    return DefineConduit(
        name=name,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
    )


@pytest.mark.unit
@given(
    state_id=st.uuids(),
    existing_source=st.uuids(),
    existing_target=st.uuids(),
    name=_NAME,
    source_zone_id=st.uuids(),
    target_zone_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    verdict_logbook_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    state_id: UUID,
    existing_source: UUID,
    existing_target: UUID,
    name: str,
    source_zone_id: UUID,
    target_zone_id: UUID,
    now: datetime,
    new_id: UUID,
    verdict_logbook_id: UUID,
) -> None:
    """Any non-None state raises ConduitAlreadyExistsError carrying state.id."""
    existing = _state(
        state_id=state_id,
        source_zone_id=existing_source,
        target_zone_id=existing_target,
    )
    with pytest.raises(ConduitAlreadyExistsError) as exc:
        define_conduit.decide(
            state=existing,
            command=_command(
                name=name,
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            ),
            now=now,
            new_id=new_id,
            verdict_logbook_id=verdict_logbook_id,
        )
    assert exc.value.conduit_id == state_id


@pytest.mark.unit
@given(
    name=_NAME,
    source_zone_id=st.uuids(),
    target_zone_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    verdict_logbook_id=st.uuids(),
)
def test_define_on_empty_stream_emits_defined_then_logbook_opened(
    name: str,
    source_zone_id: UUID,
    target_zone_id: UUID,
    now: datetime,
    new_id: UUID,
    verdict_logbook_id: UUID,
) -> None:
    """Empty stream emits exactly ConduitDefined then ConduitLogbookOpened."""
    events = define_conduit.decide(
        state=None,
        command=_command(
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ),
        now=now,
        new_id=new_id,
        verdict_logbook_id=verdict_logbook_id,
    )
    assert len(events) == 2
    assert isinstance(events[0], ConduitDefined)
    assert isinstance(events[1], ConduitLogbookOpened)


@pytest.mark.unit
@given(
    name=_NAME,
    source_zone_id=st.uuids(),
    target_zone_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    verdict_logbook_id=st.uuids(),
)
def test_define_threads_injected_fields_into_both_events(
    name: str,
    source_zone_id: UUID,
    target_zone_id: UUID,
    now: datetime,
    new_id: UUID,
    verdict_logbook_id: UUID,
) -> None:
    """Both events carry conduit_id=new_id and occurred_at=now; the logbook
    carries logbook_id=verdict_logbook_id and the verdict kind."""
    events = define_conduit.decide(
        state=None,
        command=_command(
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ),
        now=now,
        new_id=new_id,
        verdict_logbook_id=verdict_logbook_id,
    )
    defined, opened = events
    assert isinstance(defined, ConduitDefined)
    assert isinstance(opened, ConduitLogbookOpened)
    assert defined.conduit_id == new_id
    assert defined.occurred_at == now
    assert opened.conduit_id == new_id
    assert opened.occurred_at == now
    assert opened.logbook_id == verdict_logbook_id
    assert opened.kind == LOGBOOK_KIND_VERDICT


@pytest.mark.unit
@given(
    name=_NAME,
    source_zone_id=st.uuids(),
    target_zone_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    verdict_logbook_id=st.uuids(),
)
def test_define_carries_command_endpoints_and_trimmed_name(
    name: str,
    source_zone_id: UUID,
    target_zone_id: UUID,
    now: datetime,
    new_id: UUID,
    verdict_logbook_id: UUID,
) -> None:
    """The genesis event carries the command endpoints and the trimmed name."""
    events = define_conduit.decide(
        state=None,
        command=_command(
            name=name,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        ),
        now=now,
        new_id=new_id,
        verdict_logbook_id=verdict_logbook_id,
    )
    defined = events[0]
    assert isinstance(defined, ConduitDefined)
    assert defined.source_zone_id == source_zone_id
    assert defined.target_zone_id == target_zone_id
    assert defined.name == ConduitName(name).value


@pytest.mark.unit
@given(
    name=_NAME,
    source_zone_id=st.uuids(),
    target_zone_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    verdict_logbook_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    name: str,
    source_zone_id: UUID,
    target_zone_id: UUID,
    now: datetime,
    new_id: UUID,
    verdict_logbook_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(
        name=name,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
    )
    first = define_conduit.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        verdict_logbook_id=verdict_logbook_id,
    )
    second = define_conduit.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        verdict_logbook_id=verdict_logbook_id,
    )
    assert first == second
