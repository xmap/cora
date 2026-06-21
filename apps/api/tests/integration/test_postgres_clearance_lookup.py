"""Integration tests for `PostgresClearanceLookup` against a real Postgres.

Pins the cross-stream query contract under the real Safety projection:
seeds clearances via `register_clearance` + transition handlers, drains
the projection worker, then queries through the adapter and verifies
the result matches the seeded clearances.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceLookup, PostgresClearanceTemplateLookup
from cora.safety.aggregates.clearance import (
    AssetBinding,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance_template import ClearanceTemplateId
from cora.safety.features import (
    activate_clearance,
    activate_clearance_template,
    append_clearance_review_step,
    approve_clearance,
    define_clearance_template,
    register_clearance,
    start_clearance_review,
    submit_clearance,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.activate_clearance_template import ActivateClearanceTemplate
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.submit_clearance import SubmitClearance
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000b001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000b002")
_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "ESAF"


async def _seed_active_template(db_pool: asyncpg.Pool) -> UUID:
    """Define + Activate a ClearanceTemplate in the self-Facility, drain
    Safety projections so PostgresClearanceTemplateLookup can resolve it,
    return its deterministic stream id."""
    define_event_id = uuid4()
    activate_event_id = uuid4()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[define_event_id, activate_event_id],
    )
    template_id = await define_clearance_template.bind(deps)(
        DefineClearanceTemplate(
            code=_TEMPLATE_CODE,
            title="Test ESAF Template",
            facility_code=_FACILITY_CODE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_clearance_template.bind(deps)(
        ActivateClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_safety(db_pool)
    return template_id


async def _seed_active_clearance(
    deps,  # type: ignore[no-untyped-def]
    *,
    template_id: UUID,
    bindings: frozenset,  # type: ignore[type-arg]
) -> UUID:
    """Register + walk a clearance to Active, return its id."""
    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code=_FACILITY_CODE,
            title="Pilot",
            bindings=bindings,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_clearance_review.bind(deps)(
        StartClearanceReview(clearance_id=cid, first_reviewer_role="ESH"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await append_clearance_review_step.bind(deps)(
        AppendClearanceReviewStep(
            clearance_id=cid,
            step_index=0,
            role="ESH",
            actor_id=_PRINCIPAL_ID,
            decision="Approved",
            decided_at=_NOW,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await approve_clearance.bind(deps)(
        ApproveClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_clearance.bind(deps)(
        ActivateClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return cid


def _build_deps_with_pg_template_lookup(db_pool: asyncpg.Pool, *, ids: list[UUID]):  # type: ignore[no-untyped-def]
    """Build integration deps with PostgresClearanceTemplateLookup so the
    register_clearance handler resolves the seeded template against the
    real Postgres projection."""
    return replace(
        build_postgres_deps(db_pool, now=_NOW, ids=ids),
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
    )


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_finds_active_clearance_bound_to_run_id(db_pool: asyncpg.Pool) -> None:
    template_id = await _seed_active_template(db_pool)
    deps = _build_deps_with_pg_template_lookup(db_pool, ids=[uuid4() for _ in range(30)])
    run_id = uuid4()
    cid = await _seed_active_clearance(
        deps, template_id=template_id, bindings=frozenset({RunBinding(run_id=run_id)})
    )
    await _drain_safety(db_pool)

    lookup = PostgresClearanceLookup(db_pool)
    results = await lookup.find_covering(
        run_id=run_id,
        subject_id=None,
        asset_ids=frozenset(),
    )
    assert len(results) == 1
    assert results[0].clearance_id == cid
    assert results[0].status == "Active"
    assert results[0].template_id == template_id
    assert results[0].template_code == _TEMPLATE_CODE


@pytest.mark.integration
async def test_finds_active_clearance_bound_to_subject_id(db_pool: asyncpg.Pool) -> None:
    template_id = await _seed_active_template(db_pool)
    deps = _build_deps_with_pg_template_lookup(db_pool, ids=[uuid4() for _ in range(30)])
    subject_id = uuid4()
    cid = await _seed_active_clearance(
        deps,
        template_id=template_id,
        bindings=frozenset({SubjectBinding(subject_id=subject_id)}),
    )
    await _drain_safety(db_pool)

    lookup = PostgresClearanceLookup(db_pool)
    results = await lookup.find_covering(
        run_id=uuid4(),  # unrelated run id
        subject_id=subject_id,
        asset_ids=frozenset(),
    )
    assert len(results) == 1
    assert results[0].clearance_id == cid


@pytest.mark.integration
async def test_finds_active_clearance_bound_to_any_asset_id(db_pool: asyncpg.Pool) -> None:
    """Asset coverage uses the && (overlap) operator: if ANY of the
    Run's asset_ids matches the Clearance's asset_binding_ids, the
    clearance is returned."""
    template_id = await _seed_active_template(db_pool)
    deps = _build_deps_with_pg_template_lookup(db_pool, ids=[uuid4() for _ in range(30)])
    asset_id_a = uuid4()
    asset_id_b = uuid4()
    cid = await _seed_active_clearance(
        deps,
        template_id=template_id,
        bindings=frozenset({AssetBinding(asset_id=asset_id_a)}),
    )
    await _drain_safety(db_pool)

    lookup = PostgresClearanceLookup(db_pool)
    # Run uses both asset_a (overlap with clearance) and asset_b (unrelated).
    results = await lookup.find_covering(
        run_id=uuid4(),
        subject_id=None,
        asset_ids=frozenset({asset_id_a, asset_id_b}),
    )
    assert len(results) == 1
    assert results[0].clearance_id == cid


@pytest.mark.integration
async def test_returns_empty_when_no_clearance_references_the_scope(
    db_pool: asyncpg.Pool,
) -> None:
    """A Run with no matching clearance binding gets an empty list."""
    template_id = await _seed_active_template(db_pool)
    deps = _build_deps_with_pg_template_lookup(db_pool, ids=[uuid4() for _ in range(30)])
    # Seed a clearance bound to an UNRELATED Run.
    await _seed_active_clearance(
        deps, template_id=template_id, bindings=frozenset({RunBinding(run_id=uuid4())})
    )
    await _drain_safety(db_pool)

    lookup = PostgresClearanceLookup(db_pool)
    results = await lookup.find_covering(
        run_id=uuid4(),  # different from the seeded clearance's run_id
        subject_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
    )
    assert results == []


@pytest.mark.integration
async def test_returns_non_active_clearances_too(db_pool: asyncpg.Pool) -> None:
    """find_covering returns ALL statuses; the decider partitions
    on Active. Pin this by seeding a Defined (no transitions) clearance."""
    template_id = await _seed_active_template(db_pool)
    deps = _build_deps_with_pg_template_lookup(db_pool, ids=[uuid4() for _ in range(20)])
    run_id = uuid4()
    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code=_FACILITY_CODE,
            title="Stayed in Defined",
            bindings=frozenset({RunBinding(run_id=run_id)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_safety(db_pool)

    lookup = PostgresClearanceLookup(db_pool)
    results = await lookup.find_covering(
        run_id=run_id,
        subject_id=None,
        asset_ids=frozenset(),
    )
    assert len(results) == 1
    assert results[0].clearance_id == cid
    assert results[0].status == "Defined"
