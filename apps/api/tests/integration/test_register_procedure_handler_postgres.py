"""End-to-end integration test: register_procedure against real Postgres.

Pinned: ProcedureRegistered round-trips through jsonb (target_asset_ids
as a sorted list, parent_run_id as str|None) and the Procedure
folds back to the expected state.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    ProcedureStatus,
    fold,
    from_stored,
)
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityDefined,
    CapabilityName,
    ExecutorShape,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_register_procedure_persists_event_to_postgres_with_target_assets(
    db_pool: asyncpg.Pool,
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-0000000c0a01")
    event_id = UUID("01900000-0000-7000-8000-0000000c0a02")
    asset1 = UUID("01900000-0000-7000-8000-0000000c0a11")
    asset2 = UUID("01900000-0000-7000-8000-0000000c0a12")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_id, event_id])

    returned_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({asset2, asset1}),  # unsorted input
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == procedure_id

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ProcedureRegistered"
    assert stored.payload == {
        "procedure_id": str(procedure_id),
        "name": "2-BM rotation-axis alignment",
        "kind": "alignment",
        # Sorted by UUID string form (deterministic).
        "target_asset_ids": sorted([str(asset1), str(asset2)]),
        "parent_run_id": None,
        "capability_id": None,
        "recipe_id": None,
        "max_consecutive_unconverged_iterations": None,
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == event_id
    assert stored.principal_id == _PRINCIPAL_ID
    assert stored.metadata == {"command": "RegisterProcedure"}

    # Round-trip back through fold to confirm state shape.
    rebuilt_events = [from_stored(s) for s in events]
    state = fold(rebuilt_events)
    assert state is not None
    assert state.id == procedure_id
    assert state.kind == "alignment"
    assert state.target_asset_ids == frozenset({asset1, asset2})
    assert state.parent_run_id is None
    assert state.status is ProcedureStatus.DEFINED


@pytest.mark.integration
async def test_register_procedure_persists_phase_of_run_with_parent_run_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Phase-of-Run procedure: parent_run_id round-trips as str through
    jsonb and rebuilds as UUID in state."""
    procedure_id = UUID("01900000-0000-7000-8000-0000000c0a21")
    event_id = UUID("01900000-0000-7000-8000-0000000c0a22")
    parent_run = UUID("01900000-0000-7000-8000-0000000c0a23")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_id, event_id])

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="Mid-run alignment",
            kind="alignment",
            parent_run_id=parent_run,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    assert events[0].payload["parent_run_id"] == str(parent_run)
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.parent_run_id == parent_run


@pytest.mark.integration
async def test_register_procedure_persists_facility_envelope_with_empty_target_assets(
    db_pool: asyncpg.Pool,
) -> None:
    """Facility-envelope procedures (beam-mode change) have empty
    target_asset_ids; both empty list and None parent_run_id round-
    trip through jsonb cleanly."""
    procedure_id = UUID("01900000-0000-7000-8000-0000000c0a31")
    event_id = UUID("01900000-0000-7000-8000-0000000c0a32")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_id, event_id])

    await bind_register_procedure(deps)(
        RegisterProcedure(name="Beam-mode change to white", kind="beam_mode_change"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    assert events[0].payload["target_asset_ids"] == []
    assert events[0].payload["parent_run_id"] is None


@pytest.mark.integration
async def test_register_procedure_persists_bound_capability_id_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """PG round-trip: when capability_id is set,
    the handler loads the bound Capability from PG, validates
    `ExecutorShape.PROCEDURE` is declared, and persists the
    capability_id into the ProcedureRegistered payload as a UUID
    string. Mirrors test_define_method_persists_bound_capability_id_to_postgres."""
    procedure_id = UUID("01900000-0000-7000-8000-0000000c0a41")
    event_id = UUID("01900000-0000-7000-8000-0000000c0a42")
    capability_id = UUID("01900000-0000-7000-8000-0000000c00d3")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_id, event_id])

    # Seed a Procedure-shaped Capability via the event-store API.
    cap_event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.x").value,
        name=CapabilityName("X").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.PROCEDURE}),
        occurred_at=_NOW,
    )

    await deps.event_store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=capability_event_type_name(cap_event),
                payload=capability_to_payload(cap_event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefineCapability",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    await bind_register_procedure(deps)(
        RegisterProcedure(name="Hexapod reboot", kind="recovery", capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Procedure", procedure_id)
    assert events[0].payload["capability_id"] == str(capability_id)
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.capability_id == capability_id
