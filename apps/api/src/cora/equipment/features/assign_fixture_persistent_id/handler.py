"""Application handler for the `assign_fixture_persistent_id` slice.

Server-mint posture per Lock 5 of [[project-fixture-pidinst-design]]:
the route forwards `(fixture_id, scheme, suffix)` to the handler, and
the handler closure resolves the `PersistentIdentifier` from the shared
`DoiMinter` port BEFORE invoking the pure decider. Non-determinism
(the minter call) is captured in the handler closure per
[[project-non-determinism-principle]], NOT at the route layer. One
minter call site (this handler), not two (route + MCP tool).

Returns the assigned `PersistentIdentifier` so the route layer can echo
it in the 201 response body (Section 6.5 of the design memo): the
operator needs the authority-minted DOI string immediately; reading
back through `GET /fixtures/{id}/pidinst` is a wasteful round-trip and
is subject to projection lag.

NOT idempotency-wrapped at the CORA layer: set-once at the decider
PLUS DOI-string-as-dedup-key at DataCite (F5.2 PUT /dois/{id} upsert
semantics) covers retry safely without a CORA idempotency_key
(mirrors slice F at the Asset tier).

Mint failures bubble as `PersistentIdentifierMintError` from the port
(raised by the production adapter); the route layer maps it to HTTP
502 via the standard exception-handler registration in
`equipment/routes.py` (shared with the Asset-tier mint flow per Lock 5;
one mapping serves both callers).

Per Section 6.4 of the design memo, this slice is the FIRST Fixture-
stream mutation; per the rule-of-three convention behind
`_asset_update_handler.py` (hoisted only AFTER multiple byte-identical
longhand handlers existed), this slice ships the longhand call to
`make_update_handler` directly. A future second Fixture-stream
mutation owns hoisting the per-aggregate factory.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from cora.equipment.aggregates.asset import PersistentIdentifier
from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)
from cora.equipment.features.assign_fixture_persistent_id.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.infrastructure.update_handler import make_update_handler

if TYPE_CHECKING:
    from cora.equipment.ports.doi_minter import DoiMinter


class Handler(Protocol):
    """Callable interface every assign_fixture_persistent_id handler implements."""

    async def __call__(
        self,
        command: AssignFixturePersistentId,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PersistentIdentifier: ...


def bind(deps: Kernel) -> Handler:
    """Build an assign_fixture_persistent_id handler closed over the shared deps.

    Reads the BC-tier `DoiMinter` from `deps.equipment.doi_minter`
    (shared with the Asset-tier slice per Lock 5; same SimpleNamespace
    stash wired by `wire_equipment(deps)`). Calls `minter.mint(scheme,
    suffix)` to resolve the `PersistentIdentifier`, then runs the pure
    decider through the cross-BC `make_update_handler` factory directly
    (no per-aggregate Fixture factory ships in this slice per Section 6.4).
    Returns the assigned `PersistentIdentifier` so the route can echo
    it in the 201 body.
    """
    minter = cast("DoiMinter", deps.equipment.doi_minter)  # type: ignore[attr-defined]

    async def handler(
        command: AssignFixturePersistentId,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PersistentIdentifier:
        persistent_id = await minter.mint(scheme=command.scheme, suffix=command.suffix)

        def decide_with_resolved(
            *,
            state: Fixture | None,
            command: AssignFixturePersistentId,
            now: datetime,
        ) -> Sequence[FixtureEvent]:
            return decide(state, command, persistent_id=persistent_id, now=now)

        inner = make_update_handler(
            deps,
            stream_type="Fixture",
            target_id_attr="fixture_id",
            from_stored=from_stored,
            to_payload=to_payload,
            event_type_name=event_type_name,
            fold=fold,
            unauthorized_error=UnauthorizedError,
            command_name="AssignFixturePersistentId",
            log_prefix="assign_fixture_persistent_id",
            decide_fn=decide_with_resolved,
        )
        await inner(
            command,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        return persistent_id

    return handler
