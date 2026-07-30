"""Pin: every Supply transition the FSM documents can actually be performed.

`SupplyStatus`'s docstring lists the transitions the aggregate supports.
That list is a promise, and until this test existed nothing checked it:
the promise lived in a docstring while the reality lived in six separate
slice deciders, each holding its own source-state allowlist. They drifted.

`Degraded -> Available` was documented and no slice performed it.
`mark_supply_available` accepts only `Unknown` (the first-observation
declaration) and `restore_supply` accepted only `Recovering`, so a
degraded Supply could go deeper but never back. The only exit was
`mark_supply_unavailable` then `mark_supply_recovering` then
`restore_supply`: three gestures for one, and the first appended "this
resource was unavailable" to an append-only log about a resource that was
never down. `degrade_supply` ships a live REST route and MCP tool and
`Degraded` is a permitted monitor target, so the dead end was reachable
both by hand and by sensor. It went unnoticed because nothing compared
the two lists.

Hence this test rather than a longer docstring. It drives every declared
transition through every slice decider that could produce it and fails
when one has no performer, naming the transition.

## Why the table is duplicated here rather than parsed

`_DOCUMENTED_TRANSITIONS` restates the FSM in code instead of parsing the
docstring. Parsing prose is brittle in the direction that matters: a
reformat would silently shrink the table and the test would pass while
checking less. A hand-kept table can fall out of step with the docstring,
but that is a visible edit in a diff, and `test_the_table_matches_the_status_enum`
below catches the shape errors that matter most (a status that vanished,
a table that emptied).

## Scope

Health transitions only. `deregister_supply`'s `-> Decommissioned` is a
lifecycle terminal reachable from every status and is not part of the
health FSM, so it is excluded rather than enumerated; `SupplyStatus`'s
docstring documents it separately for the same reason.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import Supply, SupplyName
from cora.supply.aggregates.supply import SupplyStatus as S
from cora.supply.features.degrade_supply.command import DegradeSupply
from cora.supply.features.degrade_supply.decider import decide as degrade
from cora.supply.features.mark_supply_available.command import MarkSupplyAvailable
from cora.supply.features.mark_supply_available.decider import decide as mark_available
from cora.supply.features.mark_supply_recovering.command import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering.decider import decide as mark_recovering
from cora.supply.features.mark_supply_unavailable.command import MarkSupplyUnavailable
from cora.supply.features.mark_supply_unavailable.decider import decide as mark_unavailable
from cora.supply.features.restore_supply.command import RestoreSupply
from cora.supply.features.restore_supply.decider import decide as restore

_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_REASON = "operator said so"
_ACTOR = ActorId(uuid4())

# Every health transition the `SupplyStatus` docstring lists.
_DOCUMENTED_TRANSITIONS: tuple[tuple[S, S], ...] = (
    (S.UNKNOWN, S.AVAILABLE),
    (S.UNKNOWN, S.DEGRADED),
    (S.UNKNOWN, S.UNAVAILABLE),
    (S.AVAILABLE, S.DEGRADED),
    (S.AVAILABLE, S.UNAVAILABLE),
    (S.DEGRADED, S.AVAILABLE),
    (S.DEGRADED, S.UNAVAILABLE),
    (S.UNAVAILABLE, S.RECOVERING),
    (S.RECOVERING, S.AVAILABLE),
    (S.RECOVERING, S.DEGRADED),
    (S.RECOVERING, S.UNAVAILABLE),
)

# Each slice: its name, the status it lands on, and a thunk that attempts
# the transition against a given state, raising if the slice refuses.
# Per-slice closures rather than one heterogeneous table so each decider
# keeps its own command type instead of collapsing to a union.
_Attempt = Callable[["Supply"], None]

_SLICES: tuple[tuple[str, S, _Attempt], ...] = (
    (
        "mark_supply_available",
        S.AVAILABLE,
        lambda st: _drop(
            mark_available(
                st,
                MarkSupplyAvailable(supply_id=st.id, reason=_REASON),
                now=_NOW,
                triggered_by=_ACTOR,
            )
        ),
    ),
    (
        "restore_supply",
        S.AVAILABLE,
        lambda st: _drop(
            restore(
                st,
                RestoreSupply(supply_id=st.id, reason=_REASON),
                now=_NOW,
                triggered_by=_ACTOR,
            )
        ),
    ),
    (
        "degrade_supply",
        S.DEGRADED,
        lambda st: _drop(
            degrade(
                st,
                DegradeSupply(supply_id=st.id, reason=_REASON),
                now=_NOW,
                triggered_by=_ACTOR,
            )
        ),
    ),
    (
        "mark_supply_unavailable",
        S.UNAVAILABLE,
        lambda st: _drop(
            mark_unavailable(
                st,
                MarkSupplyUnavailable(supply_id=st.id, reason=_REASON),
                now=_NOW,
                triggered_by=_ACTOR,
            )
        ),
    ),
    (
        "mark_supply_recovering",
        S.RECOVERING,
        lambda st: _drop(
            mark_recovering(
                st,
                MarkSupplyRecovering(supply_id=st.id, reason=_REASON),
                now=_NOW,
                triggered_by=_ACTOR,
            )
        ),
    ),
)


def _drop(_events: object) -> None:
    """Discard a decider's events; this probe only asks whether it refused."""
    return


def _supply(status: S) -> Supply:
    return Supply(
        id=uuid4(),
        kind="CoolingWater",
        name=SupplyName("probe"),
        facility_code=FacilityCode("aps"),
        status=status,
    )


def _performers(source: S, target: S) -> list[str]:
    """Names of the slices that accept `source` and land on `target`."""
    found: list[str] = []
    for name, lands_on, attempt in _SLICES:
        if lands_on is not target:
            continue
        try:
            attempt(_supply(source))
        except Exception:
            continue
        found.append(name)
    return found


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("source", "target"),
    _DOCUMENTED_TRANSITIONS,
    ids=[f"{s.value}->{t.value}" for s, t in _DOCUMENTED_TRANSITIONS],
)
def test_every_documented_transition_has_a_performer(source: S, target: S) -> None:
    performers = _performers(source, target)
    assert performers, (
        f"{source.value} -> {target.value} is documented in the SupplyStatus FSM "
        f"but no slice performs it. Either add a slice / widen a source-state "
        f"allowlist, or delete the transition from the docstring. Do not reach "
        f"for a multi-step workaround that records a status the resource was "
        f"never in."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("source", "target"),
    _DOCUMENTED_TRANSITIONS,
    ids=[f"{s.value}->{t.value}" for s, t in _DOCUMENTED_TRANSITIONS],
)
def test_no_documented_transition_has_two_performers(source: S, target: S) -> None:
    """Two slices performing one transition means two events for one fact.

    Not a hypothetical: `mark_supply_available` and `restore_supply` both
    land on `Available` and are kept apart purely by their source sets. If
    those ever overlap, the same operator gesture emits different events
    depending on which endpoint was called, and the record stops being
    readable.
    """
    performers = _performers(source, target)
    assert len(performers) <= 1, (
        f"{source.value} -> {target.value} is performed by {performers}; "
        f"one transition, one slice, one event class."
    )


@pytest.mark.architecture
def test_the_table_matches_the_status_enum() -> None:
    """Guards the guard: an emptied or stale table would pass vacuously.

    Checks the shape rather than the content, which is what a duplicated
    table can plausibly get wrong: statuses renamed or removed, or the
    table itself truncated.
    """
    assert len(_DOCUMENTED_TRANSITIONS) >= 11
    named = {s for pair in _DOCUMENTED_TRANSITIONS for s in pair}
    # Decommissioned is the lifecycle terminal, deliberately out of scope.
    assert named == set(S) - {S.DECOMMISSIONED}
    assert (S.DEGRADED, S.AVAILABLE) in _DOCUMENTED_TRANSITIONS, (
        "the transition this test was written for must stay in the table"
    )


@pytest.mark.architecture
def test_the_probe_can_detect_an_unperformable_transition() -> None:
    """Guards the guard again: prove `_performers` can return empty.

    A `_performers` that always found something would make the whole file
    vacuous. `Unavailable -> Available` is not in the documented FSM and
    no slice performs it (a downed resource passes through `Recovering`
    first), so it is a standing negative control.
    """
    assert _performers(S.UNAVAILABLE, S.AVAILABLE) == []
    assert (S.UNAVAILABLE, S.AVAILABLE) not in _DOCUMENTED_TRANSITIONS
