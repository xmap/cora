"""`DigestingDurableCopyRegistrar`: the composition root's own `DurableCopyRegistrar`.

`_durable_distribution_driver.DurableCopyRegistrar` names two obligations
and leaves both unmet: idempotent on `(dataset_id, supply_id, locator)`
established from the WRITE model, checked BEFORE digesting. This module
closes that hole.

## Composes the pure decider directly; does not call the shipped handler

`register_distribution`'s own handler (`cora.data.features.register_distribution
.handler.bind`) allocates its own fresh UUIDv7 id
(`deps.id_generator.new_id()`) and relies on that freshness to justify
`decide(state=None, ...)`: a UUIDv7 nobody has used yet is guaranteed to
have an empty stream (`handler.py`'s own docstring). This registrar
needs the OPPOSITE: a caller-CHOSEN id (walked deterministically from
`dataset_id` / `supply_id` / `locator`) so a re-delivered call lands on
the same stream twice rather than minting a second Distribution for the
same durable copy.

Widening the handler's `IdempotentHandler` to accept a caller-supplied id
does not typecheck: `with_idempotency`'s `wrapped` closure has a closed
keyword list (`command`, `principal_id`, `correlation_id`, `causation_id`,
`surface_id`, `idempotency_key`), so `wire.py`'s composition would break.
Narrowing to the bare `Handler` typechecks but repeals the handler's own
documented invariant that the fresh id IS what makes `decide(state=None)`
sound. So this module composes `decide()` + `event_store.append()`
directly, the same Pattern C every cross-BC write in this codebase
already uses (`data._ingest.decide_ingest`, `agent.subscribers
.caution_promoter._write_caution`).

## The generation chain

A single `uuid5(dataset_id, supply_id, locator)` id would be permanently
burned the first time this exact triple's Distribution is discarded:
`_durable_distribution_sweep`'s candidate query deliberately re-admits a
Dataset whose Distribution was discarded (mirroring the projection's own
partial unique index, which excludes `Discarded` rows so a re-register is
legal), and re-deriving the SAME id would collide with a non-empty
(discarded) stream forever.

The fix is a chain: `uuid5(_NAMESPACE, f"{dataset_id}:{supply_id}:{locator}#{n}")`
for `n = 0, 1, 2, 3`. Walked via `load_distribution` (the WRITE model,
never the lagging projection) BEFORE any digest:

  - empty stream at generation `n` -> that is the target id; register there.
  - non-empty, not Discarded -> `DurableCopyAlreadyRegistered`. This is
    the expected answer while the projection is catching up, and
    answering it from a directory listing plus a handful of event-store
    reads is the entire reason a stalled projector costs nothing more
    than that instead of re-reading tens of gigabytes over SSH.
  - Discarded -> advance to `n + 1`; someone discarded THIS generation's
    copy on purpose, so the next generation is where a fresh register
    belongs.

Bounded at 4 generations. Exhausting all four without landing on an
empty or non-Discarded stream means this exact triple has been
registered-then-discarded three times over, which has no operational
precedent; refusing (`DurableCopyRegisterRefused`) rather than walking
forever is the conservative choice.

## What "idempotent" actually promises here

Scoped honestly: `uuid5` gives idempotence against *this agent's own*
prior writes, because only this registrar derives ids this way. A human
calling `POST /distributions` at the very same `(dataset_id, supply_id,
uri)` triple allocates a fresh UUIDv7 through the ordinary handler, and
the write model has no uniqueness constraint on the triple at all -- only
`proj_data_distribution_summary`'s partial unique index does, at the
projection tier. That is exactly enough to solve the lagging-projection
problem this Protocol exists for (a sweep tick re-examining a Dataset it
already handled); it is not a claim that two DIFFERENT principals can
never race to register the same durable copy under two different ids.
Saying more here would let a reader infer a guarantee the write model
does not hold.

## The independence trap: three fields, not one

The decider (`register_distribution.decider.decide`) compares
`algorithm`, `value` and `byte_size` against the Dataset's OWN recorded
values. All three MUST be sourced from the digest this registrar just
computed, never from the `Dataset` it also loads for `encoding` --
sourcing even one of them from `dataset` instead of `computed` makes
that comparison agree by construction, and the whole point of digesting
the durable copy is to prove independently that its bytes match. This
class never reads `dataset.checksum` or `dataset.byte_size` for exactly
that reason; `media_type` and `conforms_to` are the only two fields
carried from `dataset.encoding`, and that asymmetry is deliberate: the
decider does not check those two against anything, so there is no
independence property to protect there.

## Refusal text

`Unreachable` from the checksum computer collapses to ONE fixed literal,
never `error_detail` verbatim: some implementors' `error_detail` values
can embed a path (the discipline is enforced at each origin, not
provable from this module reading an abstract `ChecksumComputer`), and
a refusal string here is logged the same as every other refusal in this
sweep. Decider exceptions render `str(exc)` instead: none of them can
carry a filesystem path (they report dataset ids, checksums and byte
counts), and the extra detail is a genuine diagnostic an operator can
act on without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.agent.seed_durable_copy_registrar import DURABLE_COPY_REGISTRAR_AGENT_ID
from cora.api._durable_distribution_driver import (
    DurableCopyAlreadyRegistered,
    DurableCopyRegistered,
    DurableCopyRegisterRefused,
    DurableCopyRegisterUnauthorized,
    DurableCopyRegistration,
)
from cora.data.aggregates.dataset import load_dataset
from cora.data.aggregates.distribution import (
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumAlgorithmMismatchError,
    DistributionChecksumMismatchError,
    DistributionStatus,
    InvalidAccessProtocolError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidDistributionUriError,
    event_type_name,
    load_distribution,
    to_payload,
)
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.context import (
    DistributionRegistrationContext,
)
from cora.data.features.register_distribution.decider import decide
from cora.data.ports.checksum_verifier import Unreachable
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import ConcurrencyError, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from datetime import datetime

    from cora.data.ports.checksum_computer import ChecksumComputer
    from cora.infrastructure.ports import Authorize, Clock, IdGenerator
    from cora.infrastructure.ports.event_store import EventStore
    from cora.infrastructure.ports.supply_lookup import SupplyLookup

_STREAM_TYPE = "Distribution"
_COMMAND_NAME = "RegisterDistribution"

_MAX_GENERATIONS = 4
"""Bound on the generation chain. See the module docstring: exhausting
this means the same triple has been registered and discarded three
times over, which has no operational precedent."""

# Stable namespace for the generation-chain ids this registrar derives.
# Lives in this module, not the seed module: it is an algorithm detail
# of THIS class, not part of the Agent's identity. Distinct from the
# agent's own 2679-block identity constants (`0010`/`0012`/`0013`/`0014`);
# `0002` mirrors CautionPromoter's own derived-id namespace suffix within
# its agent's block.
_NAMESPACE = UUID("01900000-0000-7000-8000-000026790002")

_DECIDER_ERRORS = (
    InvalidDistributionUriError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidAccessProtocolError,
    DistributionAlreadyExistsError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumAlgorithmMismatchError,
    DistributionChecksumMismatchError,
    DistributionByteSizeMismatchError,
)


def _candidate_distribution_id(
    *, dataset_id: UUID, supply_id: UUID, locator: str, generation: int
) -> UUID:
    return uuid5(_NAMESPACE, f"{dataset_id}:{supply_id}:{locator}#{generation}")


class DigestingDurableCopyRegistrar:
    """Production `DurableCopyRegistrar`: digests the durable copy and
    registers it by composing `register_distribution`'s own decider.

    See the module docstring for why the handler is not called, how the
    generation chain solves the discard-and-reuse case, and the
    independence discipline the digest path must hold.
    """

    def __init__(
        self,
        *,
        event_store: EventStore,
        authz: Authorize,
        supply_lookup: SupplyLookup,
        checksum_computer: ChecksumComputer,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._event_store = event_store
        self._authz = authz
        self._supply_lookup = supply_lookup
        self._checksum_computer = checksum_computer
        self._clock = clock
        self._id_generator = id_generator

    async def register(
        self,
        *,
        dataset_id: UUID,
        supply_id: UUID,
        locator: str,
        durable_path: str,
        access_protocol: str,
        observed_modified_at: datetime,
    ) -> DurableCopyRegistration:
        resolution = await self._resolve_target_id(
            dataset_id=dataset_id, supply_id=supply_id, locator=locator
        )
        if not isinstance(resolution, UUID):
            return resolution
        target_id = resolution

        decision = await self._authz.authorize(
            principal_id=DURABLE_COPY_REGISTRAR_AGENT_ID,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=NIL_SENTINEL_ID,
        )
        if isinstance(decision, Deny):
            return DurableCopyRegisterUnauthorized()

        dataset = await load_dataset(self._event_store, dataset_id)
        if dataset is None:
            return DurableCopyRegisterRefused(detail="dataset not found")

        supply = await self._supply_lookup.lookup(supply_id)
        if supply is None:
            return DurableCopyRegisterRefused(detail="supply not found")

        # `file://` built from the raw durable_path: this is the URI the
        # digest actually reads, never the `locator` that gets stored
        # (the indirect cora-capture-path:// scheme the driver minted).
        computed = await self._checksum_computer.compute(
            locator_uri=f"file://{durable_path}", supply_id=supply_id
        )
        if isinstance(computed, Unreachable):
            return DurableCopyRegisterRefused(detail="durable copy could not be digested")

        # Whole-second comparison, not a direct float-vs-nanosecond
        # equality: `observed_modified_at` and `computed.mtime_ns` come
        # from two INDEPENDENT stat() calls (locate, then the digest
        # walk), each converted through its own floating-point
        # representation on the way here. Comparing at nanosecond
        # precision would flag an unchanged file as "moved" on nothing
        # more than float round-trip noise; a copy actually moving under
        # the read changes by real seconds, not fractions of one.
        if int(observed_modified_at.timestamp()) != computed.mtime_ns // 1_000_000_000:
            return DurableCopyRegisterRefused(detail="durable copy changed while being digested")

        now = self._clock.now()
        command = RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=locator,
            checksum_algorithm=computed.algorithm,
            checksum_value=computed.value,
            byte_size=computed.byte_size,
            media_type=dataset.encoding.media_type,
            access_protocol=access_protocol,
            conforms_to=dataset.encoding.conforms_to,
        )
        context = DistributionRegistrationContext(dataset=dataset, supply=supply)
        try:
            domain_events = decide(
                state=None,
                command=command,
                context=context,
                now=now,
                new_id=target_id,
                registered_by=ActorId(DURABLE_COPY_REGISTRAR_AGENT_ID),
            )
        except _DECIDER_ERRORS as exc:
            return DurableCopyRegisterRefused(detail=str(exc))

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=uuid5(target_id, "event:0"),
                command_name=_COMMAND_NAME,
                correlation_id=self._id_generator.new_id(),
                causation_id=None,
                principal_id=DURABLE_COPY_REGISTRAR_AGENT_ID,
            )
            for event in domain_events
        ]
        try:
            await self._event_store.append(
                stream_type=_STREAM_TYPE,
                stream_id=target_id,
                expected_version=0,
                events=new_events,
            )
        except ConcurrencyError:
            return DurableCopyAlreadyRegistered(distribution_id=target_id)

        return DurableCopyRegistered(distribution_id=target_id)

    async def _resolve_target_id(
        self, *, dataset_id: UUID, supply_id: UUID, locator: str
    ) -> UUID | DurableCopyRegistration:
        """Walk the generation chain from the WRITE model; see the module docstring."""
        for generation in range(_MAX_GENERATIONS):
            candidate_id = _candidate_distribution_id(
                dataset_id=dataset_id, supply_id=supply_id, locator=locator, generation=generation
            )
            state = await load_distribution(self._event_store, candidate_id)
            if state is None:
                return candidate_id
            if state.status is not DistributionStatus.DISCARDED:
                return DurableCopyAlreadyRegistered(distribution_id=candidate_id)
        return DurableCopyRegisterRefused(
            detail="every generation at this dataset/supply/locator triple is discarded"
        )


__all__ = ["DigestingDurableCopyRegistrar"]
