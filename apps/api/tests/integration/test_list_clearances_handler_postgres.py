"""End-to-end integration test: list_clearances + projection round-trip.

Seeds 3 Clearances via register + transition handlers, drains the
projection worker via the integration helper, then queries
list_clearances and verifies:
  - all 3 surface in the projection
  - status filter narrows correctly
  - facility_code filter narrows correctly
  - subject-binding filter narrows correctly via UUID[] GIN
  - cursor pagination produces disjoint pages whose union is complete
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety._projections import register_safety_projections
from cora.safety.aggregates.clearance import (
    SubjectBinding,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import (
    list_clearances,
    register_clearance,
    submit_clearance,
)
from cora.safety.features.list_clearances import ListClearances
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.submit_clearance import SubmitClearance
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_list_clearances_full_filter_matrix_postgres(db_pool: asyncpg.Pool) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(40)])
    fc_aps = "aps"
    fc_als = "als"
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code=fc_aps, kind="Site", status="Active"
    )
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code=fc_als, kind="Site", status="Active"
    )
    # Templates: APS-ESAF, ALS-ESAF, APS-SAF. Seed via the in-memory
    # ClearanceTemplateLookup since build_postgres_deps doesn't trigger
    # the lifespan auto-seed.
    esaf_aps_tid = ClearanceTemplateId(clearance_template_stream_id(fc_aps, "ESAF"))
    esaf_als_tid = ClearanceTemplateId(clearance_template_stream_id(fc_als, "ESAF"))
    saf_aps_tid = ClearanceTemplateId(clearance_template_stream_id(fc_aps, "SAF"))
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=esaf_aps_tid, facility_code=fc_aps, code="ESAF", status="Active", version=1
    )
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=esaf_als_tid, facility_code=fc_als, code="ESAF", status="Active", version=1
    )
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=saf_aps_tid, facility_code=fc_aps, code="SAF", status="Active", version=1
    )
    sid_target = uuid4()  # Subject we'll filter on

    # Seed 3 Clearances:
    #   c1: template=ESAF/APS, status=Defined, risk_band=None,
    #         binds Subject sid_target
    #   c2: template=ESAF/ALS, status=Submitted (after submit), risk_band=Yellow,
    #         binds Subject sid_target + a different Subject
    #   c3: template=SAF/APS, status=Defined, risk_band=Green,
    #         binds different Subject only
    sid_other = uuid4()

    c1_id = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=esaf_aps_tid,
            facility_code=fc_aps,
            title="C1",
            bindings=frozenset({SubjectBinding(subject_id=sid_target)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    c2_id = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=esaf_als_tid,
            facility_code=fc_als,
            title="C2",
            bindings=frozenset(
                {
                    SubjectBinding(subject_id=sid_target),
                    SubjectBinding(subject_id=uuid4()),
                }
            ),
            risk_band=RiskBand.YELLOW,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Move c2 to Submitted
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=c2_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    c3_id = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=saf_aps_tid,
            facility_code=fc_aps,
            title="C3",
            bindings=frozenset({SubjectBinding(subject_id=sid_other)}),
            risk_band=RiskBand.GREEN,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Drain the projection
    await _drain(db_pool)

    handler = list_clearances.bind(deps)

    # All 3 returned with no filter
    page = await handler(
        ListClearances(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = {item.clearance_id for item in page.items}
    assert {c1_id, c2_id, c3_id}.issubset(ids)

    # Status filter narrows to c2 only
    page = await handler(
        ListClearances(status="Submitted"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    submitted_ids = {item.clearance_id for item in page.items}
    assert c2_id in submitted_ids
    assert c1_id not in submitted_ids
    assert c3_id not in submitted_ids

    # facility_code filter narrows to APS-issued (c1 + c3)
    page = await handler(
        ListClearances(facility_code=fc_aps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    aps_ids = {item.clearance_id for item in page.items}
    assert c1_id in aps_ids
    assert c3_id in aps_ids
    assert c2_id not in aps_ids

    # binds_to_subject_id filter narrows to c1 + c2 (both bind sid_target)
    page = await handler(
        ListClearances(binds_to_subject_id=sid_target),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matched = {item.clearance_id for item in page.items}
    assert c1_id in matched
    assert c2_id in matched
    assert c3_id not in matched

    # template_code="SAF" narrows to c3 only
    page = await handler(
        ListClearances(template_code="SAF"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.clearance_id for item in page.items} == {c3_id}

    # risk_band=Yellow narrows to c2 only
    page = await handler(
        ListClearances(risk_band="Yellow"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.clearance_id for item in page.items} == {c2_id}


@pytest.mark.integration
async def test_approved_with_validity_window_overrides_updates_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """`ClearanceApproved` carrying valid_from / valid_until overrides
    MUST propagate to `proj_safety_clearance_summary.valid_from` /
    `valid_until` via the COALESCE-update in the projection consumer.

    Pins the projection's `_UPDATE_APPROVED_SQL` arm at the integration
    tier; the unit test pins the SQL shape, this test pins the actual
    PG write.
    """
    from cora.safety.features.append_clearance_review_step import (
        AppendClearanceReviewStep,
    )
    from cora.safety.features.append_clearance_review_step import (
        bind as append_review_step_bind,
    )
    from cora.safety.features.approve_clearance import (
        ApproveClearance,
    )
    from cora.safety.features.approve_clearance import (
        bind as approve_bind,
    )
    from cora.safety.features.start_clearance_review import (
        StartClearanceReview,
    )
    from cora.safety.features.start_clearance_review import (
        bind as start_review_bind,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code="aps", kind="Site", status="Active"
    )
    esaf_tid = ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF"))
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=esaf_tid, facility_code="aps", code="ESAF", status="Active", version=1
    )
    valid_from = datetime(2026, 6, 1, tzinfo=UTC)
    valid_until = datetime(2026, 9, 1, tzinfo=UTC)

    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=esaf_tid,
            facility_code="aps",
            title="Approve-window override",
            bindings=frozenset({SubjectBinding(subject_id=uuid4())}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_review_bind(deps)(
        StartClearanceReview(clearance_id=cid, first_reviewer_role="ESH"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await append_review_step_bind(deps)(
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
    await approve_bind(deps)(
        ApproveClearance(
            clearance_id=cid,
            valid_from=valid_from,
            valid_until=valid_until,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    page = await list_clearances.bind(deps)(
        ListClearances(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matched = [item for item in page.items if item.clearance_id == cid]
    assert len(matched) == 1
    item = matched[0]
    assert item.status == "Approved"
    assert item.valid_from == valid_from
    assert item.valid_until == valid_until
    assert item.last_reviewed_by == _PRINCIPAL_ID


@pytest.mark.integration
async def test_list_clearances_cursor_pagination_postgres(db_pool: asyncpg.Pool) -> None:
    """Pagination invariants: page size, non-null cursor mid-page, disjoint pages,
    union covers all 3 created."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    unique_code = "DOOR"  # Use DOOR to scope to just this test's seeds
    fc = "aps"
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code=fc, kind="Site", status="Active"
    )
    door_tid = ClearanceTemplateId(clearance_template_stream_id(fc, unique_code))
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=door_tid, facility_code=fc, code=unique_code, status="Active", version=1
    )

    seeded_ids: list[UUID] = []
    for i in range(3):
        cid = await register_clearance.bind(deps)(
            RegisterClearance(
                template_id=door_tid,
                facility_code=fc,
                title=f"PaginationTest-{i}",
                bindings=frozenset({SubjectBinding(subject_id=uuid4())}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        seeded_ids.append(cid)

    await _drain(db_pool)

    handler = list_clearances.bind(deps)
    # Page 1: limit=2 with template_code=DOOR + facility_code=fc scopes tightly
    page1 = await handler(
        ListClearances(limit=2, template_code=unique_code, facility_code=fc),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page1_ids = {item.clearance_id for item in page1.items}

    # Page 2: continue with cursor
    page2 = await handler(
        ListClearances(
            cursor=page1.next_cursor,
            limit=2,
            template_code=unique_code,
            facility_code=fc,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    page2_ids = {item.clearance_id for item in page2.items}

    # Disjoint pages, union covers all 3 seeds
    assert page1_ids.isdisjoint(page2_ids)
    assert page1_ids | page2_ids == set(seeded_ids)
