"""End-to-end: `list_model_ids` against `proj_equipment_model_summary`.

Pins the two SQL-tier contracts the read function carries:

  - Deprecated Models are excluded (`WHERE status <> 'Deprecated'`),
    so future cross-BC candidate-enumeration callers do not surface
    Deprecated Models as bindable sources.
  - Returned ids are sorted by `model_id::text` ascending, so the
    list is deterministic across calls regardless of insert order.

Plus the empty-projection arm: zero rows in the summary projection
yields `[]`, matching the `pool=None` short-circuit pinned at unit
tier in `tests/unit/equipment/test_list_model_ids.py`.

Sibling Kernel + pg_pool fixture pattern from
`test_postgres_model_summary_projection.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    list_model_ids,
)
from cora.equipment.features import (
    define_family,
    define_model,
    deprecate_model,
)
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.deprecate_model import DeprecateModel
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_list_model_ids_excludes_deprecated_models(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed 3 Models, deprecate 1, drain: `list_model_ids` returns the
    2 non-Deprecated ids in `model_id::text`-sorted ascending order.
    Pins the `WHERE status <> 'Deprecated'` filter."""
    family_id = UUID("01900000-0000-7000-8000-0000000cd001")
    family_event_id = UUID("01900000-0000-7000-8000-0000000cd00e")
    model_a_id = UUID("01900000-0000-7000-8000-0000000cd0a1")
    model_a_event_id = UUID("01900000-0000-7000-8000-0000000cd0ae")
    model_b_id = UUID("01900000-0000-7000-8000-0000000cd0a2")
    model_b_event_id = UUID("01900000-0000-7000-8000-0000000cd0af")
    model_c_id = UUID("01900000-0000-7000-8000-0000000cd0a3")
    model_c_event_id = UUID("01900000-0000-7000-8000-0000000cd0b0")
    deprecate_event_id = UUID("01900000-0000-7000-8000-0000000cd0b1")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            model_a_id,
            model_a_event_id,
            model_b_id,
            model_b_event_id,
            model_c_id,
            model_c_event_id,
            deprecate_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    for name, part_number in (
        ("Aerotech ANT130-L", "ANT130-L"),
        ("Aerotech ANT130-LZS", "ANT130-LZS"),
        ("Aerotech ANT95-L", "ANT95-L"),
    ):
        await define_model.bind(deps)(
            DefineModel(
                name=name,
                manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
                part_number=part_number,
                declared_families=frozenset({family_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=model_b_id, reason="superseded"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    ids = await list_model_ids(db_pool)
    expected = sorted([model_a_id, model_c_id], key=lambda u: str(u))
    assert ids == expected


@pytest.mark.integration
async def test_list_model_ids_returns_models_in_canonical_sort_order(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed 3 Models, drain: `list_model_ids` returns ids sorted by
    `model_id::text` ascending regardless of insert order. Pins the
    `ORDER BY model_id::text` clause."""
    family_id = UUID("01900000-0000-7000-8000-0000000cd101")
    family_event_id = UUID("01900000-0000-7000-8000-0000000cd10e")
    # Insert order (c, a, b) differs from text-sort order (a, b, c)
    # so an accidental "natural insertion order" implementation would
    # not pass.
    model_a_id = UUID("01900000-0000-7000-8000-0000000cd1a1")
    model_a_event_id = UUID("01900000-0000-7000-8000-0000000cd1ae")
    model_b_id = UUID("01900000-0000-7000-8000-0000000cd1a2")
    model_b_event_id = UUID("01900000-0000-7000-8000-0000000cd1af")
    model_c_id = UUID("01900000-0000-7000-8000-0000000cd1a3")
    model_c_event_id = UUID("01900000-0000-7000-8000-0000000cd1b0")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_id,
            family_event_id,
            model_c_id,
            model_c_event_id,
            model_a_id,
            model_a_event_id,
            model_b_id,
            model_b_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    for name, part_number in (
        ("Aerotech ANT95-L", "ANT95-L"),
        ("Aerotech ANT130-L", "ANT130-L"),
        ("Aerotech ANT130-LZS", "ANT130-LZS"),
    ):
        await define_model.bind(deps)(
            DefineModel(
                name=name,
                manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
                part_number=part_number,
                declared_families=frozenset({family_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await drain_equipment_projections(db_pool)

    ids = await list_model_ids(db_pool)
    expected = sorted([model_a_id, model_b_id, model_c_id], key=lambda u: str(u))
    assert ids == expected


@pytest.mark.integration
async def test_list_model_ids_returns_empty_when_no_models(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty projection: `list_model_ids` returns `[]`. Matches the
    `pool=None` short-circuit pinned at unit tier."""
    assert await list_model_ids(db_pool) == []
