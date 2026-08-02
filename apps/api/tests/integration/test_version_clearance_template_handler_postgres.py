"""End-to-end integration test: version_clearance_template handler against real Postgres.

Pinned:
- Happy path single-stream v1 -> v2 round-trip: seed two sibling templates
  in the same facility (child + parent), drain Safety projections so
  PostgresClearanceTemplateLookup sees the parent row, then call
  version_clearance_template against the child. The persisted
  ClearanceTemplateVersioned event carries new_version=2 and
  supersedes_template_id pointing at the parent.
- Cross-facility parent rejected via the real Postgres FacilityLookup +
  ClearanceTemplateLookup: register a second Facility through the
  Federation BC, drain federation projections, seed a parent in that
  facility and a child in "cora", drain Safety projections, then verify
  the decider raises ClearanceTemplateFacilityMismatchError. No
  Versioned event lands on the child stream.
- Self-supersede guarded at the decider (the 6th invariant shipped
  alongside the new transitions): a command whose supersedes_template_id
  equals its template_id raises ClearanceTemplateCannotVersionError
  before the lookup is consulted. No Versioned event lands.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation._projections import register_federation_projections
from cora.federation.adapters import PostgresFacilityLookup
from cora.federation.aggregates.facility import FacilityKind
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceTemplateLookup
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateFacilityMismatchError,
    clearance_template_stream_id,
)
from cora.safety.features import (
    activate_clearance_template,
    define_clearance_template,
    version_clearance_template,
)
from cora.safety.features.activate_clearance_template import ActivateClearanceTemplate
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from cora.safety.features.version_clearance_template import VersionClearanceTemplate
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_federation(db_pool: asyncpg.Pool) -> None:
    """Pump Federation-owned projections so FacilityRegistered rows land
    in proj_federation_facility_summary; PostgresFacilityLookup queries
    that projection."""
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    """Pump Safety-owned projections so ClearanceTemplate{Defined,Activated}
    rows land in proj_safety_clearance_template_summary;
    PostgresClearanceTemplateLookup queries that projection."""
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _seed_active_template(
    db_pool: asyncpg.Pool,
    *,
    facility_code: str,
    template_code: str,
    title: str,
    facility_lookup: object | None = None,
) -> UUID:
    """Define then Activate a ClearanceTemplate. Returns its deterministic id."""
    define_event_id = uuid4()
    activate_event_id = uuid4()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[define_event_id, activate_event_id],
        facility_lookup=facility_lookup,  # type: ignore[arg-type]
    )
    template_id = await define_clearance_template.bind(deps)(
        DefineClearanceTemplate(
            code=template_code,
            title=title,
            facility_code=facility_code,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_clearance_template.bind(deps)(
        ActivateClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return template_id


@pytest.mark.integration
async def test_version_clearance_template_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Single-stream v1 -> v2 round-trip: seed two sibling templates in
    the same facility (child + parent), drain Safety projections so the
    Postgres ClearanceTemplateLookup sees the parent row, then version
    the child against the parent. Exactly one ClearanceTemplateVersioned
    event lands on the child stream with new_version=2 and
    supersedes_template_id pointing at the parent."""
    facility_code = "cora"
    child_code = f"esaf-child-{uuid4().hex[:8]}"
    parent_code = f"esaf-parent-{uuid4().hex[:8]}"
    expected_child_id = clearance_template_stream_id(facility_code, child_code)
    expected_parent_id = clearance_template_stream_id(facility_code, parent_code)

    child_id = await _seed_active_template(
        db_pool,
        facility_code=facility_code,
        template_code=child_code,
        title="Child ESAF Form",
    )
    parent_id = await _seed_active_template(
        db_pool,
        facility_code=facility_code,
        template_code=parent_code,
        title="Parent ESAF Form",
    )
    assert child_id == expected_child_id
    assert parent_id == expected_parent_id

    await _drain_safety(db_pool)

    version_event_id = uuid4()
    version_deps = replace(
        build_postgres_deps(db_pool, now=_NOW, ids=[version_event_id]),
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
    )

    await version_clearance_template.bind(version_deps)(
        VersionClearanceTemplate(
            template_id=child_id,
            new_version=2,
            supersedes_template_id=parent_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await version_deps.event_store.load("ClearanceTemplate", child_id)
    # Child stream now has: Defined (v1) + Activated (v2) + Versioned (v3).
    assert version == 3
    versioned_events = [e for e in events if e.event_type == "ClearanceTemplateVersioned"]
    assert len(versioned_events) == 1
    stored = versioned_events[0]
    assert stored.payload["template_id"] == str(child_id)
    assert stored.payload["new_version"] == 2
    assert stored.payload["supersedes_template_id"] == str(parent_id)
    assert stored.payload["versioned_by"] == str(_PRINCIPAL_ID)
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == version_event_id


@pytest.mark.integration
async def test_version_clearance_template_facility_mismatch_rejected_through_pg_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-facility chain rejection through real Postgres adapters:
    register a fresh Facility via the Federation BC, drain federation
    projections, then seed an Active parent template in that brand-new
    facility and an Active child template in the lifespan-seeded "cora"
    self-Facility. Drain Safety projections so PostgresClearanceTemplateLookup
    can resolve the parent, then attempt to version the child against the
    cross-facility parent. The decider raises
    ClearanceTemplateFacilityMismatchError and no Versioned event lands."""
    facility_id = uuid4()
    facility_event_id = uuid4()
    other_facility_code = f"maxiv-{uuid4().hex[:8]}"
    facility_deps = build_postgres_deps(db_pool, now=_NOW, ids=[facility_id, facility_event_id])
    await register_facility.bind(facility_deps)(
        RegisterFacility(
            code=other_facility_code,
            kind=FacilityKind.SITE,
            display_name="MAX IV",
            parent_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    pg_facility_lookup = PostgresFacilityLookup(db_pool)
    child_code = f"esaf-child-{uuid4().hex[:8]}"
    parent_code = f"esaf-parent-{uuid4().hex[:8]}"

    child_id = await _seed_active_template(
        db_pool,
        facility_code="cora",
        template_code=child_code,
        title="Child in cora",
    )
    parent_id = await _seed_active_template(
        db_pool,
        facility_code=other_facility_code,
        template_code=parent_code,
        title="Parent in MAX IV",
        facility_lookup=pg_facility_lookup,
    )

    await _drain_safety(db_pool)

    version_event_id = uuid4()
    version_deps = replace(
        build_postgres_deps(db_pool, now=_NOW, ids=[version_event_id]),
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
    )

    with pytest.raises(ClearanceTemplateFacilityMismatchError) as exc_info:
        await version_clearance_template.bind(version_deps)(
            VersionClearanceTemplate(
                template_id=child_id,
                new_version=2,
                supersedes_template_id=parent_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.template_id == child_id

    # No ClearanceTemplateVersioned event landed on the child stream:
    # only Defined (v1) + Activated (v2).
    events, version = await version_deps.event_store.load("ClearanceTemplate", child_id)
    assert version == 2
    assert all(e.event_type != "ClearanceTemplateVersioned" for e in events)


@pytest.mark.integration
async def test_version_clearance_template_self_supersede_rejected_at_decider(
    db_pool: asyncpg.Pool,
) -> None:
    """Self-supersede invariant (6th invariant shipped alongside the new
    transitions): a command whose supersedes_template_id equals its
    template_id raises ClearanceTemplateCannotVersionError before any
    lookup is consulted. Exactly Defined + Activated remain on the
    stream; no Versioned event is appended."""
    facility_code = "cora"
    template_code = f"esaf-self-{uuid4().hex[:8]}"
    template_id = await _seed_active_template(
        db_pool,
        facility_code=facility_code,
        template_code=template_code,
        title="Self-supersede Template",
    )
    await _drain_safety(db_pool)

    version_event_id = uuid4()
    version_deps = replace(
        build_postgres_deps(db_pool, now=_NOW, ids=[version_event_id]),
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
    )

    with pytest.raises(ClearanceTemplateCannotVersionError) as exc_info:
        await version_clearance_template.bind(version_deps)(
            VersionClearanceTemplate(
                template_id=template_id,
                new_version=2,
                supersedes_template_id=template_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.template_id == template_id

    events, version = await version_deps.event_store.load("ClearanceTemplate", template_id)
    assert version == 2
    assert all(e.event_type != "ClearanceTemplateVersioned" for e in events)
