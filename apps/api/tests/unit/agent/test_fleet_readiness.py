from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.agent._seeded_fleet import SEEDED_FLEET, SeededAgent
from cora.agent.aggregates.agent import AgentStatus
from cora.agent.fleet_readiness import (
    FleetReadiness,
    fleet_readiness,
    log_fleet_readiness,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_A = SeededAgent(UUID("00000000-0000-0000-0000-0000000000a1"), "AlphaWatcher")
_B = SeededAgent(UUID("00000000-0000-0000-0000-0000000000b2"), "BetaWatcher")
_C = SeededAgent(UUID("00000000-0000-0000-0000-0000000000c3"), "GammaWatcher")
_FLEET = (_A, _B, _C)


def test_fleet_readiness_versioned_member_counts_as_ready() -> None:
    result = fleet_readiness({_A.agent_id: AgentStatus.VERSIONED}, (_A,))
    assert result.ready == ("AlphaWatcher",)
    assert result.stranded is False


def test_fleet_readiness_defined_member_reports_stranded() -> None:
    result = fleet_readiness({_A.agent_id: AgentStatus.DEFINED}, (_A,))
    assert result.not_ready == ("AlphaWatcher",)
    assert result.stranded is True


@pytest.mark.parametrize(
    ("status", "bucket"),
    [
        (AgentStatus.SUSPENDED, "held"),
        (AgentStatus.DEPRECATED, "retired"),
    ],
)
def test_fleet_readiness_deliberately_stopped_member_is_not_stranded(
    status: AgentStatus, bucket: str
) -> None:
    result = fleet_readiness({_A.agent_id: status}, (_A,))
    assert getattr(result, bucket) == ("AlphaWatcher",)
    assert result.stranded is False


def test_fleet_readiness_member_missing_from_the_record_lands_in_absent() -> None:
    result = fleet_readiness({_A.agent_id: None}, (_A,))
    assert result.absent == ("AlphaWatcher",)


def test_fleet_readiness_member_missing_from_the_lookup_still_counts() -> None:
    """A member the caller never looked up must not vanish from the total.

    Ranging over the status map instead of the fleet would silently
    shrink the denominator, so "2 of 2 ready" would be reported for a
    fleet of three with one unread. That is the same silent-incompleteness
    shape the fleet value was introduced to close.
    """
    result = fleet_readiness({_A.agent_id: AgentStatus.VERSIONED}, _FLEET)
    assert result.total == 3
    assert result.absent == ("BetaWatcher", "GammaWatcher")


def test_fleet_readiness_sorts_a_mixed_fleet_into_every_bucket() -> None:
    result = fleet_readiness(
        {
            _A.agent_id: AgentStatus.VERSIONED,
            _B.agent_id: AgentStatus.DEFINED,
            _C.agent_id: AgentStatus.SUSPENDED,
        },
        _FLEET,
    )
    assert (result.ready, result.not_ready, result.held) == (
        ("AlphaWatcher",),
        ("BetaWatcher",),
        ("GammaWatcher",),
    )
    assert result.total == 3


def test_fleet_readiness_ignores_a_status_for_an_unshipped_agent() -> None:
    result = fleet_readiness(
        {_A.agent_id: AgentStatus.VERSIONED, uuid4(): AgentStatus.DEFINED}, (_A,)
    )
    assert result.total == 1
    assert result.stranded is False


def test_fleet_readiness_reports_names_in_the_fleet_s_own_order() -> None:
    forward = fleet_readiness(
        dict.fromkeys((m.agent_id for m in _FLEET), AgentStatus.DEFINED), _FLEET
    )
    assert forward.not_ready == ("AlphaWatcher", "BetaWatcher", "GammaWatcher")


def test_fleet_readiness_over_the_real_shipped_fleet_counts_every_member() -> None:
    """The denominator has to be the fleet CORA actually ships.

    Pinning it against `SEEDED_FLEET` rather than a fixture is what makes
    a future agent added without a readiness story show up here as well as
    in the completeness test.
    """
    result = fleet_readiness({})
    assert result.total == len(SEEDED_FLEET)
    assert len(result.absent) == len(SEEDED_FLEET)


def _emit(readiness: FleetReadiness) -> Sequence[Mapping[str, Any]]:
    with structlog.testing.capture_logs() as logs:
        log_fleet_readiness(readiness)
    return logs


def test_log_fleet_readiness_stranded_fleet_warns_and_names_the_remedy() -> None:
    entry = next(
        e
        for e in _emit(FleetReadiness((), ("RunWitness",), (), (), ()))
        if e["event"] == "agent_fleet.stranded"
    )
    assert entry["log_level"] == "warning"
    assert entry["not_ready"] == ["RunWitness"]
    assert entry["remedy"] == "promote_seeded_fleet"


def test_log_fleet_readiness_healthy_fleet_does_not_warn() -> None:
    logs = _emit(FleetReadiness(("RunWitness",), (), (), (), ()))
    assert [e["event"] for e in logs] == ["agent_fleet.ready"]
    assert not [e for e in logs if e["log_level"] == "warning"]


def test_log_fleet_readiness_suspended_member_alone_does_not_warn() -> None:
    """A paused agent is somebody's decision, not a fault.

    Warning about it would train an operator to ignore the line, which
    costs exactly the signal this function exists to add.
    """
    assert not [
        e for e in _emit(FleetReadiness(("A",), (), ("B",), (), ())) if e["log_level"] == "warning"
    ]


def test_log_fleet_readiness_absent_member_warns_on_its_own_line() -> None:
    logs = _emit(FleetReadiness(("A",), (), (), (), ("B",)))
    assert [e["event"] for e in logs] == ["agent_fleet.ready", "agent_fleet.absent"]
    assert next(e for e in logs if e["event"] == "agent_fleet.absent")["log_level"] == "warning"
