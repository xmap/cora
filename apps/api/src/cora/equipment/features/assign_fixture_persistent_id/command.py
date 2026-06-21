"""The `AssignFixturePersistentId` command, intent dataclass for this slice.

`fixture_id` is the target Fixture aggregate. `scheme` selects the PID
scheme (DOI or HANDLE). `suffix` is the optional operator-supplied
local part; when absent the configured `PersistentIdentifierMinter` adapter auto-
generates one. The command does NOT carry the resolved
`PersistentIdentifier` VO (server-mint posture per Lock 5 of
[[project-fixture-pidinst-design]]): the handler resolves the minter
call and forwards the resolved VO into the pure decider.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.identifier import PersistentIdentifierScheme


@dataclass(frozen=True)
class AssignFixturePersistentId:
    """Assign a persistent identifier (PIDINST Property 1) to an existing Fixture.

    Set-once at the aggregate level: a second assign on a Fixture that
    already carries a `persistent_id` is rejected by the decider. There
    is no Fixture lifecycle gate today (Fixture has no Decommissioned
    state today). The handler resolves `(scheme, suffix)` through the
    `PersistentIdentifierMinter` port into the full `PersistentIdentifier` before invoking
    the pure decider.
    """

    fixture_id: UUID
    scheme: PersistentIdentifierScheme
    suffix: str | None = None
