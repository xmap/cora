"""Application handler for the `register_dataset` slice.

First Data BC handler, second cross-BC create-style handler that
pre-loads upstream aggregate state (after `start_run`). Per
gate-review Q2 lock B, this is the canonical pattern for
cross-aggregate validation in CORA, mirroring `RunStartContext`
(documented in CONTRIBUTING.md).

## Pre-load order (Run? → Subject? → each derived_from?)

  1. If `command.producing_run_id is not None`:
     `load_run(producing_run_id)` → if None,
     `ProducingRunNotFoundError` (Data-BC error → 409)
  2. If `command.subject_id is not None`:
     `load_subject(subject_id)` → if None,
     `LinkedSubjectNotFoundError` (Data-BC error → 409)
  3. For each id in `command.derived_from`:
     `load_dataset(id)` → collect missing ids, raise
     `DerivedFromDatasetsNotFoundError(missing)` if any

Loads run sequentially; could be optimized to async-gather later
but not the bottleneck at MVP scale.

## Cross-track surface

This is the first Data BC handler that crosses tracks: Run (Track
A) and Subject (Independent) are both consulted at registration
time. The pattern locked here will inform every future "X is
about Y" or "X was produced by Y" relationship.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    Dataset,
    DerivedFromDatasetsNotFoundError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
    event_type_name,
    load_dataset,
    to_payload,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.context import DatasetRegistrationContext
from cora.data.features.register_dataset.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import load_run
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import load_subject

_STREAM_TYPE = "Dataset"
_COMMAND_NAME = "RegisterDataset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_dataset handler, what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use
    bare Handler directly when they don't need idempotency
    semantics.
    """

    async def __call__(
        self,
        command: RegisterDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_dataset handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_dataset handler closed over the shared deps."""

    async def handler(
        command: RegisterDataset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_dataset.start",
            command_name=_COMMAND_NAME,
            producing_run_id=(
                str(command.producing_run_id) if command.producing_run_id is not None else None
            ),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            derived_from_count=len(command.derived_from),
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
                "register_dataset.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load cross-aggregate context (gate-review Q2 lock B).
        producing_run = None
        if command.producing_run_id is not None:
            producing_run = await load_run(deps.event_store, command.producing_run_id)
            if producing_run is None:
                raise ProducingRunNotFoundError(command.producing_run_id)

        subject = None
        if command.subject_id is not None:
            subject = await load_subject(deps.event_store, command.subject_id)
            if subject is None:
                raise LinkedSubjectNotFoundError(command.subject_id)

        derived_from_loaded: dict[UUID, Dataset] = {}
        missing_derived: list[UUID] = []
        for derived_id in sorted(command.derived_from, key=str):
            loaded = await load_dataset(deps.event_store, derived_id)
            if loaded is None:
                missing_derived.append(derived_id)
            else:
                derived_from_loaded[derived_id] = loaded
        if missing_derived:
            raise DerivedFromDatasetsNotFoundError(missing_derived)

        context = DatasetRegistrationContext(
            producing_run=producing_run,
            subject=subject,
            derived_from=derived_from_loaded,
        )

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            registered_by=ActorId(principal_id),
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
            "register_dataset.success",
            command_name=_COMMAND_NAME,
            dataset_id=str(new_id),
            producing_run_id=(
                str(command.producing_run_id) if command.producing_run_id is not None else None
            ),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            derived_from_count=len(command.derived_from),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
