"""Application handler for the `register_fixture` slice.

Longhand create-style handler (cannot use a factory because it loads
the target Assembly plus N cross-aggregate Asset references BEFORE
calling the decider):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load target Assembly state via `load_assembly`.
  3. Load every referenced Asset state concurrently via
     `asyncio.gather` and collect their family_ids.
  4. Call pure decider with state=None (genesis on the Fixture
     stream) + context + command + now + new_id.
  5. Append the emitted event to the Fixture stream
     (single-stream-write, expected_version=0).

The N referenced Assets are NOT mutated by this slice; they pre-exist
(registered via `register_asset`) and the registration event only
records the mapping. Per-Asset `attach_asset_to_fixture` events land
as separate single-stream appends on each touched Asset stream. The
projection-side conformance computation treats a missing back-
reference as `fixture_id=None`, so a partial failure between this
slice and per-Asset attach is recoverable.

Idempotent variant: register_fixture emits genesis events on a fresh
fixture_id, which makes Idempotency-Key handling worthwhile; the
route layer threads the header in and `with_idempotency` wraps the
bare handler.
"""

import asyncio
from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.assembly import load_assembly
from cora.equipment.aggregates.asset import load_asset
from cora.equipment.aggregates.fixture import event_type_name, to_payload
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.register_fixture.command import RegisterFixture
from cora.equipment.features.register_fixture.context import RegisterFixtureContext
from cora.equipment.features.register_fixture.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Fixture"
_COMMAND_NAME = "RegisterFixture"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_fixture handler - what `bind()` returns."""

    async def __call__(
        self,
        command: RegisterFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_fixture handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def _referenced_asset_ids(command: RegisterFixture) -> tuple[UUID, ...]:
    """Collect every referenced asset_id (deduped, deterministic order).

    Sorted by str so the gather + zip use a stable iteration order that
    is not reliant on frozenset's iteration contract (CPython preserves
    it within a process but the language spec does not promise it).
    """
    return tuple(sorted({b.asset_id for b in command.slot_asset_bindings}, key=str))


def bind(deps: Kernel) -> Handler:
    """Build a register_fixture handler closed over the shared deps."""

    async def handler(
        command: RegisterFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_fixture.start",
            command_name=_COMMAND_NAME,
            assembly_id=str(command.assembly_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "register_fixture.denied",
                command_name=_COMMAND_NAME,
                assembly_id=str(command.assembly_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        asset_ids = _referenced_asset_ids(command)
        # Split gather across the two aggregate types so pyright keeps
        # `assembly_state` narrowed to `Assembly | None` and each item
        # in `assets` narrowed to `Asset | None`; a single gather across
        # both would widen everything to the union.
        assembly_state_task = asyncio.create_task(
            load_assembly(deps.event_store, command.assembly_id)
        )
        assets = await asyncio.gather(*(load_asset(deps.event_store, aid) for aid in asset_ids))
        assembly_state = await assembly_state_task
        family_ids_by_asset_id: dict[UUID, frozenset[UUID] | None] = {
            aid: (asset.family_ids if asset is not None else None)
            for aid, asset in zip(asset_ids, assets, strict=True)
        }
        lifecycle_by_asset_id = {
            aid: (asset.lifecycle if asset is not None else None)
            for aid, asset in zip(asset_ids, assets, strict=True)
        }
        context = RegisterFixtureContext(
            assembly_state=assembly_state,
            family_ids_by_asset_id=family_ids_by_asset_id,
            lifecycle_by_asset_id=lifecycle_by_asset_id,
        )

        # Decider raises FixtureAlreadyExistsError defensively when
        # state is non-None; with UUIDv7 new_id this is essentially
        # impossible, but expected_version=0 below provides the
        # structural guard against two concurrent appends on the same
        # stream.
        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_fixture.success",
            command_name=_COMMAND_NAME,
            fixture_id=str(new_id),
            assembly_id=str(command.assembly_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler
