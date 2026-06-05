"""HTTP route integration tests for `GET /fixtures/{fixture_id}/pidinst`.

Read-side slice of project_fixture_pidinst_design Section 15.2 + 15.3. Drives
the FastAPI route via `httpx.AsyncClient + ASGITransport` against an
app whose Equipment wiring is swapped to a per-test Postgres `db_pool`
Kernel; seeds the upstream Family -> Model -> Asset -> Assembly ->
Fixture chain through direct handler invocation against the same pool.
The Postgres backing is required because `define_model` resolves
declared families via `proj_equipment_family_summary`, which the
in-memory `create_app()` cannot populate. Sibling pattern to
`test_get_fixture_pidinst_handler_postgres.py` for seeding, mirroring
`test_assign_asset_persistent_id_route.py` for the deps swap.

Covers per Section 15.2 + 15.3:

  - 200 happy path: a registered Fixture whose bound Asset carries
    owners and a Model returns `PidinstRecordResponse` JSON-LD.
  - 404 for an unknown fixture_id (the route maps a returned None to
    `FixtureNotFoundError` -> 404 via the shared `_handle_not_found`).
  - 500 when the serializer surfaces a Fixture-tier
    `FixtureManufacturerStateNotAvailableError` (the registered
    `_handle_pidinst_serialization_error` 500 backstop on the
    cross-tier `FixturePidinstSerializationError` base).
  - Response body shape lock: every Pydantic field on
    `PidinstRecordResponse` is present with the documented JSON type.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from cora.api.main import create_app
from cora.equipment.adapters.stub_doi_minter import StubDoiMinter
from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import (
    AssetLevel,
    AssetOwner,
    AssetOwnerContact,
    AssetOwnerIdentifier,
    AssetOwnerIdentifierType,
    AssetOwnerName,
)
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features import (
    add_asset_family,
    add_asset_owner,
    define_assembly,
    define_family,
    define_model,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_owner import AddAssetOwner
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.wire import wire_equipment
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2024, 7, 4, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-0000ee010000")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LANDING_TEMPLATE = "https://cora.example/assets/{asset_id}/landing"
_PUBLISHER = "Argonne National Laboratory"


def _override_settings(deps: Kernel, **overrides: object) -> Kernel:
    settings_data = deps.settings.model_dump()
    settings_data.update(overrides)
    new_settings = Settings(**settings_data)  # type: ignore[arg-type]
    return replace(deps, settings=new_settings)


def _build_deps(db_pool: asyncpg.Pool, *, ids: list[UUID]) -> Kernel:
    deps = build_postgres_deps(db_pool, ids=ids, now=_NOW)
    deps = _override_settings(
        deps,
        facility_publisher=_PUBLISHER,
        landing_page_template=_LANDING_TEMPLATE,
    )
    object.__setattr__(deps, "equipment", SimpleNamespace(doi_minter=StubDoiMinter()))
    return deps


def _hzb_owner() -> AssetOwner:
    return AssetOwner(
        name=AssetOwnerName("Helmholtz-Zentrum Berlin"),
        contact=AssetOwnerContact("instrument-data@hzb.de"),
        identifier=AssetOwnerIdentifier("https://ror.org/02aj13c28"),
        identifier_type=AssetOwnerIdentifierType("ROR"),
    )


def _aerotech_manufacturer() -> Manufacturer:
    return Manufacturer(
        name=ManufacturerName("Aerotech"),
        identifier=ManufacturerIdentifier("https://ror.org/04bw7nh07"),
        identifier_type=ManufacturerIdentifierType.ROR,
    )


async def _seed_family(db_pool: asyncpg.Pool, *, name: str) -> UUID:
    family_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[family_id, define_event_id])
    await define_family.bind(deps)(
        DefineFamily(name=name, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    return family_id


async def _seed_model(db_pool: asyncpg.Pool, *, declared_family_ids: frozenset[UUID]) -> UUID:
    model_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[model_id, define_event_id])
    return await define_model.bind(deps)(
        DefineModel(
            name="ANT130-L",
            manufacturer=_aerotech_manufacturer(),
            part_number="ANT130-L-RM",
            declared_family_ids=declared_family_ids,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _add_family_to_asset(db_pool: asyncpg.Pool, *, asset_id: UUID, family_id: UUID) -> None:
    event_id = uuid4()
    deps = _build_deps(db_pool, ids=[event_id])
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_asset(
    db_pool: asyncpg.Pool,
    *,
    family_id: UUID,
    model_id: UUID | None,
    name: str,
    owner: AssetOwner | None,
) -> UUID:
    asset_id = uuid4()
    register_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[asset_id, register_event_id])
    await register_asset.bind(deps)(
        RegisterAsset(
            name=name,
            level=AssetLevel.DEVICE,
            parent_id=_PARENT_ID,
            model_id=model_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _add_family_to_asset(db_pool, asset_id=asset_id, family_id=family_id)
    if owner is not None:
        owner_event_id = uuid4()
        owner_deps = _build_deps(db_pool, ids=[owner_event_id])
        await add_asset_owner.bind(owner_deps)(
            AddAssetOwner(asset_id=asset_id, owner=owner),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    return asset_id


async def _seed_assembly_one_slot(
    db_pool: asyncpg.Pool, *, family_id: UUID, name: str = "MCTOptics"
) -> UUID:
    assembly_id = uuid4()
    define_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[assembly_id, define_event_id])
    return await define_assembly.bind(deps)(
        DefineAssembly(
            name=name,
            presents_as_family_id=family_id,
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_fixture(
    db_pool: asyncpg.Pool,
    *,
    assembly_id: UUID,
    asset_id: UUID,
) -> UUID:
    fixture_id = uuid4()
    fixture_event_id = uuid4()
    deps = _build_deps(db_pool, ids=[fixture_id, fixture_event_id])
    return await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_fixture_with_owners_and_model(db_pool: asyncpg.Pool) -> UUID:
    family_id = await _seed_family(db_pool, name="Camera")
    model_id = await _seed_model(db_pool, declared_family_ids=frozenset({family_id}))
    asset_id = await _seed_asset(
        db_pool,
        family_id=family_id,
        model_id=model_id,
        name="Camera-A",
        owner=_hzb_owner(),
    )
    assembly_id = await _seed_assembly_one_slot(db_pool, family_id=family_id)
    return await _seed_fixture(db_pool, assembly_id=assembly_id, asset_id=asset_id)


async def _seed_fixture_with_owners_but_no_model(db_pool: asyncpg.Pool) -> UUID:
    family_id = await _seed_family(db_pool, name="Camera")
    asset_id = await _seed_asset(
        db_pool,
        family_id=family_id,
        model_id=None,
        name="Camera-A",
        owner=_hzb_owner(),
    )
    assembly_id = await _seed_assembly_one_slot(db_pool, family_id=family_id)
    return await _seed_fixture(db_pool, assembly_id=assembly_id, asset_id=asset_id)


@pytest_asyncio.fixture
async def pg_async_client(db_pool: asyncpg.Pool) -> AsyncIterator[AsyncClient]:
    """Async HTTP client whose Equipment routes resolve against `db_pool`.

    `create_app()` boots with the in-memory adapters per APP_ENV=test;
    we sidestep the in-memory wiring by REPLACING `app.state.deps`,
    `app.state.settings`, and `app.state.equipment` with a Postgres-
    backed Kernel + freshly wired `EquipmentHandlers` BEFORE the route
    closure resolves them via `request.app.state.equipment.*`. The
    httpx `ASGITransport` drives the FastAPI app directly without a
    network socket, so the route's exception-handler tuples + status
    code mapping are exercised end-to-end.

    The lifespan is NOT entered, so subsystems requiring it (MCP
    session manager, projection worker, idempotency pruner, agent
    seed) do not boot. The Equipment GET route uses only the
    `app.state.equipment.get_fixture_pidinst` closure + the BC's
    exception-handler registrations, which `register_equipment_routes`
    attaches at app construction.
    """
    app = create_app()
    pg_deps = _build_deps(db_pool, ids=[])
    app.state.deps = pg_deps
    app.state.settings = pg_deps.settings
    app.state.equipment = wire_equipment(pg_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.integration
async def test_get_fixture_pidinst_route_returns_200_with_pidinst_record_for_minted_fixture(
    db_pool: asyncpg.Pool,
    pg_async_client: AsyncClient,
) -> None:
    fixture_id = await _seed_fixture_with_owners_and_model(db_pool)
    response = await pg_async_client.get(f"/fixtures/{fixture_id}/pidinst")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["identifier"]["value"] == f"urn:uuid:{fixture_id}"
    assert body["identifier"]["scheme"] == "URN"
    assert body["schema_version"]
    assert len(body["owners"]) >= 1
    assert body["owners"][0]["name"] == "Helmholtz-Zentrum Berlin"
    assert len(body["manufacturers"]) >= 1
    assert body["manufacturers"][0]["name"] == "Aerotech"


@pytest.mark.integration
async def test_get_fixture_pidinst_route_returns_404_for_unknown_fixture(
    pg_async_client: AsyncClient,
) -> None:
    missing = str(uuid4())
    response = await pg_async_client.get(f"/fixtures/{missing}/pidinst")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert missing in body["detail"]


@pytest.mark.integration
async def test_route_returns_409_when_serializer_raises_manufacturer_state_unavailable(
    db_pool: asyncpg.Pool,
    pg_async_client: AsyncClient,
) -> None:
    fixture_id = await _seed_fixture_with_owners_but_no_model(db_pool)
    response = await pg_async_client.get(f"/fixtures/{fixture_id}/pidinst")
    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "manufacturer" in body["detail"].lower()


@pytest.mark.integration
async def test_get_fixture_pidinst_route_response_body_shape_matches_pidinst_record_response(
    db_pool: asyncpg.Pool,
    pg_async_client: AsyncClient,
) -> None:
    fixture_id = await _seed_fixture_with_owners_and_model(db_pool)
    response = await pg_async_client.get(f"/fixtures/{fixture_id}/pidinst")
    assert response.status_code == 200, response.text
    body = response.json()
    expected_keys = {
        "identifier",
        "schema_version",
        "landing_page",
        "name",
        "publisher",
        "publication_year",
        "owners",
        "manufacturers",
        "model",
        "description",
        "instrument_types",
        "measured_variables",
        "dates",
        "related_identifiers",
        "alternate_identifiers",
        "measurement_techniques",
    }
    assert set(body.keys()) == expected_keys
    assert isinstance(body["identifier"], dict)
    assert set(body["identifier"].keys()) == {"value", "scheme"}
    assert isinstance(body["schema_version"], str)
    assert isinstance(body["landing_page"], str)
    assert isinstance(body["name"], str)
    assert isinstance(body["publisher"], str)
    assert isinstance(body["publication_year"], int)
    assert isinstance(body["owners"], list)
    assert isinstance(body["manufacturers"], list)
    assert body["model"] is None or isinstance(body["model"], dict)
    assert body["description"] is None or isinstance(body["description"], str)
    assert isinstance(body["instrument_types"], list)
    assert isinstance(body["measured_variables"], list)
    assert isinstance(body["dates"], list)
    assert isinstance(body["related_identifiers"], list)
    assert isinstance(body["alternate_identifiers"], list)
    assert isinstance(body["measurement_techniques"], list)
