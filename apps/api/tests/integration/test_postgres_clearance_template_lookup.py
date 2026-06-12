"""Integration tests for `PostgresClearanceTemplateLookup` against a real Postgres.

Pins the single-template projection read contract under the real Safety
projection: seeds clearance templates via `define_clearance_template` plus
the FSM transition handlers (`activate`, `deprecate`, `withdraw`,
`version`), drains the projection worker, then queries through the
adapter and verifies the returned `ClearanceTemplateLookupResult`
mirrors the seeded template's id, facility_code, code, status, and
version.

Cross-aggregate consumer ergonomics live in their own slice tests
(`version_clearance_template` parent-chain validation; future
`register_clearance` / `amend_clearance` template bindings). The
purpose of THIS module is the adapter -> projection contract: every
FSM status the projection materializes round-trips through
`lookup`, and the missing-template case returns `None`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.in_memory_clearance_template_lookup import (
    InMemoryClearanceTemplateLookup,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceTemplateLookup
from cora.safety.aggregates.clearance_template import clearance_template_stream_id
from cora.safety.features import (
    activate_clearance_template,
    define_clearance_template,
    deprecate_clearance_template,
    version_clearance_template,
    withdraw_clearance_template,
)
from cora.safety.features.activate_clearance_template import ActivateClearanceTemplate
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from cora.safety.features.deprecate_clearance_template import DeprecateClearanceTemplate
from cora.safety.features.version_clearance_template import VersionClearanceTemplate
from cora.safety.features.withdraw_clearance_template import WithdrawClearanceTemplate
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000c701")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c702")
_FACILITY_CODE = "cora"


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    """Pump the Safety projection so ClearanceTemplate events land in
    proj_safety_clearance_template_summary; PostgresClearanceTemplateLookup
    queries that projection."""
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _define_template(
    db_pool: asyncpg.Pool,
    *,
    code: str,
    title: str,
) -> UUID:
    """Define a clearance template against the lifespan-seeded "cora"
    self-Facility and return the deterministic template_id."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    return await define_clearance_template.bind(deps)(
        DefineClearanceTemplate(
            code=code,
            title=title,
            facility_code=_FACILITY_CODE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _activate_template(db_pool: asyncpg.Pool, template_id: UUID) -> None:
    """Append a `ClearanceTemplateActivated` event (Draft -> Active)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await activate_clearance_template.bind(deps)(
        ActivateClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _deprecate_template(db_pool: asyncpg.Pool, template_id: UUID) -> None:
    """Append a `ClearanceTemplateDeprecated` event (Active -> Deprecated)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await deprecate_clearance_template.bind(deps)(
        DeprecateClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _withdraw_template(db_pool: asyncpg.Pool, template_id: UUID) -> None:
    """Append a `ClearanceTemplateWithdrawn` event (any -> Withdrawn)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    await withdraw_clearance_template.bind(deps)(
        WithdrawClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_lookup_by_id_returns_none_when_template_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    """Unknown template_id resolves to None: the adapter never raises
    for missing rows, it returns None so consumers can translate to
    their own domain error at the boundary."""
    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(uuid4())
    assert result is None


@pytest.mark.integration
async def test_lookup_by_id_returns_result_when_template_defined(
    db_pool: asyncpg.Pool,
) -> None:
    """Defined-only template (Draft status, version 1) round-trips
    through the projection: id, facility_code, code, status, and
    version all reflect the seeded ClearanceTemplateDefined event."""
    template_code = f"esaf-defined-{uuid4().hex[:8]}"
    expected_id = clearance_template_stream_id(_FACILITY_CODE, template_code)

    returned_id = await _define_template(db_pool, code=template_code, title="ESAF Defined Only")
    assert returned_id == expected_id
    await _drain_safety(db_pool)

    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(expected_id)
    assert result is not None
    assert result.id == expected_id
    assert result.facility_code == _FACILITY_CODE
    assert isinstance(result.facility_code, str)
    assert result.code == template_code
    assert isinstance(result.code, str)
    assert result.status == "Draft"
    assert isinstance(result.status, str)
    assert result.version == 1
    assert isinstance(result.version, int)


@pytest.mark.integration
async def test_lookup_by_id_returns_active_after_activate_event_drains(
    db_pool: asyncpg.Pool,
) -> None:
    """After Defined + Activated, the projection row's status is
    "Active" and the adapter returns that literal value."""
    template_code = f"esaf-active-{uuid4().hex[:8]}"
    template_id = await _define_template(db_pool, code=template_code, title="ESAF Active")
    await _activate_template(db_pool, template_id)
    await _drain_safety(db_pool)

    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(template_id)
    assert result is not None
    assert result.id == template_id
    assert result.status == "Active"
    assert result.version == 1


@pytest.mark.integration
async def test_lookup_by_id_returns_deprecated_after_deprecate_event_drains(
    db_pool: asyncpg.Pool,
) -> None:
    """After Defined + Activated + Deprecated, the projection row's
    status is "Deprecated"."""
    template_code = f"esaf-deprecated-{uuid4().hex[:8]}"
    template_id = await _define_template(db_pool, code=template_code, title="ESAF Deprecated")
    await _activate_template(db_pool, template_id)
    await _deprecate_template(db_pool, template_id)
    await _drain_safety(db_pool)

    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(template_id)
    assert result is not None
    assert result.id == template_id
    assert result.status == "Deprecated"


@pytest.mark.integration
async def test_lookup_by_id_returns_withdrawn_after_withdraw_event_drains(
    db_pool: asyncpg.Pool,
) -> None:
    """After Defined + Withdrawn (Draft -> Withdrawn is a valid
    transition), the projection row's status is "Withdrawn"."""
    template_code = f"esaf-withdrawn-{uuid4().hex[:8]}"
    template_id = await _define_template(db_pool, code=template_code, title="ESAF Withdrawn")
    await _withdraw_template(db_pool, template_id)
    await _drain_safety(db_pool)

    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(template_id)
    assert result is not None
    assert result.id == template_id
    assert result.status == "Withdrawn"


@pytest.mark.integration
async def test_lookup_by_id_returns_bumped_version_after_versioned_event_drains(
    db_pool: asyncpg.Pool,
) -> None:
    """After two templates are Defined + Activated in the same facility
    and `version_clearance_template` records that the second supersedes
    the first at `new_version=2`, the projection row for the child
    template carries `version=2`. The adapter surfaces the bumped int.

    Parent-chain validation in the version handler resolves
    `supersedes_template_id` via `clearance_template_lookup`. The
    handler's deps are constructed with an in-memory lookup seeded
    with the parent's projection-shaped row so the decider sees the
    parent as Active in the same facility; the integration we are
    pinning here is the projection write path for
    `ClearanceTemplateVersioned`, not the lookup port wiring."""
    parent_code = f"esaf-parent-{uuid4().hex[:8]}"
    child_code = f"esaf-child-{uuid4().hex[:8]}"

    parent_id = await _define_template(db_pool, code=parent_code, title="ESAF Parent v1")
    await _activate_template(db_pool, parent_id)
    child_id = await _define_template(db_pool, code=child_code, title="ESAF Child to be v2")
    await _activate_template(db_pool, child_id)

    seeded_lookup = InMemoryClearanceTemplateLookup()
    seeded_lookup.register(
        parent_id,
        facility_code=_FACILITY_CODE,
        code=parent_code,
        status="Active",
        version=1,
    )
    version_deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4()])
    version_deps = dataclasses.replace(
        version_deps,
        clearance_template_lookup=seeded_lookup,
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
    await _drain_safety(db_pool)

    lookup = PostgresClearanceTemplateLookup(db_pool)
    result = await lookup.lookup(child_id)
    assert result is not None
    assert result.id == child_id
    assert result.facility_code == _FACILITY_CODE
    assert result.code == child_code
    assert result.status == "Active"
    assert result.version == 2
