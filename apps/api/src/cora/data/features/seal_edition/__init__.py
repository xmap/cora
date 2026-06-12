"""`seal_edition`: transitions an Edition from Registered to Sealed.

Pre-loads each member Dataset for the Production-intent guard and the
canonical Distribution per Dataset for the serializer's `DatasetRef`
boundary. Resolves the publisher Facility via `FacilityLookup`,
invokes the per-kind `EditionSerializer` (today: only
`RoCrate12Adapter`), captures the sha256 `content_hash`, and emits
`EditionSealed`. Strict-not-idempotent on re-seal.
"""

from cora.data.features.seal_edition.handler import Handler, bind
from cora.data.features.seal_edition.route import router

__all__ = ["Handler", "bind", "router"]
