"""Shared helpers for Equipment BC PG integration tests.

The Mount/Frame PG integration test files share an identical
`placement(parent_frame_id)` constructor and projection-drain wrapper;
hoisted here so per-file boilerplate stays short. `seed_installed_asset`
is the install-then-register-fixture choreography helper used by every
Fixture-touching integration test (register_fixture requires every
bound Asset to be currently installed in some Mount).

Per-file helpers that vary (the `_seed_*` family, scenario-specific
fixtures) stay local to each test file. Only the genuinely-identical
shared pieces live here.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.install_asset import InstallAsset
from cora.equipment.features.install_asset import bind as bind_install_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.equipment.features.register_frame import RegisterFrame
from cora.equipment.features.register_frame import bind as bind_register_frame
from cora.equipment.features.register_mount import RegisterMount
from cora.equipment.features.register_mount import bind as bind_register_mount
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

if TYPE_CHECKING:
    from datetime import datetime

    import asyncpg


# Helper-internal principal / correlation ids. They intentionally
# differ from per-test `_PRINCIPAL_ID` / `_CORRELATION_ID` constants:
# tests that need the seeded events to share a principal / correlation
# id with their own commands should run their own setup inline rather
# than call this helper.
_SEED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_SEED_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def placement(parent_frame_id: UUID) -> Placement:
    """A minimal Placement adequate for any slot in PG integration tests.

    Pins the parent_frame_id; everything else is canonical zero / SI_MM_RAD
    so test-side construction stays terse. Tests that need a specific
    pose construct Placement directly rather than calling this helper.
    """
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.1,
        tol_y=0.1,
        tol_z=0.1,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


async def drain_equipment_projections(
    pool: asyncpg.Pool,
    *,
    deadline_seconds: float = 2.0,
) -> None:
    """Construct a fresh ProjectionRegistry, register Equipment's projections,
    and drain pending events to the projection workers' bookmarks.
    """
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(pool, registry, deadline_seconds=deadline_seconds)


async def seed_installed_asset(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    slot_code: str,
    asset_name: str | None = None,
    asset_level: AssetLevel = AssetLevel.DEVICE,
) -> tuple[UUID, UUID, UUID]:
    """Register Frame + Mount + Asset, activate Asset, install Asset; drain.

    Returns (frame_id, mount_id, asset_id). Drains projections after
    activate (so install_asset's preconditions pass) and after install
    (so the asset_location projection row is visible to downstream
    register_fixture calls that need to pass the orphan guard).

    Shared by every register_fixture / attach_asset_to_fixture /
    detach_asset_from_fixture integration test that needs a real
    Fixture-able Asset (register_fixture rejects bindings whose Asset
    is not currently installed in some Mount). Tests that need
    fine-grained control over the individual ids (specific
    FixedIdGenerator values) keep their own inline setup.

    The helper uses its own per-call `build_postgres_deps` so it
    consumes ids from a fresh FixedIdGenerator each time; the caller's
    outer deps's id pool only needs to budget for the work after
    seeding (define_family, add_asset_family, define_assembly,
    register_fixture, etc.).
    """
    frame_id, mount_id, asset_id = uuid4(), uuid4(), uuid4()
    asset_name = asset_name if asset_name is not None else f"specimen-{slot_code}"

    deps = build_postgres_deps(pool, now=now, ids=[frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(name=f"frame-{slot_code}", parent_frame_id=None, placement=None),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=now, ids=[mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=now, ids=[asset_id, uuid4()])
    await bind_register_asset(deps)(
        RegisterAsset(name=asset_name, level=asset_level, parent_id=uuid4()),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )
    deps = build_postgres_deps(pool, now=now, ids=[uuid4()])
    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    deps = build_postgres_deps(pool, now=now, ids=[uuid4()])
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    return frame_id, mount_id, asset_id


async def install_existing_asset_into_fresh_mount(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    asset_id: UUID,
    slot_code: str,
) -> tuple[UUID, UUID]:
    """Activate the given pre-registered Asset, then register a fresh
    Frame + Mount and install the Asset; drain. Returns (frame_id,
    mount_id).

    Companion to `seed_installed_asset`: use this when the test
    already needed to register the Asset itself (e.g., to bind a
    model_id or seed an owner) and now needs to satisfy the INV-4
    install-required guard before calling `register_fixture`.

    Activates the Asset because `install_asset` rejects non-Active
    Assets (`AssetNotInstallableError`). Tests that have already
    activated the Asset should not call this helper; activate is a
    strict-not-idempotent transition.
    """
    frame_id, mount_id = uuid4(), uuid4()

    deps = build_postgres_deps(pool, now=now, ids=[frame_id, uuid4()])
    await bind_register_frame(deps)(
        RegisterFrame(name=f"frame-{slot_code}", parent_frame_id=None, placement=None),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=now, ids=[mount_id, uuid4()])
    await bind_register_mount(deps)(
        RegisterMount(
            slot_code=slot_code,
            parent_mount_id=None,
            placement=placement(frame_id),
            drawing=None,
        ),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )

    deps = build_postgres_deps(pool, now=now, ids=[uuid4()])
    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=asset_id),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    deps = build_postgres_deps(pool, now=now, ids=[uuid4()])
    await bind_install_asset(deps)(
        InstallAsset(mount_id=mount_id, asset_id=asset_id),
        principal_id=_SEED_PRINCIPAL_ID,
        correlation_id=_SEED_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)

    return frame_id, mount_id


__all__ = [
    "drain_equipment_projections",
    "install_existing_asset_into_fresh_mount",
    "placement",
    "seed_installed_asset",
]
