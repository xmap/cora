"""Commands for the ``record_attestation`` slice.

Two frozen dataclasses, because the operator's request and the decider's
input are now genuinely different shapes:

- ``RecordAttestation`` is the OPERATOR command (the boundary intent):
  "verify this Distribution and record the result". It carries only
  ``dataset_id`` + ``distribution_id`` + ``kind``. CORA computes the
  checksum itself, so the caller no longer asserts an outcome or any
  evidence. This is the command the idempotency wrapper hashes; it must
  stay free of the non-deterministic computed digest (a re-walk that
  produced different bytes must NOT look like a different request).

- ``AttestationRecordingInput`` is the DECIDER input: the operator intent
  PLUS the evidence CORA computed (outcome, computed checksum, the
  Distribution's expected checksum, the verifier provenance). The handler
  assembles it after calling the ChecksumVerifier port and hands it to the
  pure decider. Holding the evidence here (not on the operator command)
  keeps the decider pure and its invariants unchanged while moving the
  source of the digest from the caller to CORA.

"Record" rather than "register" or "define": the fact-act exists in the
world (the verifier walked the bytes and computed a digest) and we are
recording it. Mirrors [[project_asset_condition_design]] precedent
(degrade / fault / restore are acts-of-record).

## Strict-not-idempotent at same-stream-id

Per L14: same-stream-id re-issue raises ``AttestationAlreadyExistsError``.
No silent ``[]`` no-op. No cross-stream uniqueness constraint (multiple
Attestations for one tuple are first-class; nightly re-checks are
expected).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RecordAttestation:
    """Operator command: verify a Distribution's bytes and record the fact.

    Slim by design. CORA reads the Distribution's bytes via the
    ChecksumVerifier port, computes the digest, and derives the outcome +
    evidence; the caller does not supply them. Today only
    ``kind == "ChecksumVerified"`` is supported; other kinds raise
    ``AttestationKindNotYetSupportedError`` at the handler tier. For
    ``ChecksumVerified`` a ``distribution_id`` is required (there is no
    byte-copy to verify without one).
    """

    dataset_id: UUID
    distribution_id: UUID | None
    kind: str


@dataclass(frozen=True)
class AttestationRecordingInput:
    """Decider input: operator intent plus the evidence CORA computed.

    Assembled by the handler after the ChecksumVerifier port runs.
    ``evidence_expected_checksum`` is the Distribution's canonical value,
    ``evidence_computed_checksum`` is what the verifier digested (None on
    Unreachable), ``evidence_verifier_supply_id`` is the Supply whose bytes
    were walked, and ``evidence_verifier_kind`` names the adapter that
    computed it. The decider validates these and emits ``AttestationRecorded``.
    """

    dataset_id: UUID
    distribution_id: UUID | None
    kind: str
    outcome: str
    evidence_expected_checksum: str
    evidence_computed_checksum: str | None
    evidence_algorithm: str
    evidence_verifier_supply_id: UUID
    evidence_verifier_kind: str
    evidence_error_detail: str | None = None
