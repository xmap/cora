"""Tests for the BLEPS-observed Supply seeder (`cora/supply/_supply_seed.py`).

Pins the three properties the monitor runtime depends on: the configured
Supplies exist with the right kind, re-running does not duplicate them,
and a freshly seeded Supply is registered but NOT Available.

That last one is the load-bearing choice. CORA has observed nothing about
the cooling water at boot, and the pre-flight gate is default-strict, so
an Available-at-boot Supply would pass a gate on a resource nobody has
looked at.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.config import BlepsSupplyChannelConfig, Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply._supply_seed import (
    UnknownSupplyNameError,
    seed_observed_supplies,
    supply_kind_from_name,
    validate_supply_names,
)
from cora.supply.adapters.postgres_supply_lookup import PostgresSupplyLookup
from cora.supply.aggregates.supply import SupplyStatus, fold, from_stored
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_COMMS = "2bmBLEPS:BLEPS:COMMUNICATIONS_FAULT"
_WATER = "2-BM cooling water"
_VACUUM = "2-BM beamline vacuum"


def _channels(*supplies: str) -> list[BlepsSupplyChannelConfig]:
    return [
        BlepsSupplyChannelConfig(
            supply=supply,
            label=f"{supply} channel",
            trip=f"2bmBLEPS:BLEPS:{i}_TRIP",
        )
        for i, supply in enumerate(supplies)
    ]


def _deps_with(db_pool: asyncpg.Pool, channels: list[BlepsSupplyChannelConfig]) -> Kernel:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(12)])
    return dataclasses.replace(
        deps,
        settings=Settings(  # type: ignore[call-arg]
            app_env="test",
            bleps_supply_channels=channels,
            # Required whenever channels are configured: without the
            # comms flag a stale BLEPS feed would be trusted forever.
            bleps_communications_fault_pv=_COMMS if channels else "",
        ),
        # The default is the synthetic AllSatisfiedSupplyLookup; the
        # seeder's re-boot pre-check reads real projection rows, which is
        # what production wires.
        supply_lookup=PostgresSupplyLookup(db_pool),
    )


def _names(deps: Kernel) -> frozenset[str]:
    """What the composition root computes and hands the seeder."""
    return frozenset(channel.supply for channel in deps.settings.bleps_supply_channels)


async def _status(deps: Kernel, supply_id: object) -> SupplyStatus | None:
    events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)  # type: ignore[arg-type]
    state = fold([from_stored(e) for e in events])
    return None if state is None else state.status


@pytest.mark.integration
async def test_no_channels_seeds_nothing(db_pool: asyncpg.Pool) -> None:
    """A generic boot configures no channels and must register no Supplies."""
    assert await seed_observed_supplies(_deps_with(db_pool, []), supply_names=frozenset()) == {}


@pytest.mark.integration
async def test_each_configured_supply_is_registered_once(db_pool: asyncpg.Pool) -> None:
    deps = _deps_with(db_pool, _channels(_WATER, _VACUUM))

    seeded = await seed_observed_supplies(deps, supply_names=_names(deps))

    assert sorted(seeded) == sorted([_WATER, _VACUUM])
    for supply_id in seeded.values():
        events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
        assert [e.event_type for e in events] == ["SupplyRegistered"]


@pytest.mark.integration
async def test_many_channels_on_one_supply_seed_one_supply(db_pool: asyncpg.Pool) -> None:
    """Eight cooling circuits are eight channels and one resource."""
    channels = [
        BlepsSupplyChannelConfig(
            supply=_WATER, label=f"Flow{n}", trip=f"2bmBLEPS:BLEPS:FLOW{n}_TRIP"
        )
        for n in range(1, 9)
    ]
    seeded = await seed_observed_supplies(
        _deps_with(db_pool, channels), supply_names=frozenset({_WATER})
    )
    assert list(seeded) == [_WATER]


@pytest.mark.integration
async def test_a_seeded_supply_is_registered_but_not_available(db_pool: asyncpg.Pool) -> None:
    """Unknown is what "no observation yet" means; Available is a person's word."""
    deps = _deps_with(db_pool, _channels(_WATER))

    seeded = await seed_observed_supplies(deps, supply_names=_names(deps))

    assert await _status(deps, seeded[_WATER]) is SupplyStatus.UNKNOWN


@pytest.mark.integration
async def test_an_unknown_supply_name_is_skipped_not_guessed(db_pool: asyncpg.Pool) -> None:
    """A guessed kind would never match a Method's needed_supplies."""
    deps = _deps_with(db_pool, _channels("not a supply CORA knows"))
    assert await seed_observed_supplies(deps, supply_names=_names(deps)) == {}


@pytest.mark.unit
def test_the_kind_table_covers_both_bleps_resources() -> None:
    assert supply_kind_from_name(_WATER) == "CoolingWater"
    assert supply_kind_from_name(_VACUUM) == "Vacuum"
    assert supply_kind_from_name("something else") is None


@pytest.mark.unit
def test_validate_supply_names_passes_every_recognized_name() -> None:
    validate_supply_names([_WATER, _VACUUM])  # must not raise


@pytest.mark.unit
def test_validate_supply_names_raises_loud_on_an_unrecognized_name() -> None:
    """The composition-root counterpart to
    test_an_unknown_supply_name_is_skipped_not_guessed above: that test
    pins seed_observed_supplies's own defensive skip-and-warn; this pins
    that main.py's boot-time call is what actually turns an unrecognized
    BLEPS_SUPPLY_CHANNELS entry into a hard failure instead of a
    permanently-unmonitored channel with one log line to show for it.
    """
    with pytest.raises(UnknownSupplyNameError) as excinfo:
        validate_supply_names([_WATER, "not a supply CORA knows"])
    assert excinfo.value.unknown_names == frozenset({"not a supply CORA knows"})


@pytest.mark.integration
async def test_a_second_boot_reuses_the_seeded_supplies(db_pool: asyncpg.Pool) -> None:
    """Re-running the hook must not append a second genesis event.

    The pre-check reads the projection, so this drains between calls
    exactly as the lifespan does. Without that drain the pre-check misses
    and every boot would register a duplicate resource, which is why the
    drain is called load-bearing in the seeder's docstring rather than
    merely tidy.
    """
    deps = _deps_with(db_pool, _channels(_WATER, _VACUUM))

    first = await seed_observed_supplies(deps, supply_names=_names(deps))
    registry = ProjectionRegistry()
    register_supply_projections(registry, deps)
    await drain_projections(db_pool, registry, deadline_seconds=5.0)
    second = await seed_observed_supplies(deps, supply_names=_names(deps))

    assert second == first
    for supply_id in first.values():
        events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
        assert [e.event_type for e in events] == ["SupplyRegistered"]
