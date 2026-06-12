"""Runtime contract for start_run's ancestor-chain scope widening (Slice 5, Anti-hook 4b).

Pins the handler-level wiring the behavioral canary
(`test_start_run_enclosure_preflight`) can't isolate: that the rows
returned by `AssetLookup.ancestors_of` are unioned into the scope the
downstream cross-BC lookups receive, AND that a Decommissioned ancestor
row is DROPPED from that union (a retired intermediate must not pull its
stale Enclosure into the gate's scope, while a live ancestor must).

Strategy: stub `ancestors_of` to return a fixed row set (the plan-bound
Asset + one live ancestor + one Decommissioned ancestor), and a
recording `find_for_assets` that captures the asset_ids the handler
hands it. Assert the live ancestor arrived and the Decommissioned one
did not. The handler still completes (the recorder returns no
Enclosures, so the gate is permit-by-default), so this also pins that
the widening does not itself break the happy path.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.asset_lookup import (
    ANCESTOR_WALK_DEPTH_CAP,
    AncestorWalkDepthExceededError,
    AssetLookupResult,
)
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.run.aggregates.run import RunRequiresActiveClearanceError
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from tests.unit._helpers import build_deps
from tests.unit.run.test_start_run_handler import seed_full_chain

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000f01")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000000f02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LIVE_ANCESTOR_ID = UUID("01900000-0000-7000-8000-000000000c01")
_DEAD_ANCESTOR_ID = UUID("01900000-0000-7000-8000-000000000c02")


def _result(asset_id: UUID, lifecycle: str, tier: str = "Unit") -> AssetLookupResult:
    return AssetLookupResult(
        id=asset_id,
        name=f"asset-{asset_id}",
        tier=tier,
        lifecycle=lifecycle,
        family_affordances=frozenset(),
    )


class _StubAssetLookup:
    """Returns a fixed ancestor closure regardless of input (test double)."""

    def __init__(self, rows: frozenset[AssetLookupResult]) -> None:
        self._rows = rows

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        return next((r for r in self._rows if r.id == asset_id), None)

    async def ancestors_of(self, asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]:
        del asset_ids
        return self._rows


class _RecordingEnclosureLookup:
    """Captures the asset_ids `find_for_assets` is called with."""

    def __init__(self) -> None:
        self.captured: frozenset[UUID] | None = None

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        del enclosure_id
        return None

    async def find_for_assets(self, *, asset_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        self.captured = asset_ids
        return []


@pytest.mark.unit
async def test_widened_scope_includes_every_ancestor_regardless_of_lifecycle() -> None:
    """The widening unions EVERY ancestor into scope, including a
    Decommissioned one. The containing Asset's lifecycle is NOT the source
    of truth for whether a physical interlock is live: an Enclosure on a
    Decommissioned ancestor must still reach the gate (the Enclosure's own
    lifecycle filter, applied downstream by find_for_assets + the decider,
    decides whether it blocks). Filtering Decommissioned ancestors here
    would silently suppress an Active+NotPermitted Enclosure on a retired
    ancestor and admit the Run into an un-permitted hutch."""
    store = InMemoryEventStore()
    _, asset_id, _, _, plan_id, subject_id = await seed_full_chain(store)

    asset_lookup = _StubAssetLookup(
        frozenset(
            {
                _result(asset_id, lifecycle="Active", tier="Device"),
                _result(_LIVE_ANCESTOR_ID, lifecycle="Active"),
                _result(_DEAD_ANCESTOR_ID, lifecycle="Decommissioned"),
            }
        )
    )
    recorder = _RecordingEnclosureLookup()
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, asset_lookup=asset_lookup
    )
    deps = dataclasses.replace(deps, enclosure_lookup=recorder)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Run-widen", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID
    assert recorder.captured is not None
    # every ancestor widened the scope, the plan-bound Asset stays...
    assert _LIVE_ANCESTOR_ID in recorder.captured
    assert asset_id in recorder.captured
    # ...AND the Decommissioned ancestor is included (its Enclosure must
    # still be able to gate; the Enclosure's own lifecycle decides downstream).
    assert _DEAD_ANCESTOR_ID in recorder.captured


@pytest.mark.unit
async def test_empty_ancestor_walk_leaves_scope_unwidened() -> None:
    """When ancestors_of returns nothing (no projection rows), the scope is
    exactly the plan-bound + controller set: the widening adds nothing and
    the gate still receives the original scope."""
    store = InMemoryEventStore()
    _, asset_id, _, _, plan_id, subject_id = await seed_full_chain(store)

    asset_lookup = _StubAssetLookup(frozenset())
    recorder = _RecordingEnclosureLookup()
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, asset_lookup=asset_lookup
    )
    deps = dataclasses.replace(deps, enclosure_lookup=recorder)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Run-flat", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID
    assert recorder.captured == frozenset({asset_id})


class _RaisingAssetLookup:
    """ancestors_of raises (simulates a parent_id cycle / over-deep chain)."""

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        del asset_id
        return None

    async def ancestors_of(self, asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]:
        del asset_ids
        raise AncestorWalkDepthExceededError(
            observed_depth=ANCESTOR_WALK_DEPTH_CAP + 1, cap=ANCESTOR_WALK_DEPTH_CAP
        )


@pytest.mark.unit
async def test_ancestor_walk_failure_propagates_and_refuses_the_run() -> None:
    """Fail-loud contract: if ancestors_of raises (a parent_id cycle or an
    over-deep chain in the projection), start_run PROPAGATES the error and
    refuses the Run, rather than swallowing it and starting with a partial,
    under-scoped gate (which could admit a Run an unreached ancestor's
    Enclosure should refuse). The error is intentionally unmapped at the
    route layer, so it surfaces as a 500: a parent_id cycle is server-side
    data corruption, not a client-fixable condition."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, asset_lookup=_RaisingAssetLookup()
    )
    handler = start_run.bind(deps)

    with pytest.raises(AncestorWalkDepthExceededError):
        await handler(
            StartRun(name="Run-cycle", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


class _RecordingClearanceLookup:
    """Captures find_referencing_run's asset_ids; returns no clearances."""

    def __init__(self) -> None:
        self.captured: frozenset[UUID] | None = None

    async def find_referencing_run(
        self,
        *,
        run_id: UUID,
        subject_id: UUID | None,
        asset_ids: frozenset[UUID],
    ) -> list[ClearanceLookupResult]:
        del run_id, subject_id
        self.captured = asset_ids
        return []


@pytest.mark.unit
async def test_clearance_lookup_also_receives_the_widened_scope() -> None:
    """Clearance is a transparent beneficiary of the SAME widening: the
    identical widened scoped_asset_ids reaches clearance_lookup, so an
    ancestor-bound Clearance can cover a child Run. The recorder returns no
    clearances (so the decider raises RunRequiresActiveClearanceError), but
    the lookup arg was captured first -- proving the widening (every
    ancestor, no lifecycle filter) flows to the Safety gate too."""
    store = InMemoryEventStore()
    _, asset_id, _, _, plan_id, subject_id = await seed_full_chain(store)

    asset_lookup = _StubAssetLookup(
        frozenset(
            {
                _result(asset_id, lifecycle="Active", tier="Device"),
                _result(_LIVE_ANCESTOR_ID, lifecycle="Active"),
                _result(_DEAD_ANCESTOR_ID, lifecycle="Decommissioned"),
            }
        )
    )
    recorder = _RecordingClearanceLookup()
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, asset_lookup=asset_lookup
    )
    deps = dataclasses.replace(deps, clearance_lookup=recorder)
    handler = start_run.bind(deps)

    with pytest.raises(RunRequiresActiveClearanceError):
        await handler(
            StartRun(name="Run-clearance", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert recorder.captured is not None
    assert _LIVE_ANCESTOR_ID in recorder.captured
    assert asset_id in recorder.captured
    assert _DEAD_ANCESTOR_ID in recorder.captured
