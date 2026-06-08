"""Unit tests for the Conduit aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust.aggregates.conduit import (
    Conduit,
    ConduitLogbookAlreadyOpenError,
    ConduitLogbookNotOpenError,
    ConduitName,
    evolve,
    fold,
)
from cora.trust.aggregates.conduit.events import (
    ConduitDefined,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
)
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit


def _sample_schema() -> LogbookSchema:
    return LogbookSchema(fields={"x": LogbookFieldSpec(type="string")})


_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_conduit_defined_from_empty_state() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = evolve(
        None,
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=source,
            target_zone_id=target,
            occurred_at=_NOW,
        ),
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_conduit_defined_returns_conduit() -> None:
    conduit_id = uuid4()
    source = uuid4()
    target = uuid4()
    state = fold(
        [
            ConduitDefined(
                conduit_id=conduit_id,
                name="Detector-to-Storage",
                source_zone_id=source,
                target_zone_id=target,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Conduit(
        id=conduit_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    conduit_id = uuid4()
    events = [
        ConduitDefined(
            conduit_id=conduit_id,
            name="Detector-to-Storage",
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state.

    The decider emits ConduitDefined + ConduitLogbookOpened, and the
    evolver folds both into a Conduit with the traversals logbook id
    present in `logbooks`.
    """
    new_id = uuid4()
    logbook_id = uuid4()
    source = uuid4()
    target = uuid4()
    command = DefineConduit(
        name="  Detector-to-Storage  ",  # whitespace exercises the VO trim
        source_zone_id=source,
        target_zone_id=target,
    )

    events = define_conduit.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        traversals_logbook_id=logbook_id,
    )
    rebuilt = fold(events)

    assert rebuilt == Conduit(
        id=new_id,
        name=ConduitName("Detector-to-Storage"),
        source_zone_id=source,
        target_zone_id=target,
        logbooks={"traversals": logbook_id},
    )


# ---------- Channel-event arms ----------


def _genesis(conduit_id: object | None = None) -> ConduitDefined:
    return ConduitDefined(
        conduit_id=conduit_id or uuid4(),  # type: ignore[arg-type]
        name="Detector-to-Storage",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_evolve_channel_opened_adds_kind_id_pair_to_channels() -> None:
    genesis = _genesis()
    state = evolve(None, genesis)
    logbook_id = uuid4()
    after_open = evolve(
        state,
        ConduitLogbookOpened(
            conduit_id=genesis.conduit_id,
            logbook_id=logbook_id,
            kind="traversals",
            schema=_sample_schema(),
            occurred_at=_NOW,
        ),
    )
    assert after_open.logbooks == {"traversals": logbook_id}


@pytest.mark.unit
def test_evolve_channel_closed_removes_kind_entry() -> None:
    genesis = _genesis()
    state = evolve(None, genesis)
    logbook_id = uuid4()
    state = evolve(
        state,
        ConduitLogbookOpened(
            conduit_id=genesis.conduit_id,
            logbook_id=logbook_id,
            kind="traversals",
            schema=_sample_schema(),
            occurred_at=_NOW,
        ),
    )
    state = evolve(
        state,
        ConduitLogbookClosed(
            conduit_id=genesis.conduit_id,
            logbook_id=logbook_id,
            occurred_at=_NOW,
        ),
    )
    assert state.logbooks == {}


@pytest.mark.unit
def test_evolve_channel_opened_on_none_state_raises() -> None:
    """Defensive guard: a channel-open before genesis is stream
    contamination — fail loud."""
    with pytest.raises(ValueError, match="ConduitLogbookOpened cannot be applied to empty state"):
        evolve(
            None,
            ConduitLogbookOpened(
                conduit_id=uuid4(),
                logbook_id=uuid4(),
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_channel_closed_on_none_state_raises() -> None:
    with pytest.raises(ValueError, match="ConduitLogbookClosed cannot be applied to empty state"):
        evolve(
            None,
            ConduitLogbookClosed(conduit_id=uuid4(), logbook_id=uuid4(), occurred_at=_NOW),
        )


@pytest.mark.unit
def test_evolve_channel_opened_raises_when_kind_already_open() -> None:
    """At-most-one-open-per-kind invariant: opening a second channel
    of an existing kind raises with the existing channel id."""
    genesis = _genesis()
    first_id = uuid4()
    second_id = uuid4()
    state = evolve(None, genesis)
    state = evolve(
        state,
        ConduitLogbookOpened(
            conduit_id=genesis.conduit_id,
            logbook_id=first_id,
            kind="traversals",
            schema=_sample_schema(),
            occurred_at=_NOW,
        ),
    )
    with pytest.raises(ConduitLogbookAlreadyOpenError) as exc_info:
        evolve(
            state,
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=second_id,  # different id, same kind
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        )
    assert exc_info.value.kind == "traversals"
    assert exc_info.value.existing_logbook_id == first_id


@pytest.mark.unit
def test_evolve_channel_closed_raises_when_id_not_open() -> None:
    """Defensive guard: closing a channel that's not open is stream
    contamination."""
    genesis = _genesis()
    state = evolve(None, genesis)
    unknown_logbook_id = uuid4()
    with pytest.raises(ConduitLogbookNotOpenError) as exc_info:
        evolve(
            state,
            ConduitLogbookClosed(
                conduit_id=genesis.conduit_id,
                logbook_id=unknown_logbook_id,
                occurred_at=_NOW,
            ),
        )
    assert exc_info.value.logbook_id == unknown_logbook_id


@pytest.mark.unit
def test_fold_full_open_close_cycle_yields_empty_channels() -> None:
    """Channel lifecycle: open then close brings logbooks back to empty."""
    genesis = _genesis()
    logbook_id = uuid4()
    state = fold(
        [
            genesis,
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=logbook_id,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
            ConduitLogbookClosed(
                conduit_id=genesis.conduit_id,
                logbook_id=logbook_id,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.logbooks == {}


@pytest.mark.unit
def test_fold_supports_multiple_kinds_open_simultaneously() -> None:
    """One channel per kind open at a time, but multiple kinds can
    coexist. Future Run/Decision aggregates will use the same shape
    (frame_triggers, motor_positions, reasoning_tokens, ...)."""
    genesis = _genesis()
    ch_a = uuid4()
    ch_b = uuid4()
    state = fold(
        [
            genesis,
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=ch_a,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=ch_b,
                kind="other_kind",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.logbooks == {"traversals": ch_a, "other_kind": ch_b}


@pytest.mark.unit
def test_fold_supports_reopening_a_kind_after_close() -> None:
    """Close-then-reopen on the same kind works (the kind slot is
    free after close, so a fresh channel can take it)."""
    genesis = _genesis()
    first_id = uuid4()
    second_id = uuid4()
    state = fold(
        [
            genesis,
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=first_id,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
            ConduitLogbookClosed(
                conduit_id=genesis.conduit_id,
                logbook_id=first_id,
                occurred_at=_NOW,
            ),
            ConduitLogbookOpened(
                conduit_id=genesis.conduit_id,
                logbook_id=second_id,
                kind="traversals",
                schema=_sample_schema(),
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.logbooks == {"traversals": second_id}
