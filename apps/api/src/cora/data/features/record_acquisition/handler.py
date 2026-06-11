"""Application handler for the `record_acquisition` slice.

Pre-loads the cross-aggregate context before reaching the pure
decider, mirroring `register_dataset`'s handler. Pre-load order
follows the design lock L14 firing order:

  1. Authorize -> UnauthorizedError (BEFORE any reads; no information
     leakage on Dataset / Asset / Run existence).
  2. Dataset pre-load via `load_dataset` -> DatasetNotFoundError.
  3. Asset lookup via `AssetLookup.lookup` -> AcquisitionAssetNotFoundError
     (None result).
  4. Run pre-load via `load_run` (only when `producing_run_id` is set)
     -> AcquisitionRunNotFoundError.

The Capturing-affordance gate (step 7 in the design lock) lives in
the pure decider, which inspects the looked-up Asset's affordance
set. The handler mints `acquisition_id`, stamps `occurred_at` from
the Clock port, and threads the envelope principal as `recorded_by`.

No `RunLookup` port exists today; the Run pre-load reaches the
Operation / Run BC's `load_run` stream read directly. The rule-of-
three for introducing a shared `RunLookup` port has not yet fired.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.acquisition import (
    AcquisitionAssetNotFoundError,
    AcquisitionRunNotFoundError,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.dataset import DatasetNotFoundError, load_dataset
from cora.data.errors import UnauthorizedError
from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.context import AcquisitionRecordingContext
from cora.data.features.record_acquisition.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import load_run
from cora.shared.identity import ActorId

_STREAM_TYPE = "Acquisition"
_COMMAND_NAME = "RecordAcquisition"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare record_acquisition handler, what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps.
    """

    async def __call__(
        self,
        command: RecordAcquisition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """record_acquisition handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RecordAcquisition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a record_acquisition handler closed over the shared deps."""

    async def handler(
        command: RecordAcquisition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "record_acquisition.start",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            producing_asset_id=str(command.producing_asset_id),
            producing_run_id=(
                str(command.producing_run_id) if command.producing_run_id is not None else None
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
                "record_acquisition.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Dataset pre-load (existence-only; status not inspected).
        dataset = await load_dataset(deps.event_store, command.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(command.dataset_id)

        # Asset lookup (carries family_affordances for the Capturing gate).
        asset = await deps.asset_lookup.lookup(command.producing_asset_id)
        if asset is None:
            raise AcquisitionAssetNotFoundError(command.producing_asset_id)

        # Run pre-load only when a Run context is named (existence-only).
        run = None
        if command.producing_run_id is not None:
            run = await load_run(deps.event_store, command.producing_run_id)
            if run is None:
                raise AcquisitionRunNotFoundError(command.producing_run_id)

        context = AcquisitionRecordingContext(dataset=dataset, asset=asset, run=run)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            recorded_by=ActorId(principal_id),
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
            "record_acquisition.success",
            command_name=_COMMAND_NAME,
            acquisition_id=str(new_id),
            dataset_id=str(command.dataset_id),
            producing_asset_id=str(command.producing_asset_id),
            producing_run_id=(
                str(command.producing_run_id) if command.producing_run_id is not None else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
