"""The `AssignAssetPersistentId` command, intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `scheme` selects the PID
scheme (DOI or HANDLE). `suffix` is the optional operator-supplied
local part; when absent the configured `DoiMinter` adapter auto-
generates one. The command does NOT carry the resolved
`PersistentIdentifier` VO (Lock 12 server-mint posture): the handler
resolves the minter call and forwards the resolved VO into the pure
decider.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.identifier import PersistentIdentifierScheme


@dataclass(frozen=True)
class AssignAssetPersistentId:
    """Assign a persistent identifier (PIDINST Property 1) to an existing Asset.

    Set-once at the aggregate level: a second assign on an Asset that
    already carries a `persistent_id` is rejected by the decider.
    Decommissioned Assets reject the assign. The handler resolves
    `(scheme, suffix)` through the `DoiMinter` port into the full
    `PersistentIdentifier` before invoking the pure decider.
    """

    asset_id: UUID
    scheme: PersistentIdentifierScheme
    suffix: str | None = None
