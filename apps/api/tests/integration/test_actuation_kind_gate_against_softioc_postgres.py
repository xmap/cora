"""End-to-end proof that the ActuationKind provenance gate fires.

The whole point of the gate: data produced by conducting a Procedure
against a SIMULATOR can never be promoted to Production, while data from
real hardware can. This test drives that end to end against real Postgres
and the real soft-IOC subprocess.

The locked trap (see [[project_actuation_kind_stage1_design]]): a soft IOC
speaks real Channel Access through the production `EpicsCaControlPort`, so
"simulated" can NOT be inferred from the transport literal. It is a
DECLARED per-route property (`ControlPortRoute.is_simulated` /
`ControlPortRegistry.register(..., is_simulated=True)`). This test routes
the SAME real `EpicsCaControlPort` two ways -- once declared simulated,
once declared physical -- and proves the gate keys off the declaration,
not the wire.

Flow per case:
  conduct a setpoint over the routed port
    -> Conductor observes ActuationKind from the route declaration
    -> records it on the Procedure terminal event (ProcedureCompleted)
  register a Dataset naming that producing Procedure
    -> register_dataset DERIVES producing_actuation_kind from the loaded
       Procedure server-side (never a caller input)
  promote the Dataset
    -> Simulated / Hybrid origin REJECTS (DatasetCannotPromoteError)
    -> Physical origin SUCCEEDS

The pure register -> fold -> promote chain is pinned in
`tests/unit/test_actuation_kind_gate_seam.py`; the Conductor's kind
production is pinned in `tests/unit/operation/test_conductor.py`. This
file pins that the two halves compose through real adapters.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.aggregates.dataset import DatasetCannotPromoteError
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.promote_dataset import bind as bind_promote_dataset
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.conductor import Conductor, SetpointStep
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.start_procedure import bind as bind_start
from cora.operation.ports.control_port import ActuationKind
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000020d0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020d00aa")
_GOOD_SHA256 = "a" * 64


async def _seed_defined_procedure(event_store: object, procedure_id: UUID) -> None:
    """Seed a single ProcedureRegistered so the Procedure exists in Defined."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM alignment rehearsal",
        kind="alignment",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    stored = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=uuid4(),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await event_store.append(  # type: ignore[attr-defined]
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[stored],
    )


def _conductor(deps: object, db_pool: asyncpg.Pool, control_port: object) -> Conductor:
    step_store = PostgresActivityStore(db_pool)
    return Conductor(
        control_port=control_port,  # type: ignore[arg-type]
        append_step=bind_append(deps, step_store=step_store),  # type: ignore[arg-type]
        clock=deps.clock,  # type: ignore[attr-defined]
        id_generator=deps.id_generator,  # type: ignore[attr-defined]
        start_procedure=bind_start(deps),  # type: ignore[arg-type]
        complete_procedure=bind_complete(deps),  # type: ignore[arg-type]
        abort_procedure=bind_abort(deps),  # type: ignore[arg-type]
    )


@pytest.mark.integration
async def test_simulated_route_conduct_yields_non_promotable_dataset(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """A conduct over a route DECLARED simulated (but speaking real CA to the
    soft IOC) produces a Dataset that promote_dataset refuses to promote."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0100")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    await _seed_defined_procedure(deps.event_store, procedure_id)

    inner = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, inner, is_simulated=True)
    conductor = _conductor(deps, db_pool, registry)
    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(SetpointStep(address=f"{softioc}double_value", value=7.5, verify=True),),
        )
    finally:
        await inner.aclose()

    assert result.succeeded is True
    # Declared simulated wins over the real-CA transport.
    assert result.actuation_kind is ActuationKind.SIMULATED

    # The kind is now on the Procedure terminal state (the gate carrier).
    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.actuation_kind == "Simulated"

    # register_dataset derives the kind server-side from the producing Procedure.
    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="rehearsal recon",
            uri="file:///data/rehearsal/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            producing_procedure_id=procedure_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    dataset_events, _ = await deps.event_store.load("Dataset", dataset_id)
    assert dataset_events[0].payload["producing_actuation_kind"] == "Simulated"

    # The gate fires: simulator-origin data cannot be promoted to Production.
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        await bind_promote_dataset(deps)(
            PromoteDataset(dataset_id=dataset_id, reason="attempting to publish rehearsal data"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "Simulated" in exc_info.value.reason


@pytest.mark.integration
async def test_physical_route_conduct_yields_promotable_dataset(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """The same real EpicsCaControlPort, declared physical, produces a Dataset
    that promotes successfully (the gate permits Physical origin)."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0200")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    await _seed_defined_procedure(deps.event_store, procedure_id)

    inner = EpicsCaControlPort()
    registry = ControlPortRegistry()
    registry.register(softioc, inner, is_simulated=False)
    conductor = _conductor(deps, db_pool, registry)
    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(SetpointStep(address=f"{softioc}double_value", value=3.0, verify=True),),
        )
    finally:
        await inner.aclose()

    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.PHYSICAL

    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.actuation_kind == "Physical"

    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="real recon",
            uri="file:///data/real/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            producing_procedure_id=procedure_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Physical-origin data promotes (no producing_run_id, so the Run-Completed
    # guard is inactive; the actuation guard permits Physical).
    await bind_promote_dataset(deps)(
        PromoteDataset(dataset_id=dataset_id, reason="real-hardware data, keeper-grade"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    dataset_events, _ = await deps.event_store.load("Dataset", dataset_id)
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered", "DatasetPromoted"]


@pytest.mark.integration
async def test_no_routing_table_conduct_yields_non_promotable_dataset(
    db_pool: asyncpg.Pool,
) -> None:
    """item-6 leak-closer, end to end: a conduct against a bare control port
    with NO routing table observes no kind (None). The Procedure still
    completes (terminal), so registration is allowed, but the Dataset's
    provenance is unproven -> promote refuses it. No soft IOC needed: this is
    the opt-out / unprovable path, not a real-adapter path."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0400")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    await _seed_defined_procedure(deps.event_store, procedure_id)

    bare = InMemoryControlPort()  # no ControlPortRegistry -> no route_is_simulated
    bare.simulate_connect("dev:motor")
    conductor = _conductor(deps, db_pool, bare)
    result = await conductor.conduct(
        procedure_id=procedure_id,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        steps=(SetpointStep(address="dev:motor", value=1.0),),
    )
    assert result.succeeded is True
    assert result.actuation_kind is None

    procedure = await load_procedure(deps.event_store, procedure_id)
    assert procedure is not None
    assert procedure.status.is_terminal
    assert procedure.actuation_kind is None

    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="unprovable recon",
            uri="file:///data/unprovable/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            producing_procedure_id=procedure_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        await bind_promote_dataset(deps)(
            PromoteDataset(dataset_id=dataset_id, reason="attempting to publish unprovable data"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "unproven" in exc_info.value.reason


@pytest.mark.integration
async def test_hybrid_route_conduct_yields_non_promotable_dataset(
    db_pool: asyncpg.Pool,
    softioc: str,
) -> None:
    """One conduct touching both a simulated and a physical sub-route records
    Hybrid, which is also disqualifying for promotion."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020d0300")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(50)])
    await _seed_defined_procedure(deps.event_store, procedure_id)

    inner = EpicsCaControlPort()
    registry = ControlPortRegistry()
    # Longest-prefix match: the double_value PV is declared simulated, the
    # long_value PV physical. Both speak CA to the same soft IOC.
    registry.register(f"{softioc}double_value", inner, is_simulated=True)
    registry.register(f"{softioc}long_value", inner, is_simulated=False)
    conductor = _conductor(deps, db_pool, registry)
    try:
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                SetpointStep(address=f"{softioc}double_value", value=1.0),
                SetpointStep(address=f"{softioc}long_value", value=2),
            ),
        )
    finally:
        await inner.aclose()

    assert result.succeeded is True
    assert result.actuation_kind is ActuationKind.HYBRID

    dataset_id = await bind_register_dataset(deps)(
        RegisterDataset(
            name="hybrid recon",
            uri="file:///data/hybrid/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            producing_procedure_id=procedure_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(DatasetCannotPromoteError):
        await bind_promote_dataset(deps)(
            PromoteDataset(dataset_id=dataset_id, reason="attempting to publish hybrid data"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
