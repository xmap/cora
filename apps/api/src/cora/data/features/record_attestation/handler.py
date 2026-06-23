"""Application handler for the ``record_attestation`` slice.

Verifier-port-driven create handler. CORA computes the checksum itself
rather than trusting a caller-asserted one:

  1. Load the parent Dataset (always) and the bound Distribution (required
     for the only supported kind, ChecksumVerified).
  2. Dispatch on the Distribution URI scheme to a ChecksumVerifier adapter
     (http/https, or file:// when ``posix_checksum_roots`` is configured);
     an unsupported scheme raises ``ChecksumVerifierUnsupportedSchemeError``.
  3. Call ``verify(...)`` to walk the bytes and compute the digest, then map
     the discriminated result to an outcome + evidence and assemble an
     ``AttestationRecordingInput`` for the pure decider.

The verifier port runs HERE (it does I/O); the decider stays pure and its
invariants run as defense-in-depth over the computed evidence. ``attested_by``
is the calling principal (the operator/agent that asked CORA to verify); the
adapter that computed the digest is recorded in the evidence's ``verifier_kind``.

## No ``load_attestation(new_id)``

``new_id`` is a freshly-allocated UUIDv7 from the IdGenerator port, so the
Attestation stream is guaranteed empty; the decider is invoked with
``state=None`` and the same-stream-id race at append time is caught by
Postgres ``ConcurrencyError``.
"""

from typing import Protocol, assert_never, cast
from urllib.parse import urlparse
from uuid import UUID

from cora.data.aggregates.attestation import (
    AttestationDistributionNotFoundError,
    AttestationKind,
    AttestationKindNotYetSupportedError,
    AttestationKindRequiresDistributionError,
    AttestationOutcome,
    AttestationTreeChecksumNotYetSupportedError,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_ALGORITHM_SHA256_TREE,
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.distribution import load_distribution
from cora.data.errors import UnauthorizedError
from cora.data.features.record_attestation.command import (
    AttestationRecordingInput,
    RecordAttestation,
)
from cora.data.features.record_attestation.context import (
    AttestationRecordingContext,
)
from cora.data.features.record_attestation.decider import decide
from cora.data.ports.checksum_verifier import (
    ChecksumVerifier,
    ChecksumVerifierUnsupportedSchemeError,
    Match,
    Mismatch,
    Unreachable,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Attestation"
_COMMAND_NAME = "RecordAttestation"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare record_attestation handler, what ``bind()`` returns."""

    async def __call__(
        self,
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """record_attestation handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def _scheme_of(uri: str) -> str:
    """Return the lowercase URI scheme used for verifier dispatch."""
    return urlparse(uri).scheme.lower()


def bind(deps: Kernel) -> Handler:
    """Build a record_attestation handler closed over the shared deps."""

    async def handler(
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "record_attestation.start",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            distribution_id=(
                str(command.distribution_id) if command.distribution_id is not None else None
            ),
            kind=command.kind,
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
                "record_attestation.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Handler-tier kind-not-yet-supported guard. Runs BEFORE any
        # event-store reads to avoid leaking information about Dataset
        # / Distribution existence to callers of unsupported kinds.
        # The decider re-checks this defensively for the in-process
        # bypass case.
        if command.kind != AttestationKind.CHECKSUM_VERIFIED.value:
            try:
                _ = AttestationKind(command.kind)
            except ValueError:
                # Invalid value lands at the decider's InvalidAttestationKindError.
                pass
            else:
                raise AttestationKindNotYetSupportedError(command.kind)

        # Pre-load parent Dataset (same-BC, always required).
        dataset = await load_dataset(deps.event_store, command.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(command.dataset_id)

        # ChecksumVerified needs a byte-copy to verify; without a
        # distribution_id there is nothing to walk.
        if command.distribution_id is None:
            raise AttestationKindRequiresDistributionError(command.kind)
        distribution = await load_distribution(deps.event_store, command.distribution_id)
        if distribution is None:
            raise AttestationDistributionNotFoundError(command.distribution_id)

        # Refuse a directory (sha256-tree) Distribution: the whole-file
        # verifiers cannot reproduce a manifest digest, and a false Mismatch
        # would flip the Distribution to Stale. (The decider guards this too.)
        if distribution.checksum.algorithm == DATASET_CHECKSUM_ALGORITHM_SHA256_TREE:
            raise AttestationTreeChecksumNotYetSupportedError(
                distribution_id=distribution.id,
                algorithm=distribution.checksum.algorithm,
            )

        scheme = _scheme_of(distribution.uri.value)
        verifiers = cast(
            "dict[str, ChecksumVerifier]",
            deps.data.checksum_verifiers,  # type: ignore[attr-defined]
        )
        verifier = verifiers.get(scheme)
        if verifier is None:
            raise ChecksumVerifierUnsupportedSchemeError(scheme)

        result = await verifier.verify(
            distribution_uri=distribution.uri.value,
            expected_checksum=distribution.checksum.value,
            supply_id=distribution.supply_id,
        )
        match result:
            case Match(computed_checksum=digest):
                outcome, computed, error_detail = AttestationOutcome.MATCH.value, digest, None
            case Mismatch(computed_checksum=digest):
                outcome, computed, error_detail = AttestationOutcome.MISMATCH.value, digest, None
            case Unreachable(error_detail=detail):
                outcome, computed, error_detail = AttestationOutcome.UNREACHABLE.value, None, detail
            case _:  # pragma: no cover - the result union is closed
                assert_never(result)

        recording_input = AttestationRecordingInput(
            dataset_id=command.dataset_id,
            distribution_id=command.distribution_id,
            kind=command.kind,
            outcome=outcome,
            evidence_expected_checksum=distribution.checksum.value,
            evidence_computed_checksum=computed,
            # All current verifiers are sha256-only; a directory (sha256-tree)
            # Distribution is rejected above, so this literal is safe. When a
            # non-sha256 verifier lands, carry the algorithm on the verify()
            # result instead of hardcoding it here.
            evidence_algorithm="sha256",
            evidence_verifier_supply_id=distribution.supply_id,
            evidence_verifier_kind=verifier.kind,
            evidence_error_detail=error_detail,
        )

        context = AttestationRecordingContext(dataset=dataset, distribution=distribution)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=recording_input,
            context=context,
            now=now,
            new_id=new_id,
            attested_by=ActorId(principal_id),
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
            "record_attestation.success",
            command_name=_COMMAND_NAME,
            attestation_id=str(new_id),
            dataset_id=str(command.dataset_id),
            distribution_id=str(command.distribution_id),
            kind=command.kind,
            outcome=outcome,
            verifier_kind=verifier.kind,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler
