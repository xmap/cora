"""Pure decider for the ``RecordAttestation`` command.

Pure function: given the (always None) Attestation state, a
``RecordAttestation`` command, and a pre-loaded
``AttestationRecordingContext``, returns the events to append. No I/O,
no awaits, no side effects.

``now`` and ``new_id`` are injected by the application handler from the
Clock and IdGenerator ports.

## Firing order

Per [[project_data_attestation_design]] L15 (re-stated here so the
order is local-and-greppable on the decider source):

  1. Pydantic 422 boundary parse-shape (off-decider).
  2. VO field validation: ``AttestationKind``, ``AttestationOutcome``,
     ``ChecksumVerifiedEvidence.__post_init__`` raise
     ``Invalid*Error``.
  3. Defensive kind/outcome closed-enum re-check (in-process callers
     bypassing the boundary).
  4. Authorize port -> ``UnauthorizedError`` (handler-tier; BEFORE
     event-store reads).
  5. ``AttestationKindNotYetSupportedError`` if kind is not
     ``ChecksumVerified`` (handler-tier).
  6. Pure-command kind/distribution_id gating ->
     ``AttestationKindRequiresDistributionError`` /
     ``AttestationKindRejectsDistributionError``.
  7. Pure-command evidence-shape vs kind (covered by VO validation
     today since only one concrete kind exists; the discriminator is
     the kind itself).
  8. Pure-command outcome-evidence cross-validation
     (``ChecksumVerifiedEvidence`` invariants: Match/Mismatch require
     computed_checksum non-None; Unreachable requires computed_checksum
     None and error_detail non-None).
  9. State-is-None genesis guard -> ``AttestationAlreadyExistsError``.
  10. (handler) Dataset pre-load -> ``DatasetNotFoundError``.
  11. (handler) Distribution pre-load (only if ``distribution_id`` set)
      -> ``AttestationDistributionNotFoundError``.
  12. Distribution.dataset_id equality vs command.dataset_id ->
      ``AttestationDistributionDatasetMismatchError``.
  12b. ``context.distribution.checksum.algorithm == 'sha256-tree'`` ->
      ``AttestationTreeChecksumNotYetSupportedError`` (the whole-file
      verifier cannot verify a directory digest; deferred).
  13. Belt-and-braces checksum comparison: ``kind=ChecksumVerified``
      AND ``outcome=Match`` AND ``evidence.computed_checksum !=
      context.distribution.checksum.value`` ->
      ``AttestationChecksumEvidenceMismatchError``.
  14. (handler) Scheme dispatch happens in the handler when the caller
      asks for verifier-port-driven recording; this decider takes the
      command's evidence as authoritative.
  15. Emit ``AttestationRecorded``.
"""

from datetime import datetime
from uuid import UUID

from cora.data.aggregates.attestation import (
    Attestation,
    AttestationAlreadyExistsError,
    AttestationChecksumEvidenceMismatchError,
    AttestationDistributionDatasetMismatchError,
    AttestationKind,
    AttestationKindRejectsDistributionError,
    AttestationKindRequiresDistributionError,
    AttestationOutcome,
    AttestationRecorded,
    AttestationTreeChecksumNotYetSupportedError,
    ChecksumVerifiedEvidence,
    InvalidAttestationEvidenceError,
    InvalidAttestationKindError,
    InvalidAttestationOutcomeError,
    build_checksum_verified_evidence_payload,
)
from cora.data.aggregates.dataset import DATASET_CHECKSUM_ALGORITHM_SHA256_TREE
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.context import (
    AttestationRecordingContext,
)
from cora.shared.identity import ActorId

#: Closed set of kinds that require a non-None distribution_id (byte-
#: level kinds). ``ConformsToValidated`` is the only kind outside this
#: set and is gated by ``_KINDS_REJECTING_DISTRIBUTION``.
_KINDS_REQUIRING_DISTRIBUTION: frozenset[AttestationKind] = frozenset(
    {
        AttestationKind.CHECKSUM_VERIFIED,
        AttestationKind.FORMAT_VALIDATED,
        AttestationKind.BIT_ROT_CHECKED,
    }
)

#: Closed set of kinds that forbid a distribution_id (profile claims
#: about logical Dataset content, scope-orthogonal to byte copies).
_KINDS_REJECTING_DISTRIBUTION: frozenset[AttestationKind] = frozenset(
    {AttestationKind.CONFORMS_TO_VALIDATED}
)


def decide(
    state: Attestation | None,
    command: RecordAttestation,
    *,
    context: AttestationRecordingContext,
    now: datetime,
    new_id: UUID,
    attested_by: ActorId,
) -> list[AttestationRecorded]:
    """Decide the events produced by recording a new Attestation fact.

    Invariants:
      (Firing order per [[project_data_attestation_design]] L15.)
      - kind must be in the closed AttestationKind enum
        -> InvalidAttestationKindError
      - outcome must be in the closed AttestationOutcome enum
        -> InvalidAttestationOutcomeError
      - kind in {ChecksumVerified, FormatValidated, BitRotChecked}
        requires distribution_id
        -> AttestationKindRequiresDistributionError
      - kind=ConformsToValidated forbids distribution_id
        -> AttestationKindRejectsDistributionError
      - Today only kind=ChecksumVerified is implemented
        (handler-tier rejection re-checked defensively here)
        -> AttestationKindNotYetSupportedError
      - ChecksumVerifiedEvidence VO shape must validate
        -> InvalidAttestationEvidenceError
      - outcome=Match requires evidence.computed_checksum non-None
        -> InvalidAttestationEvidenceError
      - outcome=Mismatch requires evidence.computed_checksum non-None
        -> InvalidAttestationEvidenceError
      - outcome=Unreachable requires evidence.computed_checksum None
        AND evidence.error_detail non-None
        -> InvalidAttestationEvidenceError
      - state must be None (genesis-only)
        -> AttestationAlreadyExistsError
      - context.distribution.dataset_id must equal context.dataset.id
        when distribution_id is set
        -> AttestationDistributionDatasetMismatchError
      - context.distribution.checksum.algorithm must not be 'sha256-tree'
        (the directory verifier is deferred)
        -> AttestationTreeChecksumNotYetSupportedError
      - Belt-and-braces: outcome=Match AND evidence.computed_checksum
        != context.distribution.checksum.value
        -> AttestationChecksumEvidenceMismatchError
    """
    # Step 2: VO field validation - kind / outcome closed enums.
    try:
        kind = AttestationKind(command.kind)
    except ValueError as exc:
        raise InvalidAttestationKindError(command.kind) from exc
    try:
        outcome = AttestationOutcome(command.outcome)
    except ValueError as exc:
        raise InvalidAttestationOutcomeError(command.outcome) from exc

    # Step 6: Pure-command kind/distribution_id gating. Runs BEFORE
    # evidence VO construction so the operator-facing error names the
    # specific failure (missing/extra distribution_id) rather than a
    # downstream evidence-shape symptom.
    if kind in _KINDS_REQUIRING_DISTRIBUTION and command.distribution_id is None:
        raise AttestationKindRequiresDistributionError(kind.value)
    if kind in _KINDS_REJECTING_DISTRIBUTION and command.distribution_id is not None:
        raise AttestationKindRejectsDistributionError(kind.value)

    # Step 2 (cont'd): construct the discriminated evidence VO. Today
    # only the ChecksumVerified arm is concrete; the
    # AttestationKindNotYetSupportedError check runs at the handler
    # tier before the decider sees the command, so we can assume
    # ChecksumVerified here.
    if kind is not AttestationKind.CHECKSUM_VERIFIED:
        # Defensive guard: the handler tier should have rejected
        # non-ChecksumVerified kinds before reaching the decider; if a
        # test bypasses the handler we raise the same NotYetSupported
        # error rather than fall through to a half-built evidence path.
        from cora.data.aggregates.attestation import (
            AttestationKindNotYetSupportedError,
        )

        raise AttestationKindNotYetSupportedError(kind.value)

    evidence = ChecksumVerifiedEvidence(
        expected_checksum=command.evidence_expected_checksum,
        computed_checksum=command.evidence_computed_checksum,
        algorithm=command.evidence_algorithm,
        verifier_supply_id=command.evidence_verifier_supply_id,
        verifier_kind=command.evidence_verifier_kind,
        error_detail=command.evidence_error_detail,
    )

    # Step 8: outcome-evidence cross-validation. The ChecksumVerified
    # arm requires computed_checksum non-None on Match/Mismatch and
    # None on Unreachable. The matching error_detail invariant is the
    # mirror (Unreachable MUST carry an error_detail; Match/Mismatch
    # SHOULD NOT but are not gated since a verifier may carry context
    # on either outcome for forensic purposes).
    if outcome is AttestationOutcome.MATCH and evidence.computed_checksum is None:
        raise InvalidAttestationEvidenceError(
            "outcome=Match requires evidence.computed_checksum to be non-None"
        )
    if outcome is AttestationOutcome.MISMATCH and evidence.computed_checksum is None:
        raise InvalidAttestationEvidenceError(
            "outcome=Mismatch requires evidence.computed_checksum to be non-None"
        )
    if outcome is AttestationOutcome.UNREACHABLE:
        if evidence.computed_checksum is not None:
            raise InvalidAttestationEvidenceError(
                "outcome=Unreachable requires evidence.computed_checksum to be None"
            )
        if evidence.error_detail is None:
            raise InvalidAttestationEvidenceError(
                "outcome=Unreachable requires evidence.error_detail to be non-None"
            )

    # Step 9: State-is-None genesis guard.
    if state is not None:
        raise AttestationAlreadyExistsError(state.id)

    # Step 12: Distribution.dataset_id equality (only when a Distribution
    # was loaded; the handler enforces the distribution_id-set ->
    # context.distribution-non-None contract).
    if context.distribution is not None:
        if context.distribution.dataset_id != context.dataset.id:
            raise AttestationDistributionDatasetMismatchError(
                distribution_id=context.distribution.id,
                expected_dataset_id=context.dataset.id,
                actual_dataset_id=context.distribution.dataset_id,
            )
        # Step 12b: refuse to verify a directory (sha256-tree) Distribution.
        # The shipped verifier hashes a whole file; a tree digest is a
        # manifest hash, so whole-file evidence would Match-fail (caught
        # below) on Match but, worse, record a false Mismatch on
        # outcome=Mismatch, flipping the Distribution to Stale. Refuse
        # outright until the directory ChecksumVerifier ships (deferred).
        if context.distribution.checksum.algorithm == DATASET_CHECKSUM_ALGORITHM_SHA256_TREE:
            raise AttestationTreeChecksumNotYetSupportedError(
                distribution_id=context.distribution.id,
                algorithm=context.distribution.checksum.algorithm,
            )
        # Step 13: belt-and-braces checksum comparison. Only meaningful
        # for ChecksumVerified Match (false-Match is the downstream-
        # visible failure mode; false-Mismatch is operator-visible but
        # does not silently flip Distribution.status to Verified).
        if (
            outcome is AttestationOutcome.MATCH
            and evidence.computed_checksum != context.distribution.checksum.value
        ):
            raise AttestationChecksumEvidenceMismatchError(
                distribution_id=context.distribution.id,
                canonical_checksum=context.distribution.checksum.value,
                evidence_checksum=evidence.computed_checksum,
            )

    # Step 15: emit AttestationRecorded with primitives on the payload.
    return [
        AttestationRecorded(
            attestation_id=new_id,
            dataset_id=command.dataset_id,
            distribution_id=command.distribution_id,
            kind=kind.value,
            outcome=outcome.value,
            evidence=build_checksum_verified_evidence_payload(evidence),
            occurred_at=now,
            attested_by=attested_by,
        )
    ]
