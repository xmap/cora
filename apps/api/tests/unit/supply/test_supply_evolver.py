"""Supply evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyDegraded,
    SupplyDeregistered,
    SupplyEvent,
    SupplyMarkedAvailable,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyName,
    SupplyRegistered,
    SupplyRestored,
    SupplyScope,
    SupplyStatus,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005222")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000005223"))


# ---------- fold (genesis only) ----------


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_lands_in_unknown() -> None:
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2 drop",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Supply(
        id=_SUPPLY_ID,
        scope=SupplyScope.BEAMLINE,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2 drop"),
        status=SupplyStatus.UNKNOWN,
    )


# ---------- fold (genesis + transition) ----------


@pytest.mark.unit
def test_fold_genesis_then_marked_available_lands_in_available() -> None:
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Facility",
                kind="PhotonBeam",
                name="APS storage-ring beam",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="control room confirms beam delivered",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == SupplyStatus.AVAILABLE
    # Identity + address preserved across the transition (additive-state pattern).
    assert state.id == _SUPPLY_ID
    assert state.scope == SupplyScope.FACILITY
    assert state.kind == "PhotonBeam"
    assert state.name.value == "APS storage-ring beam"


# ---------- transitions on empty state ----------


@pytest.mark.unit
def test_evolve_marked_available_on_empty_state_raises() -> None:
    """Transition events applied to an empty stream are corruption (require_state guard)."""
    with pytest.raises(ValueError, match="SupplyMarkedAvailable cannot be applied to empty state"):
        evolve(
            None,
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="r",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
        )


# ---------- evolver purity ----------


@pytest.mark.unit
def test_evolver_returns_new_state_does_not_mutate_input() -> None:
    initial = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            )
        ]
    )
    assert initial is not None
    transitioned = evolve(
        initial,
        SupplyMarkedAvailable(
            supply_id=_SUPPLY_ID,
            from_status="Unknown",
            reason="r",
            trigger="Operator",
            triggered_by=_ACTOR_ID,
            occurred_at=_NOW,
        ),
    )
    # Initial state is untouched (frozen dataclass guarantee).
    assert initial.status == SupplyStatus.UNKNOWN
    assert transitioned.status == SupplyStatus.AVAILABLE
    assert transitioned is not initial


# ---------- 10a-b: 4 new transition arms ----------


def _genesis_state() -> Supply:
    """Quick helper to fold a SupplyRegistered into starting state."""
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            )
        ]
    )
    assert state is not None
    return state


@pytest.mark.parametrize(
    ("event", "expected_status"),
    [
        (
            SupplyDegraded(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="half-current",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyStatus.DEGRADED,
        ),
        (
            SupplyMarkedUnavailable(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="beam dump",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyStatus.UNAVAILABLE,
        ),
        (
            SupplyMarkedRecovering(
                supply_id=_SUPPLY_ID,
                from_status="Unavailable",
                reason="beam returning",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyStatus.RECOVERING,
        ),
        (
            SupplyRestored(
                supply_id=_SUPPLY_ID,
                from_status="Recovering",
                reason="ops confirms stable",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyStatus.AVAILABLE,
        ),
        (
            SupplyDeregistered(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="duplicate; re-registering correctly",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyStatus.DECOMMISSIONED,
        ),
    ],
)
@pytest.mark.unit
def test_evolver_arms_for_each_transition_event_set_target_status(
    event: SupplyEvent, expected_status: SupplyStatus
) -> None:
    """Pin per-event-type status mapping; the evolver does NOT enforce
    source-state guards (that's the decider's job). Identity + address
    preserved across the transition."""
    prior = _genesis_state()
    evolved = evolve(prior, event)
    assert evolved.status == expected_status
    assert evolved.id == _SUPPLY_ID
    assert evolved.scope == SupplyScope.BEAMLINE
    assert evolved.kind == "LiquidNitrogen"


@pytest.mark.parametrize(
    "event_type_name",
    [
        "SupplyDegraded",
        "SupplyMarkedUnavailable",
        "SupplyMarkedRecovering",
        "SupplyRestored",
        "SupplyDeregistered",
    ],
)
@pytest.mark.unit
def test_evolver_raises_on_transition_event_with_no_genesis(event_type_name: str) -> None:
    """Every transition event requires prior state; otherwise the stream
    is corrupt (transition before genesis)."""
    event_classes = {
        "SupplyDegraded": SupplyDegraded,
        "SupplyMarkedUnavailable": SupplyMarkedUnavailable,
        "SupplyMarkedRecovering": SupplyMarkedRecovering,
        "SupplyRestored": SupplyRestored,
        "SupplyDeregistered": SupplyDeregistered,
    }
    cls = event_classes[event_type_name]
    with pytest.raises(ValueError, match=f"{event_type_name} cannot be applied to empty state"):
        evolve(
            None,
            cls(
                supply_id=_SUPPLY_ID,
                from_status="x",
                reason="r",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_full_fsm_cycle_via_fold() -> None:
    """Walk the full health-FSM cycle via fold: register -> mark_available ->
    degrade -> mark_unavailable -> mark_recovering -> restore. All 6 events
    accumulate cleanly, identity preserved, terminal status is Available.
    The lifecycle-terminal `deregister` step has its own test below."""
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="walkdown",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyDegraded(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="half-current",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyMarkedUnavailable(
                supply_id=_SUPPLY_ID,
                from_status="Degraded",
                reason="full dump",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyMarkedRecovering(
                supply_id=_SUPPLY_ID,
                from_status="Unavailable",
                reason="beam returning",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyRestored(
                supply_id=_SUPPLY_ID,
                from_status="Recovering",
                reason="confirmed stable",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == SupplyStatus.AVAILABLE
    assert state.id == _SUPPLY_ID
    assert state.kind == "LiquidNitrogen"
    assert state.name.value == "2-BM LN2"


@pytest.mark.unit
def test_full_cycle_with_terminal_deregister_via_fold() -> None:
    """Health cycle + lifecycle terminal: register -> mark_available ->
    deregister. The terminal `Decommissioned` status is reachable from any
    non-Decommissioned source; identity preserved across the terminal
    transition. No transition exits Decommissioned (re-registration
    creates a fresh stream)."""
    state = fold(
        [
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="walkdown",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
            SupplyDeregistered(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="typo; re-registering",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == SupplyStatus.DECOMMISSIONED
    assert state.id == _SUPPLY_ID
    assert state.kind == "LiquidNitrogen"
    assert state.name.value == "2-BM LN2"
