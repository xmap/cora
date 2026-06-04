"""End-to-end integration test: define_method handler against real Postgres.

Pinned: needed_family_ids round-trips through jsonb as a sorted
list of UUID strings. The frozenset[UUID] domain shape converts
to list[UUID] at the events layer (see PolicyDefined precedent in
Trust 3c).

DefineMethod.capability_id is REQUIRED; every
test seeds a Capability stream via `seed_capability_postgres` before
invoking the handler.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_method_persists_event_to_postgres_with_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    method_id = UUID("01900000-0000-7000-8000-00000056ed01")
    event_id = UUID("01900000-0000-7000-8000-00000056ed0e")
    capability_id = UUID("01900000-0000-7000-8000-00000056ed0c")
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])
    await seed_capability_postgres(
        deps.event_store, capability_id, shapes=frozenset({ExecutorShape.METHOD})
    )

    returned_id = await define_method.bind(deps)(
        DefineMethod(
            name="XRF Fly Mapping",
            capability_id=capability_id,
            needed_family_ids=frozenset({cap2, cap1}),  # unsorted input
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == method_id

    events, version = await deps.event_store.load("Method", method_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "MethodDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "method_id": str(method_id),
        "name": "XRF Fly Mapping",
        # Sorted by UUID string form (deterministic).
        "needed_family_ids": sorted([str(cap1), str(cap2)]),
        # needed_supplies. Pinned by tests/unit/recipe/test_method_needed_supplies.py.
        "needed_supplies": [],
        # MethodDefined.payload carries it as a UUID string.
        "capability_id": str(capability_id),
        # needed_assembly_ids. Pinned by tests/unit/recipe/test_method_needed_assembly_ids.py.
        "needed_assembly_ids": [],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefineMethod"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_method_persists_procedural_method_with_empty_capabilities(
    db_pool: asyncpg.Pool,
) -> None:
    """Procedural Method (no equipment requirement) round-trips
    through jsonb with `needed_family_ids = []`."""
    method_id = UUID("01900000-0000-7000-8000-00000056ee01")
    event_id = UUID("01900000-0000-7000-8000-00000056ee0e")
    capability_id = UUID("01900000-0000-7000-8000-00000056ee0c")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])
    await seed_capability_postgres(
        deps.event_store, capability_id, shapes=frozenset({ExecutorShape.METHOD})
    )

    await define_method.bind(deps)(
        DefineMethod(
            name="Sample Cleaning", capability_id=capability_id, needed_family_ids=frozenset()
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["needed_family_ids"] == []


@pytest.mark.integration
async def test_define_method_persists_needed_assembly_ids_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """needed_assembly_ids round-trips through jsonb as a sorted list of
    UUID strings (deterministic for idempotency hashing). Mirrors the
    needed_family_ids pin."""
    method_id = UUID("01900000-0000-7000-8000-00000056ef01")
    event_id = UUID("01900000-0000-7000-8000-00000056ef0e")
    capability_id = UUID("01900000-0000-7000-8000-00000056ef0c")
    asm1 = UUID("01900000-0000-7000-8000-0000a0a0a0a1")
    asm2 = UUID("01900000-0000-7000-8000-0000a0a0a0a2")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])
    await seed_capability_postgres(
        deps.event_store, capability_id, shapes=frozenset({ExecutorShape.METHOD})
    )

    await define_method.bind(deps)(
        DefineMethod(
            name="MCTOptics Tomography",
            capability_id=capability_id,
            needed_family_ids=frozenset(),
            needed_assembly_ids=frozenset({asm2, asm1}),  # unsorted input
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["needed_assembly_ids"] == sorted([str(asm1), str(asm2)])


@pytest.mark.integration
async def test_define_method_persists_bound_capability_id_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """PG round-trip: capability_id is REQUIRED. The
    handler loads the bound Capability from PG, validates
    `ExecutorShape.METHOD` is declared, and persists the resolved
    capability_id into the MethodDefined payload as a UUID string.
    Pinned because the cross-BC capability load uses jsonb-serialized
    executor_shapes via `to_payload` + the round-trip through Postgres."""
    method_id = UUID("01900000-0000-7000-8000-00000056ef01")
    event_id = UUID("01900000-0000-7000-8000-00000056ef0e")
    capability_id = UUID("01900000-0000-7000-8000-00000000c0d2")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[method_id, event_id])
    await seed_capability_postgres(
        deps.event_store, capability_id, shapes=frozenset({ExecutorShape.METHOD})
    )

    await define_method.bind(deps)(
        DefineMethod(name="X", capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Method", method_id)
    assert events[0].payload["capability_id"] == str(capability_id)
