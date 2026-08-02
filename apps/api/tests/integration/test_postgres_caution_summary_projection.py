"""End-to-end: `list_cautions` handler + CautionSummaryProjection against
real Postgres.

Pins:
  - CautionRegistered -> INSERT (status='Active', last_status_changed_at=NULL)
  - CautionSuperseded -> UPDATE status='Superseded' + last_status_changed_at
                                 + superseded_by_caution_id (parent's row)
                                 + supersession child genesis lands with
                                   parent_id
  - CautionRetired    -> UPDATE status='Retired' + retired_reason
                                 + last_status_changed_at
  - tags TEXT[] round-trip + GIN-index-backed filter
  - target_kind + target_id filter
  - category / severity / min_severity / authored_by filters
  - status default ('Active') vs status='all' (full set incl. Superseded/Retired)
  - cursor pagination across multiple cautions
  - propagate_to_children stored as-is (no hierarchy walk; Watch item #8)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.caution._projections import register_caution_projections
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    ProcedureTarget,
)
from cora.caution.features import (
    list_cautions,
    register_caution,
    retire_caution,
    supersede_caution,
)
from cora.caution.features.list_cautions import ListCautions
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.retire_caution import RetireCaution
from cora.caution.features.supersede_caution import SupersedeCaution
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_caution_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _register_command(
    target_asset_id: UUID,
    *,
    text: str = "hexapod stalls below 0.5 mm/s",
    category: CautionCategory = CautionCategory.WEAR,
    severity: CautionSeverity = CautionSeverity.CAUTION,
    tags: frozenset[str] = frozenset(),
    propagate_to_children: bool = False,
) -> RegisterCaution:
    return RegisterCaution(
        target=AssetTarget(asset_id=target_asset_id),
        category=category,
        severity=severity,
        text=text,
        workaround="run at 0.6 mm/s",
        tags=tags,
        propagate_to_children=propagate_to_children,
    )


@pytest.mark.integration
async def test_register_inserts_active_with_null_audit_columns(db_pool: asyncpg.Pool) -> None:
    """CautionRegistered -> projection row in 'Active' with last_status_changed_at NULL."""
    caution_id = uuid4()
    asset_id = uuid4()
    deps = _build_deps(db_pool, [caution_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT target_kind, target_id, category, severity, status, "
            "last_status_changed_at, parent_id, "
            "superseded_by_caution_id, retired_reason, "
            "propagate_to_children, tags "
            "FROM proj_caution_summary WHERE caution_id = $1",
            caution_id,
        )
    assert row is not None
    assert row["target_kind"] == "Asset"
    assert row["target_id"] == asset_id
    assert row["category"] == "Wear"
    assert row["severity"] == "Caution"
    assert row["status"] == "Active"
    assert row["last_status_changed_at"] is None
    assert row["parent_id"] is None
    assert row["superseded_by_caution_id"] is None
    assert row["retired_reason"] is None
    assert row["propagate_to_children"] is False
    assert list(row["tags"]) == []


@pytest.mark.integration
async def test_retire_updates_status_reason_and_audit_ts(db_pool: asyncpg.Pool) -> None:
    """Register -> retire flips status Retired, sets retired_reason +
    last_status_changed_at."""
    caution_id = uuid4()
    asset_id = uuid4()
    deps = _build_deps(db_pool, [caution_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    later_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await retire_caution.bind(later_deps)(
        RetireCaution(caution_id=caution_id, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, retired_reason, last_status_changed_at "
            "FROM proj_caution_summary WHERE caution_id = $1",
            caution_id,
        )
    assert row is not None
    assert row["status"] == "Retired"
    assert row["retired_reason"] == "Resolved"
    assert row["last_status_changed_at"] == _LATER


@pytest.mark.integration
async def test_supersede_updates_parent_row_and_inserts_child_with_parent_link(
    db_pool: asyncpg.Pool,
) -> None:
    """Supersede atomic write -> parent row's status='Superseded' +
    superseded_by_caution_id, child genesis lands with parent_id."""
    parent_id = uuid4()
    asset_id = uuid4()
    deps = _build_deps(db_pool, [parent_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # supersede: child gets a new id; consumed first, then 2 event ids.
    child_id = uuid4()
    later_deps = _build_deps(db_pool, [child_id, uuid4(), uuid4()], now=_LATER)
    await supersede_caution.bind(later_deps)(
        SupersedeCaution(
            parent_id=parent_id,
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.WARNING,
            text="hexapod stalls below 0.7 mm/s after recalibration",
            workaround="run at 0.8 mm/s",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        parent_row = await conn.fetchrow(
            "SELECT status, superseded_by_caution_id, last_status_changed_at "
            "FROM proj_caution_summary WHERE caution_id = $1",
            parent_id,
        )
        child_row = await conn.fetchrow(
            "SELECT status, parent_id, severity FROM proj_caution_summary WHERE caution_id = $1",
            child_id,
        )

    assert parent_row is not None
    assert parent_row["status"] == "Superseded"
    assert parent_row["superseded_by_caution_id"] == child_id
    assert parent_row["last_status_changed_at"] == _LATER

    assert child_row is not None
    assert child_row["status"] == "Active"
    assert child_row["parent_id"] == parent_id
    assert child_row["severity"] == "Warning"


@pytest.mark.integration
async def test_list_returns_only_active_by_default(db_pool: asyncpg.Pool) -> None:
    """Default `status` filter is Active; Retired + Superseded are hidden."""
    asset_id = uuid4()
    # 3 cautions: active, retired, superseded.
    active_id = uuid4()
    retired_id = uuid4()
    parent_id = uuid4()

    for cid in (active_id, retired_id, parent_id):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_caution.bind(deps)(
            _register_command(asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    retire_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await retire_caution.bind(retire_deps)(
        RetireCaution(caution_id=retired_id, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    child_id = uuid4()
    supersede_deps = _build_deps(db_pool, [child_id, uuid4(), uuid4()], now=_LATER)
    await supersede_caution.bind(supersede_deps)(
        SupersedeCaution(
            parent_id=parent_id,
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.CAUTION,
            text="revised supersession child",
            workaround="run slower still",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # boundary now, not in the handler. To exercise the canonical shape
    # this test pins the same operator-facing behavior by passing
    # statuses=['Active'] explicitly.
    page = await list_cautions.bind(list_deps)(
        ListCautions(statuses=["Active"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # statuses=['Active'] hides the retired one + the superseded parent;
    # active_id + child_id remain Active.
    active_ids = {item.caution_id for item in page.items}
    assert active_id in active_ids
    assert child_id in active_ids
    assert retired_id not in active_ids
    assert parent_id not in active_ids


@pytest.mark.integration
async def test_list_status_all_returns_every_caution_row(db_pool: asyncpg.Pool) -> None:
    """Passing `statuses=None` (the canonical 'no status filter') returns
    every row. Route-layer translates user-facing `?status=all` to this
    None per the cleanup convention."""
    asset_id = uuid4()
    active_id = uuid4()
    retired_id = uuid4()

    for cid in (active_id, retired_id):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_caution.bind(deps)(
            _register_command(asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    retire_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await retire_caution.bind(retire_deps)(
        RetireCaution(caution_id=retired_id, reason=CautionRetireReason.WRONG_TARGET),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await list_cautions.bind(list_deps)(
        ListCautions(statuses=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {item.caution_id for item in page.items}
    assert active_id in returned
    assert retired_id in returned


@pytest.mark.integration
async def test_list_filters_by_target_kind_and_target_id(db_pool: asyncpg.Pool) -> None:
    asset_a = uuid4()
    asset_b = uuid4()
    procedure_id = uuid4()

    a_id = uuid4()
    b_id = uuid4()
    proc_id = uuid4()

    # 2 Asset cautions + 1 Procedure caution.
    for cid, target in (
        (a_id, AssetTarget(asset_id=asset_a)),
        (b_id, AssetTarget(asset_id=asset_b)),
        (proc_id, ProcedureTarget(procedure_id=procedure_id)),
    ):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_caution.bind(deps)(
            RegisterCaution(
                target=target,
                category=CautionCategory.WEAR,
                severity=CautionSeverity.CAUTION,
                text=f"caution for {cid}",
                workaround="see notes",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # target_kind=Asset -> 2 rows.
    page = await list_cautions.bind(list_deps)(
        ListCautions(target_kind="Asset"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 2
    assert {it.target_kind for it in page.items} == {"Asset"}

    # target_kind=Procedure -> 1 row.
    page = await list_cautions.bind(list_deps)(
        ListCautions(target_kind="Procedure"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].target_id == procedure_id

    # target_id=asset_a -> 1 row.
    page = await list_cautions.bind(list_deps)(
        ListCautions(target_kind="Asset", target_id=asset_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].caution_id == a_id


@pytest.mark.integration
async def test_list_filters_by_category_severity_min_severity_author_and_tag(
    db_pool: asyncpg.Pool,
) -> None:
    """Per-column filters all narrow correctly. Route convention: the
    `min_severity` UX ladder expands to the canonical `severities` list
    BEFORE reaching the handler; this test pins the post-expansion shape
    (severities=['Caution', 'Warning'] is what the route emits when the
    user passes `?min_severity=Caution`)."""
    asset_id = uuid4()
    notice_id = uuid4()
    caution_id = uuid4()
    warning_id = uuid4()

    # 3 cautions across the severity ladder + distinct categories + tags.
    seeded: list[tuple[UUID, CautionCategory, CautionSeverity, frozenset[str]]] = [
        (notice_id, CautionCategory.WEAR, CautionSeverity.NOTICE, frozenset({"alpha"})),
        (
            caution_id,
            CautionCategory.CALIBRATION,
            CautionSeverity.CAUTION,
            frozenset({"beta", "hexapod"}),
        ),
        (warning_id, CautionCategory.WIRING, CautionSeverity.WARNING, frozenset({"gamma"})),
    ]
    for cid, cat, sev, tags in seeded:
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_caution.bind(deps)(
            _register_command(asset_id, category=cat, severity=sev, tags=tags),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # category=Wiring -> 1 row.
    page = await list_cautions.bind(list_deps)(
        ListCautions(category="Wiring"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].caution_id == warning_id

    # severities=['Caution'] -> 1 row (exact match; this is what the route
    # emits for `?severity=Caution`).
    page = await list_cautions.bind(list_deps)(
        ListCautions(severities=["Caution"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].caution_id == caution_id

    # severities=['Caution', 'Warning'] -> 2 rows. This is what the route
    # emits for `?min_severity=Caution` after expanding the ladder suffix.
    page = await list_cautions.bind(list_deps)(
        ListCautions(severities=["Caution", "Warning"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {it.caution_id for it in page.items}
    assert returned == {caution_id, warning_id}

    # severities=['Warning'] -> 1 row. Equivalent to either `?severity=Warning`
    # or `?min_severity=Warning` after the route's ladder expansion (the
    # ladder's tail element is just the single value).
    page = await list_cautions.bind(list_deps)(
        ListCautions(severities=["Warning"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {it.caution_id for it in page.items} == {warning_id}

    # tag=hexapod -> 1 row via GIN index.
    page = await list_cautions.bind(list_deps)(
        ListCautions(tag="hexapod"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {it.caution_id for it in page.items} == {caution_id}

    # authored_by=<principal> -> all 3 rows (handler derives the
    # author from the request envelope's principal_id).
    page = await list_cautions.bind(list_deps)(
        ListCautions(authored_by=_PRINCIPAL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 3


@pytest.mark.integration
async def test_list_tags_round_trip_preserves_array(db_pool: asyncpg.Pool) -> None:
    """Tags TEXT[] survives the projection round-trip with original ordering."""
    caution_id = uuid4()
    deps = _build_deps(db_pool, [caution_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(uuid4(), tags=frozenset({"zeta", "alpha", "mu"})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await list_cautions.bind(list_deps)(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    # Payload tags are sorted at to_payload; projection stores as-is.
    assert sorted(page.items[0].tags) == ["alpha", "mu", "zeta"]


@pytest.mark.integration
async def test_list_cursor_pagination_across_many_cautions(db_pool: asyncpg.Pool) -> None:
    """Page-of-10 across 25 cautions => first page returns 10 + cursor;
    subsequent pages drain the remainder."""
    asset_id = uuid4()
    for i in range(25):
        deps = _build_deps(db_pool, [uuid4(), uuid4()])
        await register_caution.bind(deps)(
            _register_command(asset_id, text=f"caution {i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    seen: set[UUID] = set()
    cursor: str | None = None
    pages_fetched = 0
    # Page until exhausted (bounded loop, no infinite-fallback risk in tests).
    while True:
        page = await list_cautions.bind(list_deps)(
            ListCautions(limit=10, cursor=cursor),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        pages_fetched += 1
        seen.update(item.caution_id for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
        assert pages_fetched <= 5, "pagination should converge within 5 pages of 10"

    assert len(seen) == 25
    assert pages_fetched >= 3  # 10 + 10 + 5 ish


@pytest.mark.integration
async def test_propagate_to_children_stored_as_is_no_hierarchy_walk(
    db_pool: asyncpg.Pool,
) -> None:
    """Watch item #8: the projection writes the flag as-is; the handler does
    NOT walk Asset.parent_id chains today. The row reflects the operator's
    choice on the source caution only."""
    parent_asset = uuid4()
    child_asset = uuid4()

    # 1 caution on parent_asset with propagate=True; 0 cautions on child_asset.
    parent_id = uuid4()
    deps = _build_deps(db_pool, [parent_id, uuid4()])
    await register_caution.bind(deps)(
        _register_command(parent_asset, propagate_to_children=True),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # Querying by parent_asset returns the row with propagate=True.
    page = await list_cautions.bind(list_deps)(
        ListCautions(target_kind="Asset", target_id=parent_asset),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].propagate_to_children is True

    # Querying by child_asset returns NOTHING -- no inherited propagation.
    page = await list_cautions.bind(list_deps)(
        ListCautions(target_kind="Asset", target_id=child_asset),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
