"""Feature-local PIDINST view assembler.

Composes the `AssetPidinstView` consumed by `to_pidinst_record` from
the Asset aggregate-loader output plus its joined neighbors (Model,
Family). Mirrors the `features/get_asset_integration_view/handler.py`
precedent EXACTLY: bare aggregate-loader function calls
(`load_asset` + `load_model` + `load_family`), no SQL JOINs across
summary projections, no `*Loader` Protocol injection (that pattern
does not exist in the codebase).

Per L6 + L22 + sections 6.2-6.3 of project_asset_persistent_id_design:

  - PURE function aside from loader reads. No clock, no UUID generator,
    no Authorize port. Settings (`facility_publisher`,
    `landing_page_template`) come in as function arguments.
  - NO raw SQL strings here. The single-statement-per-projection-writer
    rule applies to projection writers; the read-time assembler writes
    nothing.
  - Raises `AssetNotFoundError` on missing asset (the route maps to 404
    via the BC's existing 404-handler tuple registration).
  - Returns the slice-C `AssetPidinstView` dataclass unchanged; the
    handler then calls `to_pidinst_record` to produce the wire-shape
    `PidinstRecord`.
"""

import asyncio
from uuid import UUID

from cora.equipment._pidinst import AssetPidinstView, ModelPidinstView, Owner
from cora.equipment.aggregates.asset import AssetNotFoundError, load_asset
from cora.equipment.aggregates.family import load_family
from cora.equipment.aggregates.model import Model, load_model
from cora.equipment.errors import VirtualAxisNotPidinstableError
from cora.infrastructure.ports import EventStore


async def assemble_pidinst_view(
    event_store: EventStore,
    asset_id: UUID,
    *,
    facility_publisher: str,
    landing_page_template: str,
) -> AssetPidinstView:
    """Compose an `AssetPidinstView` for the target asset.

    Raises `AssetNotFoundError` if the asset stream is empty (the
    route's 404 handler maps the raise to a clean response). Missing
    Family / Model loads are tolerated as `None` and skipped from the
    view: a Family that was registered then admin-deleted out-of-band
    should not block a PIDINST emission on its sibling Families;
    matches the integration-view precedent's missing-Family tolerance.
    """
    asset = await load_asset(event_store, asset_id)
    if asset is None:
        raise AssetNotFoundError(asset_id)
    # Virtual axes (Assets carrying a partition_rule) are structurally
    # not PIDINST-eligible: PIDINST v1.0 mandates a Manufacturer + Owner
    # that virtual axes do not have. Reject here at view-assembly time
    # so the route returns 404 (resource not applicable) instead of 409
    # (which would mis-signal "fix this by adding a Manufacturer").
    # See [[project_virtual_axis_aggregate_followup]] for the broader
    # context on virtual-axis-as-Asset modeling.
    if asset.partition_rule is not None:
        raise VirtualAxisNotPidinstableError(asset_id)
    model = await load_model(event_store, asset.model_id) if asset.model_id is not None else None
    families = await asyncio.gather(
        *[load_family(event_store, family_id) for family_id in sorted(asset.family_ids, key=str)]
    )
    loaded_families = [family for family in families if family is not None]
    family_pairs = sorted(
        ((family.name.value, family.id) for family in loaded_families),
        key=lambda pair: (pair[0], str(pair[1])),
    )
    family_names = tuple(name for name, _ in family_pairs)
    family_ids = tuple(family_id for _, family_id in family_pairs)
    return AssetPidinstView(
        asset_id=asset.id,
        asset_name=asset.name.value,
        landing_page_url=landing_page_template.format(asset_id=asset_id),
        lifecycle=asset.lifecycle,
        alternate_identifiers=asset.alternate_identifiers,
        parent_id=asset.parent_id,
        family_names=family_names,
        family_ids=family_ids,
        model=_model_to_pidinst(model) if model is not None else None,
        commissioned_at=asset.commissioned_at,
        decommissioned_at=asset.decommissioned_at,
        publisher=facility_publisher,
        publication_year=(
            asset.commissioned_at.year if asset.commissioned_at is not None else None
        ),
        owners=tuple(
            Owner(
                name=owner.name.value,
                contact=owner.contact.value if owner.contact is not None else None,
                identifier=owner.identifier.value if owner.identifier is not None else None,
                identifier_type=(
                    owner.identifier_type.value if owner.identifier_type is not None else None
                ),
            )
            for owner in sorted(asset.owners, key=lambda o: o.name.value)
        ),
        persistent_id=asset.persistent_id,
    )


def _model_to_pidinst(model: Model) -> ModelPidinstView:
    manufacturer = model.manufacturer
    return ModelPidinstView(
        name=model.name.value,
        part_number=model.part_number.value,
        manufacturer_name=manufacturer.name.value,
        manufacturer_identifier=(
            manufacturer.identifier.value if manufacturer.identifier is not None else None
        ),
        manufacturer_identifier_type=manufacturer.identifier_type,
    )


__all__ = ["assemble_pidinst_view"]
