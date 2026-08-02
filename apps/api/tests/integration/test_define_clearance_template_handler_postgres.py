"""End-to-end integration test: define_clearance_template handler against real Postgres.

Pinned:
- Happy path: ClearanceTemplateDefined round-trips through jsonb with
  facility_code resolved via the in-memory FacilityLookup default seed
  (the lifespan-time "cora" self-Facility); event payload carries the
  bare-str facility_code, the deterministic template_id, the trimmed
  code + title, version=1, supersedes_template_id=None, and the
  optional external_ref dropped when None.
- Facility lookup miss: a command whose facility_code does not
  resolve to a row raises ClearanceTemplateFacilityNotFoundError
  BEFORE any event is appended. No ClearanceTemplate stream is
  written.
- Cross-BC facility binding via real Postgres FacilityLookup:
  register a fresh Facility via the Federation BC, drain the
  Federation projection, then define a ClearanceTemplate bound to
  that brand-new facility_code using PostgresFacilityLookup over the
  shared pool. Pins the cross-BC handshake the same way Slice 8A
  pinned it for Asset.
- Stream-id collision: the second define_clearance_template call
  with the same (facility_code, code) but no Idempotency-Key
  collides on append_streams(expected_version=0) and surfaces as
  ConcurrencyError -- the storage-tier manifestation the decider
  would map to ClearanceTemplateAlreadyExistsError on a fold-then-
  decide path. Only one ClearanceTemplate event row exists.
- Idempotent replay via wire_safety: same Idempotency-Key plus
  same command body returns the same template_id without writing a
  second ClearanceTemplate event. Storage-cardinality pin against
  the Brandur cache-miss regression class.
- expected_version=0 enforced: the deterministic stream_id derived
  from (facility_code, code) makes the genesis-only optimistic
  concurrency guard observable. After one successful definition the
  stream is at version 1; a second bare-handler call against the
  same stream sees expected_version=0 fail with ConcurrencyError.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation._projections import register_federation_projections
from cora.federation.adapters.postgres_facility_lookup import PostgresFacilityLookup
from cora.federation.aggregates.facility import FacilityKind
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateFacilityNotFoundError,
    clearance_template_stream_id,
)
from cora.safety.features import define_clearance_template
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from cora.safety.wire import wire_safety
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


@pytest.mark.integration
async def test_define_clearance_template_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: define a ClearanceTemplate against the lifespan-seeded
    "cora" self-Facility; read the event back from the event store and
    verify ClearanceTemplateDefined is persisted with the expected
    payload shape (bare-str facility_code, version=1, no
    supersedes_template_id, no external_ref)."""
    event_id = UUID("01900000-0000-7000-8000-0000000c70e1")
    facility_code = "cora"
    template_code = "rad-safety-001"
    expected_template_id = clearance_template_stream_id(facility_code, template_code)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[event_id])

    returned_id = await define_clearance_template.bind(deps)(
        DefineClearanceTemplate(
            code=template_code,
            title="Radiation Safety Form 001",
            facility_code=facility_code,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == expected_template_id

    events, version = await deps.event_store.load("ClearanceTemplate", expected_template_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ClearanceTemplateDefined"
    assert stored.payload == {
        "template_id": str(expected_template_id),
        "facility_code": facility_code,
        "code": template_code,
        "title": "Radiation Safety Form 001",
        "occurred_at": _NOW.isoformat(),
        "defined_by": str(_PRINCIPAL_ID),
        "version": 1,
        "supersedes_template_id": None,
        "external_ref": None,
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefineClearanceTemplate"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_clearance_template_raises_facility_not_found_on_unknown_facility_code(
    db_pool: asyncpg.Pool,
) -> None:
    """Unknown facility_code: handler resolves the slug via
    FacilityLookup, finds nothing, and the decider raises
    ClearanceTemplateFacilityNotFoundError BEFORE any event is
    appended. No ClearanceTemplate stream is written."""
    event_id = uuid4()
    unknown_facility_code = "ghost-facility"
    template_code = "rad-safety-002"
    expected_stream_id = clearance_template_stream_id(unknown_facility_code, template_code)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[event_id])

    with pytest.raises(ClearanceTemplateFacilityNotFoundError) as exc_info:
        await define_clearance_template.bind(deps)(
            DefineClearanceTemplate(
                code=template_code,
                title="Template bound to unknown facility",
                facility_code=unknown_facility_code,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.facility_code.value == unknown_facility_code

    # No ClearanceTemplate event landed: the handler raised BEFORE
    # event_store.append.
    _, version = await deps.event_store.load("ClearanceTemplate", expected_stream_id)
    assert version == 0


@pytest.mark.integration
async def test_define_clearance_template_resolves_real_postgres_facility_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """Cross-BC handshake: register a fresh Facility via the Federation
    BC, drain the Federation projection, then define a ClearanceTemplate
    bound to that brand-new facility_code using PostgresFacilityLookup
    over the shared pool. The handler resolves the slug against the
    real proj_federation_facility_summary row written in Step 1."""
    facility_id = uuid4()
    facility_event_id = uuid4()
    new_code = f"maxiv-{uuid4().hex[:8]}"
    facility_deps = build_postgres_deps(db_pool, now=_NOW, ids=[facility_id, facility_event_id])
    await register_facility.bind(facility_deps)(
        RegisterFacility(
            code=new_code,
            kind=FacilityKind.SITE,
            display_name="MAX IV",
            parent_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    template_event_id = uuid4()
    template_code = "beamline-access-001"
    expected_template_id = clearance_template_stream_id(new_code, template_code)
    template_deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[template_event_id],
        facility_lookup=PostgresFacilityLookup(db_pool),
    )
    returned_id = await define_clearance_template.bind(template_deps)(
        DefineClearanceTemplate(
            code=template_code,
            title="MAX IV Beamline Access",
            facility_code=new_code,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == expected_template_id

    events, version = await template_deps.event_store.load(
        "ClearanceTemplate", expected_template_id
    )
    assert version == 1
    assert events[0].event_type == "ClearanceTemplateDefined"
    assert events[0].payload["facility_code"] == new_code
    assert events[0].payload["code"] == template_code


@pytest.mark.integration
async def test_define_clearance_template_second_call_same_key_collides_at_storage_tier(
    db_pool: asyncpg.Pool,
) -> None:
    """Stream-id derivation collision: a second define_clearance_template
    call with the same (facility_code, code) but no Idempotency-Key
    targets the same deterministic stream_id; the genesis-only
    expected_version=0 guard fails with ConcurrencyError at the
    storage tier. Only one ClearanceTemplate event row exists."""
    first_event_id = uuid4()
    second_event_id = uuid4()
    facility_code = "cora"
    template_code = f"collision-test-{uuid4().hex[:8]}"
    expected_template_id = clearance_template_stream_id(facility_code, template_code)

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[first_event_id, second_event_id],
    )
    cmd = DefineClearanceTemplate(
        code=template_code,
        title="Collision Template",
        facility_code=facility_code,
    )

    first_id = await define_clearance_template.bind(deps)(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert first_id == expected_template_id

    with pytest.raises(ConcurrencyError):
        await define_clearance_template.bind(deps)(
            cmd,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Exactly one event row exists at the deterministic stream_id.
    _, version = await deps.event_store.load("ClearanceTemplate", expected_template_id)
    assert version == 1


@pytest.mark.integration
async def test_define_clearance_template_idempotency_key_replay_returns_same_template_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Same Idempotency-Key plus same command body returns the same
    template_id without writing a second ClearanceTemplate event.
    Storage-cardinality pin against the Brandur cache-miss regression
    class. Exercises the wired IdempotentHandler from wire_safety."""
    first_event_id = uuid4()
    # The second event_id is queued but never consumed: the Brandur
    # cache hit short-circuits before id_generator.new_id() runs on
    # the replay. The id sits unclaimed at the end of the test.
    unused_replay_event_id = uuid4()
    facility_code = "cora"
    template_code = f"idemp-replay-{uuid4().hex[:8]}"
    expected_template_id = clearance_template_stream_id(facility_code, template_code)

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[first_event_id, unused_replay_event_id],
    )
    handler = wire_safety(deps).define_clearance_template
    idempotency_key = f"ck-define-clearance-template-{uuid4().hex[:8]}"
    cmd = DefineClearanceTemplate(
        code=template_code,
        title="Idempotent Replay Template",
        facility_code=facility_code,
    )

    first_id = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )
    second_id = await handler(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        idempotency_key=idempotency_key,
    )

    assert first_id == second_id
    assert first_id == expected_template_id

    # Exactly one ClearanceTemplate stream exists, with exactly one
    # ClearanceTemplateDefined event.
    _, version = await deps.event_store.load("ClearanceTemplate", expected_template_id)
    assert version == 1
