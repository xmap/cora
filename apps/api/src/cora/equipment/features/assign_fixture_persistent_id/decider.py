"""Pure decider for the `AssignFixturePersistentId` command.

The decider sees `(state, command)` with the resolved
`PersistentIdentifier` passed as a keyword-only argument (server-mint
posture per Lock 5 of [[project-fixture-pidinst-design]]: the handler
resolves the minter call and forwards the resolved VO here). The
decider is PURE: it does NOT call the DoiMinter, does NOT read the
wall clock (caller injects `now`), and does NOT touch any I/O. Non-
determinism is captured in the handler closure per
[[project-non-determinism-principle]].

Two disqualifying conditions surface as dedicated error classes:

  - state is None (no Fixture exists with the given id) ->
    `FixtureNotFoundError`
  - `state.persistent_id is not None` (set-once; rejects same OR
    different value) -> `FixturePersistentIdAlreadyAssignedError`

There is NO lifecycle-forbidden error class today: Fixture has no
Decommissioned state today (Section 2.4 of the design memo). A
future retire-fixture slice owns its own forbidden-state error.

P2-FITNESS pin: this module MUST NOT import from
`cora.equipment.ports` or `cora.equipment.adapters`. Any future
refactor that quietly moves the mint into the decider will fail the
architecture test (mirrors the Asset-tier
`test_assign_asset_persistent_id_decider_does_not_import_doi_minter_or_adapters`
fitness).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import PersistentIdentifier
from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureNotFoundError,
    FixturePersistentIdAlreadyAssignedError,
    FixturePersistentIdAssigned,
)
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)


def decide(
    state: Fixture | None,
    command: AssignFixturePersistentId,
    *,
    persistent_id: PersistentIdentifier,
    now: datetime,
) -> list[FixturePersistentIdAssigned]:
    """Decide the events produced by assigning a persistent identifier.

    Invariants:
      - State must not be None -> FixtureNotFoundError
      - state.persistent_id must be None (set-once) ->
        FixturePersistentIdAlreadyAssignedError
    """
    if state is None:
        raise FixtureNotFoundError(command.fixture_id)

    if state.persistent_id is not None:
        raise FixturePersistentIdAlreadyAssignedError(
            state.id,
            current=state.persistent_id,
            attempted=persistent_id,
        )

    return [
        FixturePersistentIdAssigned(
            fixture_id=state.id,
            persistent_id_scheme=persistent_id.scheme.value,
            persistent_id_value=persistent_id.value,
            occurred_at=now,
        )
    ]
