"""Vertical slice for the `AssignFixturePersistentId` command.

Assigns a `PersistentIdentifier` (PIDINST v1.0 Property 1) to an
existing Fixture. Set-once at the aggregate level: a second assign
raises `FixturePersistentIdAlreadyAssignedError`. Fixture has no
lifecycle FSM today, so there is no decommission-style gate (per
Section 2.4 of [[project-fixture-pidinst-design]]).

Server-mint posture per Lock 5 of the design memo (reuses the
Asset-tier `DoiMinter` port unchanged): the route forwards
`(fixture_id, scheme, suffix)` to the handler, and the handler
closure resolves the `PersistentIdentifier` from the shared
`DoiMinter` port before invoking the pure decider.

Module-as-namespace surface:

    from cora.equipment.features import assign_fixture_persistent_id

    cmd = assign_fixture_persistent_id.AssignFixturePersistentId(
        fixture_id=...,
        scheme=PersistentIdentifierScheme.DOI,
        suffix="APS-2BM-FIX-001",
    )
    handler = assign_fixture_persistent_id.bind(deps)
    persistent_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.assign_fixture_persistent_id import tool
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)
from cora.equipment.features.assign_fixture_persistent_id.decider import decide
from cora.equipment.features.assign_fixture_persistent_id.handler import Handler, bind
from cora.equipment.features.assign_fixture_persistent_id.route import router

__all__ = [
    "AssignFixturePersistentId",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
