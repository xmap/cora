"""Vertical slice for the `AddAssetAlternateIdentifier` command.

Mirror of `add_asset_port` for the alternate-identifier facet. Adds
a single `AlternateIdentifier` (PIDINST v1.0 Property 13) to an
existing Asset's identifier set; strict-not-idempotent: a duplicate
`(kind, value)` pair surfaces as 409 rather than silent no-op.

Module-as-namespace surface:

    from cora.equipment.features import add_asset_alternate_identifier

    cmd = add_asset_alternate_identifier.AddAssetAlternateIdentifier(
        asset_id=...,
        alternate_identifier=AlternateIdentifier(
            kind=AlternateIdentifierKind.SERIAL_NUMBER,
            value="XYZ-001",
        ),
    )
    handler = add_asset_alternate_identifier.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

The `add_asset_port` / `remove_asset_port` precedent is followed
verbatim for the slice topology (POST-style action endpoint,
strict-not-idempotent, dedicated decommissioned-guard error). See
[[project-asset-alternate-identifiers-design]] Lock E.
"""

from cora.equipment.features.add_asset_alternate_identifier import tool
from cora.equipment.features.add_asset_alternate_identifier.command import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.add_asset_alternate_identifier.decider import decide
from cora.equipment.features.add_asset_alternate_identifier.handler import Handler, bind
from cora.equipment.features.add_asset_alternate_identifier.route import router

__all__ = [
    "AddAssetAlternateIdentifier",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
