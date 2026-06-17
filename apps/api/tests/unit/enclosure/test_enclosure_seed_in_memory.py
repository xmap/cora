"""In-memory unit tests for `seed_enclosures` paths the Postgres suite cannot reach.

The integration seeder tests run against `PostgresEnclosureLookup`, which
has no `register`, so the in-memory mirror is a no-op there. These tests
drive the seeder through `make_inmemory_kernel` to pin:
  - the in-memory `EnclosureLookup` mirror (a freshly seeded enclosure is
    visible to the in-process monitor without projection catch-up); and
  - the `ConcurrencyError` lost-race branch, both when the address
    resolves to the live id and when it falls back to the minted id.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.enclosure import seed_enclosures
from cora.infrastructure.adapters.in_memory_enclosure_lookup import InMemoryEnclosureLookup
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import AllowAllAuthorize
from cora.infrastructure.ports.clock import FakeClock
from cora.infrastructure.ports.enclosure_lookup import (
    AlwaysPermittedEnclosureLookup,
    EnclosureLookupResult,
)
from cora.infrastructure.ports.id_generator import FixedIdGenerator

_T0 = datetime(2026, 6, 17, 10, 0, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_seed_enclosures_mirrors_into_in_memory_lookup() -> None:
    name = "hutch-mem"
    lookup = InMemoryEnclosureLookup()
    kernel = make_inmemory_kernel(
        settings=Settings(app_env="test", enclosure_permit_pvs={name: "pvA"}),  # type: ignore[call-arg]
        clock=FakeClock(_T0),
        id_generator=FixedIdGenerator([uuid4(), uuid4(), uuid4()]),
        authz=AllowAllAuthorize(),
        enclosure_lookup=lookup,
    )

    result = await seed_enclosures(kernel)

    row = await lookup.lookup_by_name(facility_code="cora", name=name)
    assert row is not None
    assert row.enclosure_id == result[name]
    assert row.permit_status == "Unknown"
    assert row.lifecycle == "Active"


@pytest.mark.unit
async def test_seed_enclosure_concurrency_resolves_live_id() -> None:
    name = "hutch-race"
    minted_id = uuid4()
    resolved_id = uuid4()
    kernel = make_inmemory_kernel(
        settings=Settings(app_env="test", enclosure_permit_pvs={name: "pvA"}),  # type: ignore[call-arg]
        clock=FakeClock(_T0),
        id_generator=FixedIdGenerator([minted_id, uuid4(), uuid4(), minted_id, uuid4(), uuid4()]),
        authz=AllowAllAuthorize(),
        enclosure_lookup=AlwaysPermittedEnclosureLookup(),
    )

    first = await seed_enclosures(kernel)
    assert first[name] == minted_id  # stream now occupied at the minted id

    # Second boot mints the same id (a lost seed race), so the append
    # conflicts; the address now resolves to the live row, so the seeder
    # returns the resolved id rather than the doomed mint.
    racing = _MissThenHitLookup(resolved_id=resolved_id, name=name)
    second = await seed_enclosures(dataclasses.replace(kernel, enclosure_lookup=racing))
    assert second[name] == resolved_id


@pytest.mark.unit
async def test_seed_enclosure_concurrency_falls_back_to_minted_id() -> None:
    name = "hutch-race-fallback"
    minted_id = uuid4()
    kernel = make_inmemory_kernel(
        settings=Settings(app_env="test", enclosure_permit_pvs={name: "pvA"}),  # type: ignore[call-arg]
        clock=FakeClock(_T0),
        id_generator=FixedIdGenerator([minted_id, uuid4(), uuid4(), minted_id, uuid4(), uuid4()]),
        authz=AllowAllAuthorize(),
        enclosure_lookup=AlwaysPermittedEnclosureLookup(),
    )

    first = await seed_enclosures(kernel)
    assert first[name] == minted_id

    # Second boot: the stub resolves nothing on the pre-check and again on
    # the post-conflict retry, so the seeder falls back to the minted id.
    second = await seed_enclosures(kernel)
    assert second[name] == minted_id


class _MissThenHitLookup:
    """`lookup_by_name` misses on the pre-check, then resolves on the retry."""

    def __init__(self, *, resolved_id: UUID, name: str) -> None:
        self._calls = 0
        self._row = EnclosureLookupResult(
            enclosure_id=resolved_id,
            name=name,
            permit_status="Unknown",
            lifecycle="Active",
            observed_at=None,
            source_kind=None,
            source_id=None,
        )

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        return None

    async def find_by_ids(self, *, enclosure_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        return []

    async def lookup_by_name(
        self, *, facility_code: str, name: str
    ) -> EnclosureLookupResult | None:
        self._calls += 1
        return None if self._calls == 1 else self._row
