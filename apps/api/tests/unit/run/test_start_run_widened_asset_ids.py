"""Runtime contract for start_run's ancestor-chain scope widening (Slice 5, Anti-hook 4b).

Pins the handler-level wiring the behavioral canary
(`test_start_run_enclosure_preflight`) can't isolate: that the rows
returned by `AssetLookup.ancestors_of` are unioned into the clearance
scope the downstream Safety lookup receives, AND that each ancestor
row's `located_in_enclosure_id` (including a Decommissioned ancestor's)
is collected into the id-set the enclosure gate looks up. A retired
intermediate's located-in Enclosure must still reach the gate (the
Enclosure's own lifecycle, applied downstream by `find_by_ids` + the
decider, decides whether it blocks), while a live ancestor's must too.

Strategy: stub `ancestors_of` to return a fixed row set (the plan-bound
Asset + one live ancestor + one Decommissioned ancestor, each carrying a
distinct `located_in_enclosure_id`), and a recording `find_by_ids` that
captures the enclosure_ids the handler hands it. Assert every ancestor's
located-in Enclosure arrived, including the Decommissioned one's. The
handler still completes (the recorder returns no Enclosures, so the gate
is permit-by-default), so this also pins that the widening does not
itself break the happy path.
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
_DEVICE_ENCLOSURE_ID = UUID("01900000-0000-7000-8000-000000000e00")
_LIVE_ANCESTOR_ENCLOSURE_ID = UUID("01900000-0000-7000-8000-000000000e01")
_DEAD_ANCESTOR_ENCLOSURE_ID = UUID("01900000-0000-7000-8000-000000000e02")


def _result(
    asset_id: UUID,
    lifecycle: str,
    tier: str = "Unit",
    located_in_enclosure_id: UUID | None = None,
) -> AssetLookupResult:
    return AssetLookupResult(
        id=asset_id,
        name=f"asset-{asset_id}",
        tier=tier,
        lifecycle=lifecycle,
        family_affordances=frozenset(),
        located_in_enclosure_id=located_in_enclosure_id,
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
    """Captures the enclosure_ids `find_by_ids` is called with."""

    def __init__(self) -> None:
        self.captured: frozenset[UUID] | None = None

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        del enclosure_id
        return None

    async def find_by_ids(self, *, enclosure_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        self.captured = enclosure_ids
        return []


@pytest.mark.unit
async def test_widened_scope_includes_every_ancestor_regardless_of_lifecycle() -> None:
    """The walk collects the `located_in_enclosure_id` of EVERY ancestor,
    including a Decommissioned one. The containing Asset's lifecycle is NOT
    the source of truth for whether a physical interlock is live: the
    located-in Enclosure of a Decommissioned ancestor must still reach the
    gate (the Enclosure's own lifecycle filter, applied downstream by
    find_by_ids + the decider, decides whether it blocks). Filtering
    Decommissioned ancestors here would silently suppress an
    Active+NotPermitted Enclosure on a retired ancestor and admit the Run
    into an un-permitted hutch."""
    store = InMemoryEventStore()
    _, asset_id, _, _, plan_id, subject_id = await seed_full_chain(store)

    asset_lookup = _StubAssetLookup(
        frozenset(
            {
                _result(
                    asset_id,
                    lifecycle="Active",
                    tier="Device",
                    located_in_enclosure_id=_DEVICE_ENCLOSURE_ID,
                ),
                _result(
                    _LIVE_ANCESTOR_ID,
                    lifecycle="Active",
                    located_in_enclosure_id=_LIVE_ANCESTOR_ENCLOSURE_ID,
                ),
                _result(
                    _DEAD_ANCESTOR_ID,
                    lifecycle="Decommissioned",
                    located_in_enclosure_id=_DEAD_ANCESTOR_ENCLOSURE_ID,
                ),
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
    # every ancestor's located-in Enclosure entered the gate's id-set, the
    # plan-bound Asset's stays...
    assert _DEVICE_ENCLOSURE_ID in recorder.captured
    assert _LIVE_ANCESTOR_ENCLOSURE_ID in recorder.captured
    # ...AND the Decommissioned ancestor's located-in Enclosure is included
    # (its Enclosure must still be able to gate; the Enclosure's own
    # lifecycle decides downstream).
    assert _DEAD_ANCESTOR_ENCLOSURE_ID in recorder.captured


@pytest.mark.unit
async def test_empty_ancestor_walk_leaves_scope_unwidened() -> None:
    """When ancestors_of returns nothing (no projection rows), no row carries
    a `located_in_enclosure_id`, so the enclosure gate's id-set is empty and
    the gate is permit-by-default: the walk adds nothing."""
    store = InMemoryEventStore()
    _, _asset_id, _, _, plan_id, subject_id = await seed_full_chain(store)

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
    assert recorder.captured == frozenset()


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
