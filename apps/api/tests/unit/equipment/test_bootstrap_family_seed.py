"""Unit tests for the Equipment BC's Family bootstrap seed."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import bootstrap_families
from cora.equipment.aggregates.family import SEED_FAMILIES, load_family
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    # 1 correlation_id + 1 event_id per seed family per call; two calls in
    # the idempotency test. 44 families -> keep a generous buffer.
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=FixedIdGenerator(
            [UUID(f"01900000-0000-7000-8000-{i:012x}") for i in range(1, 256)]
        ),
        authz=AllowAllAuthorize(),
    )


async def test_bootstrap_seeds_all_seed_families() -> None:
    kernel = _kernel()
    await bootstrap_families(kernel)

    for seed_family in SEED_FAMILIES:
        loaded = await load_family(kernel.event_store, seed_family.id)
        assert loaded is not None
        assert loaded.id == seed_family.id
        assert loaded.name == seed_family.name
        assert loaded.affordances == seed_family.affordances
        assert loaded.presents_as == seed_family.presents_as


async def test_bootstrap_seeds_pinned_deterministic_ids() -> None:
    """Federation-portable: each Family's uuid5 id is its stream id.

    A family that presents Roles seeds genesis + one FamilyPresentsAsAdded
    per Role in one append, so the stream length is 1 + len(presents_as).
    """
    kernel = _kernel()
    await bootstrap_families(kernel)

    for seed_family in SEED_FAMILIES:
        events, version = await kernel.event_store.load("Family", seed_family.id)
        expected_len = 1 + len(seed_family.presents_as)
        assert version == expected_len
        assert len(events) == expected_len
        assert events[0].event_type == "FamilyDefined"
        for presents_event in events[1:]:
            assert presents_event.event_type == "FamilyPresentsAsAdded"


async def test_bootstrap_is_idempotent_across_calls() -> None:
    """A repeated seed call (every app boot) MUST NOT raise or duplicate."""
    kernel = _kernel()
    await bootstrap_families(kernel)
    await bootstrap_families(kernel)

    for seed_family in SEED_FAMILIES:
        _events, version = await kernel.event_store.load("Family", seed_family.id)
        assert version == 1 + len(seed_family.presents_as)


async def test_bootstrap_stamps_system_principal_id() -> None:
    """The seed-emitted events carry principal_id=SYSTEM_PRINCIPAL_ID."""
    kernel = _kernel()
    await bootstrap_families(kernel)
    camera = next(f for f in SEED_FAMILIES if f.name.value == "Camera")
    events, _version = await kernel.event_store.load("Family", camera.id)
    assert events[0].principal_id == SYSTEM_PRINCIPAL_ID
