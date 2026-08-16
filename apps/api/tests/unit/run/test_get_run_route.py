"""Unit tests for `get_run`'s route-level capture-path DTO mapping
(slice 13).

Calls `route.get_runs` directly (a plain async function; FastAPI's
`Depends`/`Annotated` wrapping does not prevent direct invocation in a
unit test), seeding a real `Run` via `InMemoryEventStore` so
`run.external_refs` is genuinely folded, not faked. Mirrors
`test_get_run_handler.py`'s `_seed_run` shape.

`capture_code` / `observed_capture_path` resolution itself happens
inside `get_run`'s `Handler` (`RunView`, per `handler.py`'s own
docstring), not at this layer: `get_run.bind(deps, capture_path_store=...,
experiment_identity_store=...)` does the vault touch, and this route
only destructures the already-composed `RunView` into its wire DTO.
These tests pin THAT destructuring for the three outcomes -- witnessed
+ vault row -> real path; witnessed + no row -> tombstone; conducted ->
both fields `None` -- by building the handler with a store pre-seeded
(or not) before calling the route. Also covers the slice 14a
proposal/ESAF/ESAF-DOI fields' destructuring the same way.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    UNOBSERVED_CAPTURE_PATH,
    InMemoryCapturePathStore,
    InMemoryExperimentIdentityStore,
)
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features import get_run
from cora.run.features.get_run.route import get_runs
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
_PLAN_ID = UUID("01900000-0000-7000-8000-00000000ff02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run(
    store: InMemoryEventStore,
    run_id: UUID,
    *,
    capture_code: str | None,
    name: str = "witnessed-run",
) -> None:
    external_refs = (
        ({"scheme": "capture-code", "value": capture_code},) if capture_code is not None else ()
    )
    event = RunStarted(
        run_id=run_id,
        name=name,
        plan_id=_PLAN_ID,
        subject_id=None,
        external_refs=external_refs,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


@pytest.mark.unit
async def test_get_run_route_resolves_the_real_path_when_the_vault_has_a_row() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id, capture_code="2bmb-tomoscan")
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    capture_path_store = InMemoryCapturePathStore()
    await capture_path_store.upsert(
        run_id=run_id,
        observed_path="/data/2026-01-Smith-12345/scan_001.h5",
        observed_at=_NOW,
        created_at=_NOW,
    )
    handler = get_run.bind(
        deps,
        capture_path_store=capture_path_store,
        experiment_identity_store=InMemoryExperimentIdentityStore(),
    )

    response = await get_runs(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.capture_code == "2bmb-tomoscan"
    assert response.observed_capture_path == "/data/2026-01-Smith-12345/scan_001.h5"


@pytest.mark.unit
async def test_get_run_route_resolves_the_experiment_identity_when_the_vault_has_a_row() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id, capture_code="2bmb-tomoscan")
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    experiment_identity_store = InMemoryExperimentIdentityStore()
    await experiment_identity_store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_NOW,
        esaf_number="67890",
        esaf_number_observed_at=_NOW,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_NOW,
    )
    handler = get_run.bind(
        deps,
        capture_path_store=InMemoryCapturePathStore(),
        experiment_identity_store=experiment_identity_store,
    )

    response = await get_runs(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.proposal_number == "12345"
    assert response.proposal_number_observed_at == _NOW
    assert response.esaf_number == "67890"
    assert response.esaf_doi_number is None


@pytest.mark.unit
async def test_get_run_route_experiment_identity_is_none_when_the_vault_has_no_row() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id, capture_code="2bmb-tomoscan-3")
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    handler = get_run.bind(
        deps,
        capture_path_store=InMemoryCapturePathStore(),
        experiment_identity_store=InMemoryExperimentIdentityStore(),
    )

    response = await get_runs(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.proposal_number is None
    assert response.esaf_number is None
    assert response.esaf_doi_number is None


@pytest.mark.unit
async def test_get_run_route_resolves_the_tombstone_when_the_vault_has_no_row() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id, capture_code="2bmb-tomoscan-2")
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    handler = get_run.bind(
        deps,
        capture_path_store=InMemoryCapturePathStore(),
        experiment_identity_store=InMemoryExperimentIdentityStore(),
    )

    response = await get_runs(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.capture_code == "2bmb-tomoscan-2"
    assert response.observed_capture_path == UNOBSERVED_CAPTURE_PATH


@pytest.mark.unit
async def test_get_run_route_a_conducted_run_has_no_capture_code_and_no_tombstone() -> None:
    """Never touches the vault at all when there's no capture_code:
    'not applicable' (bare None) is a different fact from 'expected but
    missing' (the tombstone)."""
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_run(store, run_id, capture_code=None, name="conducted-run")
    deps = build_deps(ids=[run_id], now=_NOW, event_store=store)
    handler = get_run.bind(
        deps,
        capture_path_store=InMemoryCapturePathStore(),
        experiment_identity_store=InMemoryExperimentIdentityStore(),
    )

    response = await get_runs(
        run_id,
        handler,
        _CORRELATION_ID,
        _PRINCIPAL_ID,
        NIL_SENTINEL_ID,
    )

    assert response.capture_code is None
    assert response.observed_capture_path is None


@pytest.mark.unit
async def test_get_run_route_raises_404_for_unknown_run() -> None:
    from fastapi import HTTPException

    deps = build_deps(ids=[uuid4()], now=_NOW)
    handler = get_run.bind(
        deps,
        capture_path_store=InMemoryCapturePathStore(),
        experiment_identity_store=InMemoryExperimentIdentityStore(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_runs(
            uuid4(),
            handler,
            _CORRELATION_ID,
            _PRINCIPAL_ID,
            NIL_SENTINEL_ID,
        )
    assert exc_info.value.status_code == 404
