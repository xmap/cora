"""Application handler for the `update_asset_partition_rule` slice.

Update-style handler: load + fold + decide + append. NOT
idempotency-wrapped (no-op-on-unchanged at the decider; HTTP-layer
caching adds no value).

**Cross-aggregate-validating create shape** (per [[project-define-method-shape]]).
The handler loads the Asset AND (optionally) loads the PseudoAxis Family to
verify Family membership before invoking the decider. This cross-stream validation
prevents the decider from seeing invalid states.

## Family-membership check at handler tier

The handler loads each Family in the Asset's `family_ids` and checks if any
carries the name "PseudoAxis". If no PseudoAxis Family is found, the handler
raises `AssetCannotUpdatePartitionRuleError` immediately, before invoking the
decider. This prevents the decider from seeing an Asset with no valid PseudoAxis
Family.

## Constituent asset loading (current limitation)

Current partition-rule shapes (Affine, Aggregation, LookupTable,
CompositePartition, SolverReference) do NOT carry constituent_asset_ids as
part of the rule. Constituents are inferred from Asset.ports input connections
at evaluator time. Therefore the handler does NOT load or validate
constituent assets here. Self-reference and nesting checks are a no-op here
and move to the runtime evaluator; they will be raised by the evaluator at
runtime if a future rule shape carries constituent_asset_ids.

## Two concurrency races (knowingly accepted)

The handler's optimistic-lock guards the Asset stream write but does NOT guard
cross-stream consistency:

  1. **Family lookup race**: a Family may be removed concurrently with this
     handler. We snapshot the families at read time; if a Family disappears
     after our load but before our append, the Family check is stale. Existing
     Asset.family_ids state is never auto-revalidated when a Family is removed
     (by design), so this is consistent with the broader stance.

  2. **Family-set race**: a concurrent `add_asset_family` between our Asset load
     and our Asset append would NOT have its Family in our check union. The
     Asset's `expected_version` guard would detect the conflicting Asset write
     and raise ConcurrencyError; the operator retries and gets the wider union
     on the next attempt.

Both races are rare in practice; we accept the small window rather than
locking across streams.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetCannotUpdatePartitionRuleError,
    AssetEvent,
    AssetNotFoundError,
    AssetPartitionRuleUpdated,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.family.read import load_family
from cora.equipment.aggregates.family.state import FamilyName
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.update_asset_partition_rule.command import UpdateAssetPartitionRule
from cora.equipment.features.update_asset_partition_rule.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

if TYPE_CHECKING:
    from cora.equipment.aggregates.family.state import Family

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "UpdateAssetPartitionRule"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_asset_partition_rule handler implements."""

    async def __call__(
        self,
        command: UpdateAssetPartitionRule,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_asset_partition_rule handler closed over the shared deps."""

    async def handler(
        command: UpdateAssetPartitionRule,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "update_asset_partition_rule.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            partition_rule_kind=(
                command.partition_rule.kind.value if command.partition_rule is not None else None
            ),
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
                "update_asset_partition_rule.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Surface 404 before the cross-aggregate PseudoAxis check, otherwise
        # a non-existent Asset would mis-surface as 409 ("not of Family
        # PseudoAxis") because family_ids would be empty.
        if state is None:
            raise AssetNotFoundError(command.asset_id)

        family_ids = list(state.family_ids)
        loaded: list[Family | None] = await asyncio.gather(
            *[load_family(deps.event_store, fid) for fid in family_ids],
        )
        # Drop any None results (Family stream missing; ID references a
        # non-existent stream). Eventual-consistency stance: an Asset can hold
        # a family_id that no longer corresponds to a real Family; we treat
        # such refs as non-PseudoAxis rather than raising.
        families = [f for f in loaded if f is not None]

        # Check that at least one of the Asset's Families is the PseudoAxis Family.
        # The PseudoAxis Family has name "PseudoAxis"; we compare by name rather
        # than by id (no constant is defined). Raise the cross-aggregate guard
        # here at handler tier (not in the decider) per the
        # cross-aggregate-validating-create pattern: the decider stays pure and
        # only sees what is on Asset state itself.
        if not any(f.name == FamilyName("PseudoAxis") for f in families):
            raise AssetCannotUpdatePartitionRuleError(
                command.asset_id,
                "Asset is not of Family PseudoAxis",
            )

        domain_events: list[AssetPartitionRuleUpdated] = decide(
            state=state,
            command=command,
            now=now,
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
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_asset_partition_rule.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            partition_rule_kind=(
                command.partition_rule.kind.value if command.partition_rule is not None else None
            ),
            family_count=len(families),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
