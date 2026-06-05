"""Feature-local Fixture PIDINST view assembler.

Composes the `FixturePidinstView` consumed by `to_fixture_pidinst_record`
from the Fixture aggregate plus its bound Assets (one level deep per
L24) and the Models those Assets reference (model-mediated Manufacturer
cascade per L9 revised). Mirrors the `features/get_asset_pidinst`
sibling assembler pattern: bare aggregate-loader function calls
(`load_fixture` + `load_asset` + `load_model`), no SQL JOINs across
summary projections.

Per Section 11 of project_fixture_pidinst_design:

  - PURE aside from loader reads. No clock, no UUID generator, no
    Authorize port. Per-deployment configuration (facility publisher,
    landing page URL) is the handler / route's responsibility; this
    assembler reads only aggregate state.
  - Returns `None` when the Fixture stream is empty; the route maps
    None to 404.
  - Walks bound Assets ONE LEVEL DEEP per L24; sub-Fixture composition
    is deferred until first-pilot trigger.
  - Owners cascade per L7: union of bound Assets' owners, deduped by
    (name, identifier), sorted by name.
  - Manufacturers cascade per L9 revised (model-mediated): for each
    bound Asset with `model_id` set, `load_model` returns the Model
    whose single `manufacturer` is gathered into the union, deduped by
    (name, identifier), sorted by name. Asset does NOT carry a
    `manufacturers` field; Model is the catalog-tier source of truth.
    Raises `FixtureManufacturerStateNotAvailableError` if any bound
    Asset's `model_id` resolves to a missing Model.
  - Components per L11 + L27: one entry per bound Asset with a minted
    `persistent_id`; unminted bound Assets are skipped from the view's
    components tuple so HasComponent emission only carries PID-bearing
    targets.
"""

import asyncio
from uuid import UUID

from cora.equipment._pidinst_types import (
    FixtureComponentRef,
    FixturePidinstView,
)
from cora.equipment._pidinst_types import (
    Manufacturer as PidinstManufacturer,
)
from cora.equipment.aggregates.asset import AssetOwner, load_asset
from cora.equipment.aggregates.fixture import load_fixture
from cora.equipment.aggregates.model import Manufacturer, load_model
from cora.equipment.errors import FixtureManufacturerStateNotAvailableError
from cora.infrastructure.kernel import Kernel


async def assemble_fixture_pidinst_view(
    fixture_id: UUID,
    deps: Kernel,
) -> FixturePidinstView | None:
    """Compose a `FixturePidinstView` for the target fixture, or None if absent.

    Returns `None` when no Fixture exists for `fixture_id`; the route
    maps this to a 404. Raises
    `FixtureManufacturerStateNotAvailableError` per L9 revised when any
    bound Asset's `model_id` resolves to a missing Model (Model
    admin-deleted out-of-band breaks the model-mediated Manufacturer
    cascade).
    """
    fixture = await load_fixture(deps.event_store, fixture_id)
    if fixture is None:
        return None

    bound_asset_ids = sorted(
        {binding.asset_id for binding in fixture.slot_asset_bindings},
        key=str,
    )
    bound_assets_raw = await asyncio.gather(
        *[load_asset(deps.event_store, asset_id) for asset_id in bound_asset_ids]
    )
    bound_assets = [asset for asset in bound_assets_raw if asset is not None]

    asset_model_ids = [asset.model_id for asset in bound_assets if asset.model_id is not None]
    models_raw = await asyncio.gather(
        *[load_model(deps.event_store, model_id) for model_id in asset_model_ids]
    )
    model_manufacturers: list[Manufacturer] = []
    for model in models_raw:
        if model is None:
            raise FixtureManufacturerStateNotAvailableError(fixture_id)
        model_manufacturers.append(model.manufacturer)

    owners_by_dedup_key: dict[tuple[str, str | None], AssetOwner] = {}
    for asset in bound_assets:
        for owner in asset.owners:
            identifier_value = owner.identifier.value if owner.identifier is not None else None
            dedup_key = (owner.name.value, identifier_value)
            owners_by_dedup_key.setdefault(dedup_key, owner)
    owners_union = tuple(sorted(owners_by_dedup_key.values(), key=lambda o: o.name.value))

    manufacturers_by_dedup_key: dict[tuple[str, str | None], Manufacturer] = {}
    for manufacturer in model_manufacturers:
        identifier_value = (
            manufacturer.identifier.value if manufacturer.identifier is not None else None
        )
        dedup_key = (manufacturer.name.value, identifier_value)
        manufacturers_by_dedup_key.setdefault(dedup_key, manufacturer)
    manufacturers_union = tuple(
        PidinstManufacturer(
            name=m.name.value,
            identifier=m.identifier.value if m.identifier is not None else None,
            identifier_type=m.identifier_type,
        )
        for m in sorted(manufacturers_by_dedup_key.values(), key=lambda m: m.name.value)
    )

    asset_by_id = {asset.id: asset for asset in bound_assets}
    components: list[FixtureComponentRef] = []
    for binding in sorted(
        fixture.slot_asset_bindings,
        key=lambda b: (b.slot_name, str(b.asset_id)),
    ):
        asset = asset_by_id.get(binding.asset_id)
        if asset is None:
            continue
        if asset.persistent_id is None:
            continue
        components.append(
            FixtureComponentRef(
                component_id=asset.id,
                scheme=asset.persistent_id.scheme,
                value=asset.persistent_id.value,
                name=asset.name.value,
            )
        )

    registered_at = fixture.registered_at
    assert registered_at is not None, (
        "Fixture.registered_at is set by the FixtureRegistered fold; "
        "load_fixture returning a non-None Fixture implies the fold ran."
    )

    return FixturePidinstView(
        fixture_id=fixture.id,
        name=f"Fixture {fixture.id}",
        persistent_id=fixture.persistent_id,
        owners=owners_union,
        manufacturers=manufacturers_union,
        components=tuple(components),
        publication_year=registered_at.year,
    )


__all__ = ["assemble_fixture_pidinst_view"]
