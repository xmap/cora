"""The `GetAssetPidinst` query: intent dataclass for the PIDINST read slice.

Mirrors `GetAssetIntegrationView` / `GetAsset`. Carries only the input
the caller controls (asset_id); the application handler adds context
(correlation_id, principal_id, surface_id) at call time.

Slice E.1 of project_asset_persistent_id_design.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetAssetPidinst:
    """Read the PIDINST v1.0 record for an existing asset by id."""

    asset_id: UUID
