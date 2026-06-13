"""End-to-end: `proj_equipment_model_summary` against real Postgres.

Exercises every Model-aggregate event handler in
`cora.equipment.projections.model.ModelSummaryProjection` against the
real projection table:

  - ModelDefined        -> INSERT row with status=Defined, manufacturer
                           flat columns, sorted declared_family_ids JSONB
  - ModelVersioned      -> UPDATE wholesale (name / manufacturer /
                           part_number / declared_family_ids / version_tag)
                           with status=Versioned
  - ModelDeprecated     -> UPDATE status=Deprecated + deprecation_reason,
                           vendor-key columns preserved for audit
  - ModelFamilyAdded    -> UPDATE declared_family_ids appending the new
                           family_id and re-sorting
  - ModelFamilyRemoved  -> UPDATE declared_family_ids dropping the family_id
                           while preserving the sorted-array shape

Plus the load-bearing fitness pin for the
20260602100000_drop_proj_equipment_model_summary_vendor_key_unique
migration: two define_model calls with the same
(manufacturer_name, part_number) but distinct model_id values BOTH
land in `proj_equipment_model_summary` without UniqueViolation, and
the projection bookmark advances past both events. This is the
regression class the migration exists to retire.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
    PartNumber,
    model_stream_id,
)
from cora.equipment.features import (
    add_model_family,
    define_family,
    define_model,
    deprecate_model,
    remove_model_family,
    version_model,
)
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.deprecate_model import DeprecateModel
from cora.equipment.features.remove_model_family import RemoveModelFamily
from cora.equipment.features.version_model import VersionModel
from cora.equipment.projections.model import ModelSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _fetch_summary(
    pool: asyncpg.Pool,
    model_id: UUID,
) -> asyncpg.Record | None:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT model_id, name,
                   manufacturer_name, manufacturer_identifier,
                   manufacturer_identifier_type,
                   part_number, declared_family_ids,
                   status, version_tag, deprecation_reason
            FROM proj_equipment_model_summary
            WHERE model_id = $1
            """,
            model_id,
        )


def _decode_jsonb_array(value: object) -> list[str]:
    """Normalize a JSONB array column: asyncpg returns either a JSON
    string or an already-parsed list depending on whether the codec
    is bound; coerce to list[str] uniformly so assertions stay terse.

    Matches the both-shapes-tolerant pattern in
    test_bootstrap_policy_seed_postgres.py."""
    decoded = json.loads(value) if isinstance(value, str) else value
    assert isinstance(decoded, list)
    return [str(elem) for elem in decoded]


async def _fetch_bookmark_position(pool: asyncpg.Pool) -> int:
    """Return the bookmark's `last_position` (BIGINT, monotonic per
    appended event) for the `proj_equipment_model_summary` row. Used
    to pin "bookmark moved past head" after draining the post-fix
    double-define case: if the second projection apply had raised
    UniqueViolation, the worker batch would have rolled back and
    `last_position` would stay pinned to the previous value (the
    bookmark UPDATE shares the same transaction as the projection
    writes)."""
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT last_position FROM projection_bookmarks WHERE name = $1",
            "proj_equipment_model_summary",
        )
    return int(value) if value is not None else 0


async def _fetch_model_defined_head(pool: asyncpg.Pool) -> int:
    """Return MAX(position) across all `ModelDefined` events. The
    bookmark must be at or past this value after a successful drain."""
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT MAX(position) FROM events WHERE event_type = $1",
            "ModelDefined",
        )
    return int(value) if value is not None else 0


@pytest.mark.integration
async def test_model_defined_inserts_summary_row(
    db_pool: asyncpg.Pool,
) -> None:
    """ModelDefined arm: INSERT row with status=Defined, manufacturer
    flat columns, sorted declared_family_ids JSONB, version_tag from
    payload when present."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-0000000ca70e")
    model_fallback_id = UUID("01900000-0000-7000-8000-0000000ca7a1")
    model_event_id = UUID("01900000-0000-7000-8000-0000000ca7ae")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[family_event_id, model_fallback_id, model_event_id],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(
                name=ManufacturerName("Aerotech"),
                identifier=ManufacturerIdentifier("https://ror.org/02jbv0t02"),
                identifier_type=ManufacturerIdentifierType.ROR,
            ),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_id}),
            version_tag="rev-A",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    assert row["name"] == "Aerotech ANT130-L"
    assert row["manufacturer_name"] == "Aerotech"
    assert row["manufacturer_identifier"] == "https://ror.org/02jbv0t02"
    assert row["manufacturer_identifier_type"] == "ROR"
    assert row["part_number"] == "ANT130-L"
    assert _decode_jsonb_array(row["declared_family_ids"]) == [str(family_id)]
    assert row["status"] == "Defined"
    assert row["version_tag"] == "rev-A"
    assert row["deprecation_reason"] is None


@pytest.mark.integration
async def test_model_versioned_replaces_summary_wholesale(
    db_pool: asyncpg.Pool,
) -> None:
    """ModelVersioned arm: UPDATE wholesale replaces name, manufacturer
    columns, part_number, declared_family_ids JSONB, version_tag; status
    flips to Versioned."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-0000000ca80e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-0000000ca80f")
    model_fallback_id = UUID("01900000-0000-7000-8000-0000000ca8a1")
    define_event_id = UUID("01900000-0000-7000-8000-0000000ca8ae")
    version_event_id = UUID("01900000-0000-7000-8000-0000000ca8af")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_a_event_id,
            family_b_event_id,
            model_fallback_id,
            define_event_id,
            version_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="StepScanTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_a_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_model.bind(deps)(
        VersionModel(
            model_id=model_id,
            name="Aerotech ANT130-LZS",
            manufacturer=Manufacturer(
                name=ManufacturerName("Aerotech"),
                identifier=ManufacturerIdentifier("https://ror.org/02jbv0t02"),
                identifier_type=ManufacturerIdentifierType.ROR,
            ),
            part_number="ANT130-LZS",
            declared_family_ids=frozenset({family_a_id, family_b_id}),
            version_tag="rev-B",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    assert row["name"] == "Aerotech ANT130-LZS"
    assert row["manufacturer_name"] == "Aerotech"
    assert row["manufacturer_identifier"] == "https://ror.org/02jbv0t02"
    assert row["manufacturer_identifier_type"] == "ROR"
    assert row["part_number"] == "ANT130-LZS"
    sorted_families = sorted([str(family_a_id), str(family_b_id)])
    assert _decode_jsonb_array(row["declared_family_ids"]) == sorted_families
    assert row["status"] == "Versioned"
    assert row["version_tag"] == "rev-B"


@pytest.mark.integration
async def test_model_deprecated_sets_reason_and_preserves_vendor_key(
    db_pool: asyncpg.Pool,
) -> None:
    """ModelDeprecated arm: UPDATE status=Deprecated + deprecation_reason;
    vendor-key columns (manufacturer_name, part_number) and
    declared_family_ids preserved so the audit trail of "what was
    deprecated" stays answerable."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-0000000ca90e")
    model_fallback_id = UUID("01900000-0000-7000-8000-0000000ca9a1")
    define_event_id = UUID("01900000-0000-7000-8000-0000000ca9ae")
    deprecate_event_id = UUID("01900000-0000-7000-8000-0000000ca9af")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_event_id,
            model_fallback_id,
            define_event_id,
            deprecate_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=model_id, reason="superseded by ANT130-LZS"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["deprecation_reason"] == "superseded by ANT130-LZS"
    assert row["manufacturer_name"] == "Aerotech"
    assert row["part_number"] == "ANT130-L"
    assert _decode_jsonb_array(row["declared_family_ids"]) == [str(family_id)]


@pytest.mark.integration
async def test_model_family_added_appends_and_resorts(
    db_pool: asyncpg.Pool,
) -> None:
    """ModelFamilyAdded arm: declared_family_ids gains family_id and is
    re-sorted to match the canonical sorted-string-array shape that
    event payloads carry."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-0000000caa0e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-0000000caa0f")
    model_fallback_id = UUID("01900000-0000-7000-8000-0000000caaa1")
    define_event_id = UUID("01900000-0000-7000-8000-0000000caaae")
    added_event_id = UUID("01900000-0000-7000-8000-0000000caaaf")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_a_event_id,
            family_b_event_id,
            model_fallback_id,
            define_event_id,
            added_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="StepScanTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_a_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_model_family.bind(deps)(
        AddModelFamily(model_id=model_id, family_id=family_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    sorted_families = sorted([str(family_a_id), str(family_b_id)])
    assert _decode_jsonb_array(row["declared_family_ids"]) == sorted_families


@pytest.mark.integration
async def test_model_family_removed_drops_and_preserves_sort(
    db_pool: asyncpg.Pool,
) -> None:
    """ModelFamilyRemoved arm: declared_family_ids loses family_id while
    the remaining elements keep canonical sort order."""
    family_a_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_a_event_id = UUID("01900000-0000-7000-8000-0000000cab0e")
    family_b_id = family_stream_id(FamilyName("StepScanTomography"))
    family_b_event_id = UUID("01900000-0000-7000-8000-0000000cab0f")
    model_fallback_id = UUID("01900000-0000-7000-8000-0000000caba1")
    define_event_id = UUID("01900000-0000-7000-8000-0000000cabae")
    removed_event_id = UUID("01900000-0000-7000-8000-0000000cabaf")
    model_id = model_stream_id(
        Manufacturer(name=ManufacturerName("Aerotech")),
        PartNumber("ANT130-L"),
        new_id=UUID(int=0),
    )

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_a_event_id,
            family_b_event_id,
            model_fallback_id,
            define_event_id,
            removed_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="StepScanTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_family_ids=frozenset({family_a_id, family_b_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_model_family.bind(deps)(
        RemoveModelFamily(model_id=model_id, family_id=family_b_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    assert _decode_jsonb_array(row["declared_family_ids"]) == [str(family_a_id)]


@pytest.mark.integration
async def test_two_placeholder_part_number_models_both_persist_and_advance_bookmark(
    db_pool: asyncpg.Pool,
) -> None:
    """Post-fix fitness: two distinct Models defined with the
    not-yet-confirmed placeholder part number get distinct random
    stream ids (the deterministic vendor-key derivation falls back to
    the caller's random id for the placeholder, so two genuinely
    different unconfirmed units stay distinct). Both must land in
    `proj_equipment_model_summary` sharing the same
    (manufacturer_name, part_number) columns, and the projection
    bookmark must advance past both ModelDefined events without
    UniqueViolation.

    This is the regression class the
    20260602100000_drop_proj_equipment_model_summary_vendor_key_unique
    migration exists to retire: with the dropped UNIQUE INDEX, two rows
    that share the vendor-key columns coexist; if the index were still
    present the second projection apply would blow up on it, poisoning
    the bookmark and stalling the projection indefinitely.

    With deterministic ids a REAL (non-placeholder) vendor key collides
    on the event store's `expected_version=0` (409 -> ConcurrencyError)
    before the projection ever runs, so the placeholder path is the one
    that still produces two persisted rows sharing the vendor-key
    columns. The Capability precedent at
    20260518210000_drop_proj_recipe_capability_summary_code_unique
    motivated this drop; vendor-key uniqueness is now decider-tier
    operator-curation discipline, not a projection-tier UNIQUE
    constraint."""
    family_id = family_stream_id(FamilyName("ContinuousRotationTomography"))
    family_event_id = UUID("01900000-0000-7000-8000-0000000cac0e")
    # Placeholder part number: model_stream_id falls back to the random
    # fallback id, so these two fallback ids ARE the two distinct Model
    # stream ids.
    first_model_id = UUID("01900000-0000-7000-8000-0000000caca1")
    first_event_id = UUID("01900000-0000-7000-8000-0000000cacae")
    second_model_id = UUID("01900000-0000-7000-8000-0000000caca2")
    second_event_id = UUID("01900000-0000-7000-8000-0000000cacaf")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            family_event_id,
            first_model_id,
            first_event_id,
            second_model_id,
            second_event_id,
        ],
    )
    await define_family.bind(deps)(
        DefineFamily(name="ContinuousRotationTomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    shared_command = DefineModel(
        name="Aerotech (pending confirmation)",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="unknown-pending-confirmation",
        declared_family_ids=frozenset({family_id}),
    )
    await define_model.bind(deps)(
        shared_command,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_model.bind(deps)(
        shared_command,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    bookmark_before = await _fetch_bookmark_position(db_pool)
    # Drain returns cleanly: no UniqueViolation, no bookmark poison.
    await drain_equipment_projections(db_pool)
    bookmark_after = await _fetch_bookmark_position(db_pool)
    model_defined_head = await _fetch_model_defined_head(db_pool)

    first_row = await _fetch_summary(db_pool, first_model_id)
    second_row = await _fetch_summary(db_pool, second_model_id)
    assert first_row is not None
    assert second_row is not None
    assert first_row["manufacturer_name"] == second_row["manufacturer_name"]
    assert first_row["part_number"] == second_row["part_number"]
    assert first_row["model_id"] != second_row["model_id"]
    # Bookmark advanced AND is at or past the head ModelDefined
    # position: the worker would not have moved past either
    # ModelDefined if the second projection apply had raised
    # UniqueViolation (the bookmark UPDATE shares the same transaction
    # as the projection writes, so a rolled-back batch leaves the
    # bookmark pinned to the previous value).
    assert bookmark_after > bookmark_before
    assert bookmark_after >= model_defined_head


# ----------------------------------------------------------------------------
# Projection-tier replay-safety tests.
#
# The aggregate decider rejects duplicate-add (ModelFamilyAlreadyPresentError)
# and absent-removal (ModelFamilyNotPresentError) at command time, so the
# only path to exercise the projector SQL's idempotency-under-replay shape
# is to construct StoredEvent values and call `projection.apply` directly.
# Sibling precedent: `test_postgres_surface_active_visit_projection.py` uses
# the same pattern for stale-Took and double-Released replay pins.
# ----------------------------------------------------------------------------

_T0 = datetime(2026, 6, 2, 14, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(hours=1)
_T2 = _T0 + timedelta(hours=2)
_T3 = _T0 + timedelta(hours=3)
_T4 = _T0 + timedelta(hours=4)


def _stored_event(
    event_type: str,
    model_id: UUID,
    payload: dict[str, object],
    occurred_at: datetime,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Model",
        stream_id=model_id,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
    )


def _defined_stored(
    model_id: UUID,
    *,
    name: str,
    manufacturer_name: str,
    part_number: str,
    declared_family_ids: list[UUID],
    occurred_at: datetime,
) -> StoredEvent:
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "name": name,
        "manufacturer": {"name": manufacturer_name},
        "part_number": part_number,
        "declared_family_ids": sorted(str(family_id) for family_id in declared_family_ids),
        "occurred_at": occurred_at.isoformat(),
    }
    return _stored_event("ModelDefined", model_id, payload, occurred_at)


def _family_added_stored(model_id: UUID, family_id: UUID, *, occurred_at: datetime) -> StoredEvent:
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": occurred_at.isoformat(),
    }
    return _stored_event("ModelFamilyAdded", model_id, payload, occurred_at)


def _family_removed_stored(
    model_id: UUID, family_id: UUID, *, occurred_at: datetime
) -> StoredEvent:
    payload: dict[str, object] = {
        "model_id": str(model_id),
        "family_id": str(family_id),
        "occurred_at": occurred_at.isoformat(),
    }
    return _stored_event("ModelFamilyRemoved", model_id, payload, occurred_at)


@pytest.mark.integration
async def test_family_added_idempotent_with_canonical_ordering(
    db_pool: asyncpg.Pool,
) -> None:
    """Define + add family A + add family A again + add family B:
    declared_family_ids = sorted([A, B]) with no duplicates. The
    projector's UNION-based re-aggregation is the load-bearing
    replay-safety layer (the aggregate rejects duplicate-add at
    command time; this exercises the projection-tier replay path)."""
    projection = ModelSummaryProjection()
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()

    async with db_pool.acquire() as conn:
        await projection.apply(
            _defined_stored(
                model_id,
                name="PCO edge 5.5",
                manufacturer_name="PCO",
                part_number="edge-5.5",
                declared_family_ids=[],
                occurred_at=_T0,
            ),
            conn,
        )
        await projection.apply(_family_added_stored(model_id, family_a, occurred_at=_T1), conn)
        await projection.apply(_family_added_stored(model_id, family_a, occurred_at=_T2), conn)
        await projection.apply(_family_added_stored(model_id, family_b, occurred_at=_T3), conn)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    expected = sorted([str(family_a), str(family_b)])
    assert _decode_jsonb_array(row["declared_family_ids"]) == expected


@pytest.mark.integration
async def test_family_removed_is_no_op_if_absent(
    db_pool: asyncpg.Pool,
) -> None:
    """Define + remove a family that was never added: the projector's
    `WHERE elem <> $2::text` filter drops nothing, declared_family_ids
    is unchanged. Replay-safety pin (the aggregate's strict guard
    rejects this at command time; this exercises the projection-tier
    replay path)."""
    projection = ModelSummaryProjection()
    model_id = uuid4()
    family_a = uuid4()
    absent_family = uuid4()

    async with db_pool.acquire() as conn:
        await projection.apply(
            _defined_stored(
                model_id,
                name="Mitutoyo SR1500",
                manufacturer_name="Mitutoyo",
                part_number="SR1500",
                declared_family_ids=[family_a],
                occurred_at=_T0,
            ),
            conn,
        )
        await projection.apply(
            _family_removed_stored(model_id, absent_family, occurred_at=_T1), conn
        )

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    assert _decode_jsonb_array(row["declared_family_ids"]) == [str(family_a)]


@pytest.mark.integration
async def test_sort_order_survives_add_remove_churn(
    db_pool: asyncpg.Pool,
) -> None:
    """Define + add A + add B + remove A + add C lands the final
    declared_family_ids = sorted([B, C]). Exercises both projector SQL
    paths (UNION-add and filter-remove) under interleaved churn."""
    projection = ModelSummaryProjection()
    model_id = uuid4()
    family_a = uuid4()
    family_b = uuid4()
    family_c = uuid4()

    async with db_pool.acquire() as conn:
        await projection.apply(
            _defined_stored(
                model_id,
                name="Newport SR50CC",
                manufacturer_name="Newport",
                part_number="SR50CC",
                declared_family_ids=[],
                occurred_at=_T0,
            ),
            conn,
        )
        await projection.apply(_family_added_stored(model_id, family_a, occurred_at=_T1), conn)
        await projection.apply(_family_added_stored(model_id, family_b, occurred_at=_T2), conn)
        await projection.apply(_family_removed_stored(model_id, family_a, occurred_at=_T3), conn)
        await projection.apply(_family_added_stored(model_id, family_c, occurred_at=_T4), conn)

    row = await _fetch_summary(db_pool, model_id)
    assert row is not None
    expected = sorted([str(family_b), str(family_c)])
    assert _decode_jsonb_array(row["declared_family_ids"]) == expected
