"""Unit tests for the Equipment BC's 5-Role bootstrap seed."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import bootstrap_equipment
from cora.equipment.aggregates.role import (
    SEED_ROLE_CONTROLLER_ID,
    SEED_ROLE_DETECTOR_ID,
    SEED_ROLE_POSITIONER_ID,
    SEED_ROLE_REGULATOR_ID,
    SEED_ROLE_SENSOR_ID,
    SEED_ROLES,
    load_role,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        # 1 correlation_id + 1 event_id per seed role (5); +buffer per call repeat.
        id_generator=FixedIdGenerator(
            [UUID(f"01900000-0000-7000-8000-0000000000{i:02x}") for i in range(1, 64)]
        ),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
async def test_bootstrap_seeds_all_seed_roles() -> None:
    kernel = _kernel()
    await bootstrap_equipment(kernel)

    for seed_role in SEED_ROLES:
        loaded = await load_role(kernel.event_store, seed_role.id)
        assert loaded is not None
        assert loaded.id == seed_role.id
        assert loaded.name == seed_role.name
        assert loaded.docstring == seed_role.docstring
        assert loaded.required_affordances == seed_role.required_affordances
        assert loaded.optional_affordances == seed_role.optional_affordances
        assert loaded.produces == seed_role.produces
        assert loaded.consumes == seed_role.consumes


@pytest.mark.unit
async def test_bootstrap_seeds_pinned_deterministic_ids() -> None:
    """Federation-portable: SEED_ROLE_*_ID values are the stream ids."""
    kernel = _kernel()
    await bootstrap_equipment(kernel)

    for pinned_id in (
        SEED_ROLE_DETECTOR_ID,
        SEED_ROLE_POSITIONER_ID,
        SEED_ROLE_CONTROLLER_ID,
        SEED_ROLE_SENSOR_ID,
        SEED_ROLE_REGULATOR_ID,
    ):
        events, version = await kernel.event_store.load("Role", pinned_id)
        assert version == 1
        assert len(events) == 1
        assert events[0].event_type == "RoleDefined"


@pytest.mark.unit
async def test_bootstrap_is_idempotent_across_calls() -> None:
    """A repeated seed call (on every app boot) MUST NOT raise and
    MUST NOT duplicate any Role row."""
    kernel = _kernel()
    await bootstrap_equipment(kernel)
    await bootstrap_equipment(kernel)

    for seed_role in SEED_ROLES:
        _events, version = await kernel.event_store.load("Role", seed_role.id)
        assert version == 1


@pytest.mark.unit
async def test_bootstrap_stamps_system_principal_id() -> None:
    """The seed-emitted events carry principal_id=SYSTEM_PRINCIPAL_ID."""
    kernel = _kernel()
    await bootstrap_equipment(kernel)
    events, _version = await kernel.event_store.load("Role", SEED_ROLE_DETECTOR_ID)
    assert events[0].principal_id == SYSTEM_PRINCIPAL_ID
