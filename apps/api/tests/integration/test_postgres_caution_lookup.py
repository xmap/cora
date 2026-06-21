"""Integration tests for `PostgresCautionLookup` against a real Postgres.

Pins the cross-stream query contract under the real Caution projection:
seeds cautions via `register_caution` + `retire_caution` +
`supersede_caution` handlers, drains the projection worker, then queries
through the adapter and verifies the result matches the seeded cautions.

Mirrors `test_postgres_clearance_lookup.py` inversely (non-blocking
snapshot vs gating coverage check).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_caution_promoter import CAUTION_PROMOTER_AGENT_ID
from cora.caution._projections import register_caution_projections
from cora.caution.adapters import PostgresCautionLookup
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    ProcedureTarget,
)
from cora.caution.features import register_caution, retire_caution, supersede_caution
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.retire_caution import RetireCaution
from cora.caution.features.supersede_caution import SupersedeCaution
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000d001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000d002")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_caution_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _register_command(
    *,
    target_asset_id: UUID | None = None,
    target_procedure_id: UUID | None = None,
    text: str = "hexapod stalls below 0.5 mm/s",
    workaround: str = "run at 0.6 mm/s",
    category: CautionCategory = CautionCategory.WEAR,
    severity: CautionSeverity = CautionSeverity.CAUTION,
) -> RegisterCaution:
    if target_asset_id is not None:
        target = AssetTarget(asset_id=target_asset_id)
    elif target_procedure_id is not None:
        target = ProcedureTarget(procedure_id=target_procedure_id)
    else:
        raise AssertionError("must supply either asset_id or procedure_id")
    return RegisterCaution(
        target=target,
        category=category,
        severity=severity,
        text=text,
        workaround=workaround,
    )


@pytest.mark.integration
async def test_empty_projection_returns_empty_result(db_pool: asyncpg.Pool) -> None:
    """No cautions ever registered for the queried scope -> []."""
    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({uuid4()}),
        procedure_ids=frozenset({uuid4()}),
    )
    assert result == []


@pytest.mark.integration
async def test_single_active_asset_caution_is_returned(db_pool: asyncpg.Pool) -> None:
    """One Active caution attached to the asset is surfaced via target match."""
    caution_id = uuid4()
    asset_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[caution_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(target_asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset(),
    )
    assert len(result) == 1
    entry = result[0]
    assert entry.caution_id == caution_id
    assert entry.target_kind == "Asset"
    assert entry.target_id == asset_id
    assert entry.category == "Wear"
    assert entry.severity == "Caution"
    assert entry.text_excerpt == "hexapod stalls below 0.5 mm/s"
    assert entry.workaround_excerpt == "run at 0.6 mm/s"


@pytest.mark.integration
async def test_notice_severity_filtered_out_by_default_threshold(
    db_pool: asyncpg.Pool,
) -> None:
    """Default `min_severity='Caution'` silences Notice-severity entries
    from the Run.start banner per the design memo's read-side table."""
    notice_id = uuid4()
    asset_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[notice_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(target_asset_id=asset_id, severity=CautionSeverity.NOTICE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result_default = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset(),
    )
    assert result_default == []

    # Explicit Notice threshold lets it through.
    result_notice = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset(),
        min_severity="Notice",
    )
    assert len(result_notice) == 1
    assert result_notice[0].caution_id == notice_id


@pytest.mark.integration
async def test_retired_and_superseded_cautions_never_returned(
    db_pool: asyncpg.Pool,
) -> None:
    """The projection filter `status = 'Active'` excludes Retired +
    Superseded. The supersession CHILD is Active and IS returned;
    its parent is Superseded and is not."""
    asset_id = uuid4()

    retired_id = uuid4()
    deps_r = build_postgres_deps(db_pool, now=_NOW, ids=[retired_id, uuid4()])
    await register_caution.bind(deps_r)(
        _register_command(target_asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps_r_later = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4()])
    await retire_caution.bind(deps_r_later)(
        RetireCaution(caution_id=retired_id, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    parent_id = uuid4()
    deps_p = build_postgres_deps(db_pool, now=_NOW, ids=[parent_id, uuid4()])
    await register_caution.bind(deps_p)(
        _register_command(target_asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    child_id = uuid4()
    deps_s = build_postgres_deps(db_pool, now=_LATER, ids=[child_id, uuid4(), uuid4()])
    await supersede_caution.bind(deps_s)(
        SupersedeCaution(
            parent_id=parent_id,
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.WARNING,
            text="recalibrated; tighter limit",
            workaround="run at 0.7 mm/s",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset(),
    )
    returned_ids = {entry.caution_id for entry in result}
    # Active child of the supersession chain IS present; retired and
    # superseded parent are both absent.
    assert child_id in returned_ids
    assert retired_id not in returned_ids
    assert parent_id not in returned_ids


@pytest.mark.integration
async def test_find_retired_for_target_returns_operator_retired_match(
    db_pool: asyncpg.Pool,
) -> None:
    """find_retired_for_target surfaces a Retired caution matching
    target_kind+target_id+category+authored_by (the CautionPromoter GOV-1 guard);
    a non-matching author / category / target returns nothing."""
    asset_id = uuid4()
    retired_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[retired_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(target_asset_id=asset_id, category=CautionCategory.WEAR),
        principal_id=CAUTION_PROMOTER_AGENT_ID,  # authored_by = the promoter
        correlation_id=_CORRELATION_ID,
    )
    deps_later = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4()])
    await retire_caution.bind(deps_later)(
        RetireCaution(caution_id=retired_id, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    match = await lookup.find_retired_for_target(
        target_kind="Asset",
        target_id=asset_id,
        category="Wear",
        authored_by=CAUTION_PROMOTER_AGENT_ID,
    )
    assert len(match) == 1
    assert match[0].caution_id == retired_id

    # A Retired row is NOT returned by the Active lookup.
    assert (
        await lookup.find_active_for_run(
            asset_ids=frozenset({asset_id}), procedure_ids=frozenset(), min_severity="Notice"
        )
        == []
    )
    # Non-matching author, category, and target each return nothing.
    assert (
        await lookup.find_retired_for_target(
            target_kind="Asset", target_id=asset_id, category="Wear", authored_by=uuid4()
        )
        == []
    )
    assert (
        await lookup.find_retired_for_target(
            target_kind="Asset",
            target_id=asset_id,
            category="OperationalWindow",
            authored_by=CAUTION_PROMOTER_AGENT_ID,
        )
        == []
    )
    assert (
        await lookup.find_retired_for_target(
            target_kind="Asset",
            target_id=uuid4(),
            category="Wear",
            authored_by=CAUTION_PROMOTER_AGENT_ID,
        )
        == []
    )


@pytest.mark.integration
async def test_find_retired_for_target_excludes_superseded(db_pool: asyncpg.Pool) -> None:
    """A Superseded predecessor (status='Superseded', NOT 'Retired') does not
    veto: find_retired_for_target filters status='Retired' only, so a superseded
    same-target+category Notice is absent (pins the docstring promise)."""
    asset_id = uuid4()
    parent_id = uuid4()
    deps_p = build_postgres_deps(db_pool, now=_NOW, ids=[parent_id, uuid4()])
    await register_caution.bind(deps_p)(
        _register_command(target_asset_id=asset_id, category=CautionCategory.WEAR),
        principal_id=CAUTION_PROMOTER_AGENT_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps_s = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4(), uuid4(), uuid4()])
    await supersede_caution.bind(deps_s)(
        SupersedeCaution(
            parent_id=parent_id,
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.CAUTION,
            text="recalibrated; tighter limit",
            workaround="run at 0.7 mm/s",
        ),
        principal_id=CAUTION_PROMOTER_AGENT_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    assert (
        await lookup.find_retired_for_target(
            target_kind="Asset",
            target_id=asset_id,
            category="Wear",
            authored_by=CAUTION_PROMOTER_AGENT_ID,
        )
        == []
    )


@pytest.mark.integration
async def test_procedure_targeted_caution_matched_via_procedure_ids(
    db_pool: asyncpg.Pool,
) -> None:
    """target_kind='Procedure' rows match against the procedure_ids
    arg, independent of the asset_ids arg."""
    caution_id = uuid4()
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[caution_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(target_procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({uuid4()}),  # unrelated asset id
        procedure_ids=frozenset({procedure_id}),
    )
    assert len(result) == 1
    assert result[0].caution_id == caution_id
    assert result[0].target_kind == "Procedure"
    assert result[0].target_id == procedure_id


@pytest.mark.integration
async def test_asset_and_procedure_targets_in_one_call_returns_both(
    db_pool: asyncpg.Pool,
) -> None:
    """A single lookup call against scope `(asset_ids, procedure_ids)`
    surfaces matches from both target-kind buckets."""
    asset_id = uuid4()
    procedure_id = uuid4()
    asset_caution_id = uuid4()
    procedure_caution_id = uuid4()

    deps_a = build_postgres_deps(db_pool, now=_NOW, ids=[asset_caution_id, uuid4()])
    await register_caution.bind(deps_a)(
        _register_command(target_asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps_p = build_postgres_deps(db_pool, now=_NOW, ids=[procedure_caution_id, uuid4()])
    await register_caution.bind(deps_p)(
        _register_command(target_procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset({procedure_id}),
    )
    returned_ids = {entry.caution_id for entry in result}
    assert returned_ids == {asset_caution_id, procedure_caution_id}


@pytest.mark.integration
async def test_sort_order_warning_before_caution_before_notice(
    db_pool: asyncpg.Pool,
) -> None:
    """Result is sorted severity-descending (Warning > Caution > Notice).
    Pinned at the adapter layer so the most urgent items lead the
    snapshot."""
    asset_id = uuid4()
    notice_id = uuid4()
    caution_only_id = uuid4()
    warning_id = uuid4()

    for cid, sev in (
        (notice_id, CautionSeverity.NOTICE),
        (caution_only_id, CautionSeverity.CAUTION),
        (warning_id, CautionSeverity.WARNING),
    ):
        deps = build_postgres_deps(db_pool, now=_NOW, ids=[cid, uuid4()])
        await register_caution.bind(deps)(
            _register_command(target_asset_id=asset_id, severity=sev),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    lookup = PostgresCautionLookup(db_pool)
    result = await lookup.find_active_for_run(
        asset_ids=frozenset({asset_id}),
        procedure_ids=frozenset(),
        min_severity="Notice",
    )
    severities = [entry.severity for entry in result]
    assert severities == ["Warning", "Caution", "Notice"]
