"""End-to-end: `list_decisions` handler against real Postgres
projection table. Most-important goal: prove the
`confidence_band()` enum's `.value` strings round-trip through the
migration's CHECK constraint on `proj_decision_summary.confidence_band`
(`('Low', 'Medium', 'High', 'Certain')`). With band denormalization
happening at INSERT inside the projection, a typo in the
`ConfidenceBand` enum or a divergent CHECK clause would silently
break in production but the unit test (mock-based) couldn't catch it.

Also exercises:
  - The `confidence_band` column being `NULL` when `confidence` is
    omitted from the command (preserves the not-set distinction).
  - The `confidence_band` filter narrowing results, proving the
    partial-index added in migration 20260513030000 is reachable.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access._projections import register_access_projections
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.decision._projections import register_decision_projections
from cora.decision.features.list_decisions import ListDecisions
from cora.decision.features.list_decisions import bind as bind_list
from cora.decision.features.register_decision import RegisterDecision
from cora.decision.features.register_decision import bind as bind_register
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Access + Decision projections (Decision needs Actor
    upstream for cross-aggregate validation, but list_decisions only
    reads proj_decision_summary)."""
    registry = ProjectionRegistry()
    register_access_projections(registry)
    register_decision_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_actor(deps: Kernel, db_pool: asyncpg.Pool) -> UUID:
    """Register an Actor so register_decision's cross-aggregate
    existence check passes. Consumes 2 ids from FixedIdGenerator."""
    return await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="Decider"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_every_band_value_writes_a_check_constraint_accepted_string(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing test: prove the `ConfidenceBand` enum's
    `.value` strings (Low / Medium / High / Certain) all round-trip
    through the `proj_decision_summary.confidence_band` CHECK
    constraint. Without this round-trip, a typo in either the enum
    or the migration would silently break in production but pass
    the projection's mock-based unit test.

    Drives 4 separate Decisions through 4 confidence floats spanning
    each band's interior, plus a 5th with `confidence=None` to prove
    the NULL path survives the CHECK.
    """
    actor_id_holder: list[UUID] = []
    decision_ids: dict[str, UUID] = {}

    bands_under_test = (
        ("low", 0.10),
        ("medium", 0.50),
        ("high", 0.85),
        ("certain", 0.99),
    )
    expected_bands = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "certain": "Certain",
    }

    actor_id = uuid4()
    actor_event_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, actor_event_id])
    actor_id_holder.append(await _seed_actor(deps_actor, db_pool))

    for label, confidence in bands_under_test:
        decision_id = uuid4()
        event_id = uuid4()
        deps = _build_deps(db_pool, [decision_id, event_id])
        decision_ids[label] = await bind_register(deps)(
            RegisterDecision(
                actor_id=actor_id_holder[0],
                context="RecipeApproval",
                choice=f"approve-{label}",
                confidence=confidence,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Fifth Decision with confidence=None to prove the NULL branch
    # of the CHECK survives end-to-end.
    none_id = uuid4()
    none_event = uuid4()
    deps_none = _build_deps(db_pool, [none_id, none_event])
    decision_ids["none"] = await bind_register(deps_none)(
        RegisterDecision(
            actor_id=actor_id_holder[0],
            context="RecipeApproval",
            choice="approve-no-confidence",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT decision_id, confidence, confidence_band "
            "FROM proj_decision_summary WHERE decision_id = ANY($1)",
            list(decision_ids.values()),
        )
    by_id = {row["decision_id"]: row for row in rows}

    for label, expected_band in expected_bands.items():
        row = by_id[decision_ids[label]]
        assert row["confidence_band"] == expected_band, (
            f"band mismatch for {label}: got {row['confidence_band']!r}, expected {expected_band!r}"
        )

    none_row = by_id[decision_ids["none"]]
    assert none_row["confidence"] is None
    assert none_row["confidence_band"] is None


@pytest.mark.integration
async def test_confidence_band_filter_narrows_results(
    db_pool: asyncpg.Pool,
) -> None:
    """Filter by confidence_band returns only matching rows.

    Exercises the partial-index added in migration
    20260513030000_add_decision_summary_band_idx.sql; without that
    index the query still works but full-scans. This test pins the
    handler's filter SQL behavior, not the planner's choice."""
    actor_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, uuid4()])
    actor_real_id = await _seed_actor(deps_actor, db_pool)

    high_id = uuid4()
    deps_high = _build_deps(db_pool, [high_id, uuid4()])
    await bind_register(deps_high)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RecipeApproval",
            choice="approve",
            confidence=0.80,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    low_id = uuid4()
    deps_low = _build_deps(db_pool, [low_id, uuid4()])
    await bind_register(deps_low)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RecipeApproval",
            choice="reject",
            confidence=0.10,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = bind_list(deps_high)
    high_page = await handler(
        ListDecisions(confidence_band="High", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(high_page.items) == 1
    assert high_page.items[0].decision_id == high_id
    assert high_page.items[0].confidence_band == "High"

    low_page = await handler(
        ListDecisions(confidence_band="Low", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(low_page.items) == 1
    assert low_page.items[0].decision_id == low_id
    assert low_page.items[0].confidence_band == "Low"


@pytest.mark.integration
async def test_choice_filter_narrows_to_one_choice_value(
    db_pool: asyncpg.Pool,
) -> None:
    """Filter by `choice` returns only rows with that DecisionChoice value.

    Proves the new column populated by migration 20260605000000 round-
    trips through the projection INSERT into the handler's SELECT and
    is sargable on the `(actor_id, choice)` composite index."""
    actor_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, uuid4()])
    actor_real_id = await _seed_actor(deps_actor, db_pool)

    nominal_id = uuid4()
    deps_nominal = _build_deps(db_pool, [nominal_id, uuid4()])
    await bind_register(deps_nominal)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RunDebrief",
            choice="NominalCompletion",
            confidence=0.92,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    conflicted_id = uuid4()
    deps_conflicted = _build_deps(db_pool, [conflicted_id, uuid4()])
    await bind_register(deps_conflicted)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RunDebrief",
            choice="DebriefConflicted",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = bind_list(deps_nominal)
    nominal_page = await handler(
        ListDecisions(choice="NominalCompletion", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(nominal_page.items) == 1
    assert nominal_page.items[0].decision_id == nominal_id
    assert nominal_page.items[0].choice == "NominalCompletion"

    conflicted_page = await handler(
        ListDecisions(choice="DebriefConflicted", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conflicted_page.items) == 1
    assert conflicted_page.items[0].decision_id == conflicted_id
    assert conflicted_page.items[0].choice == "DebriefConflicted"


@pytest.mark.integration
async def test_exclude_choices_filter_drops_audit_only_rows_from_analytic_query(
    db_pool: asyncpg.Pool,
) -> None:
    """`exclude_choices` is the analytic-query primitive for excluding
    the audit-only DebriefConflicted / CautionDraftConflicted rows
    (per project_run_debriefer_lease_design follow-up). Proves the
    `<> ALL($N)` SQL composition + NOT NULL guarantee on the choice
    column survives end-to-end against real PG (NULL `<> ALL` would
    evaluate to NULL and silently drop the row otherwise)."""
    actor_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, uuid4()])
    actor_real_id = await _seed_actor(deps_actor, db_pool)

    nominal_id_a = uuid4()
    deps_a = _build_deps(db_pool, [nominal_id_a, uuid4()])
    await bind_register(deps_a)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RunDebrief",
            choice="NominalCompletion",
            confidence=0.90,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    nominal_id_b = uuid4()
    deps_b = _build_deps(db_pool, [nominal_id_b, uuid4()])
    await bind_register(deps_b)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RunDebrief",
            choice="DegradedCompletion",
            confidence=0.55,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    debrief_conflicted_id = uuid4()
    deps_conf_a = _build_deps(db_pool, [debrief_conflicted_id, uuid4()])
    await bind_register(deps_conf_a)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="RunDebrief",
            choice="DebriefConflicted",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    caution_conflicted_id = uuid4()
    deps_conf_b = _build_deps(db_pool, [caution_conflicted_id, uuid4()])
    await bind_register(deps_conf_b)(
        RegisterDecision(
            actor_id=actor_real_id,
            context="CautionProposal",
            choice="CautionDraftConflicted",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    handler = bind_list(deps_a)
    no_audit_page = await handler(
        ListDecisions(
            exclude_choices=("DebriefConflicted", "CautionDraftConflicted"),
            limit=20,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned_choices = {item.choice for item in no_audit_page.items}
    assert "DebriefConflicted" not in returned_choices
    assert "CautionDraftConflicted" not in returned_choices
    assert {"NominalCompletion", "DegradedCompletion"}.issubset(returned_choices)

    # Unfiltered baseline: the audit rows are visible.
    baseline_page = await handler(
        ListDecisions(limit=20),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    baseline_choices = {item.choice for item in baseline_page.items}
    assert "DebriefConflicted" in baseline_choices
    assert "CautionDraftConflicted" in baseline_choices


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListDecisions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.integration
async def test_cursor_walks_pages(db_pool: asyncpg.Pool) -> None:
    """5 Decisions, limit=2: walk 3 pages with cursors. Covers the
    `_LIST_WITH_CURSOR_SQL` branch and `next_cursor` build that the
    other tests in this file (single-row + filter) don't reach."""
    actor_id_holder: list[UUID] = []
    actor_id = uuid4()
    deps_actor = _build_deps(db_pool, [actor_id, uuid4()])
    actor_id_holder.append(await _seed_actor(deps_actor, db_pool))

    decision_ids: list[UUID] = []
    for i in range(5):
        dec_id = uuid4()
        decision_ids.append(dec_id)
        deps = _build_deps(db_pool, [dec_id, uuid4()])
        await bind_register(deps)(
            RegisterDecision(
                actor_id=actor_id_holder[0],
                context="RecipeApproval",
                choice=f"approve-{i}",
                confidence=0.50,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)

    handler = bind_list(_build_deps(db_pool, []))
    page1 = await handler(
        ListDecisions(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListDecisions(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListDecisions(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None
    seen = {item.decision_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(decision_ids)
