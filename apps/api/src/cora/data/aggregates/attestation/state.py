"""Attestation aggregate state, value objects, status enum, and domain errors.

An ``Attestation`` is a recorded fact about a ``Dataset`` (always) and
optionally a specific ``Distribution`` byte-copy. Each Attestation is
its own stream (one event ever per stream: ``AttestationRecorded``);
the aggregate is terminal-at-genesis with a single FSM state.

## What an Attestation is

  - A statement that some property of a Dataset (and possibly a
    specific Distribution byte-copy) was observed at a moment by an
    actor (verifier-port-driven or operator-initiated).
  - Carries a closed ``AttestationKind`` (what was checked) plus a
    closed ``AttestationOutcome`` (Match / Mismatch / Unreachable)
    plus a discriminated ``AttestationEvidence`` value object whose
    shape varies by kind.

## What an Attestation is NOT

  - Not the bytes (the verifier reads bytes at the Distribution URI;
    the fact recorded here is the outcome, not the bytes themselves).
  - Not a Distribution status flip; the Distribution projection
    writer denormalizes the latest ``ChecksumVerified`` outcome to
    ``Distribution.status`` (Verified / Stale). This aggregate
    carries the underlying fact.
  - Not amendable; a flawed Attestation is corrected by recording a
    new Attestation (future W3 ``AttestationSuperseded`` may land if
    operators demand a corrective event).

## Dual binding gated by kind

Every Attestation carries BOTH a ``dataset_id`` (always required) and
a ``distribution_id`` (``UUID | None``). The kind decides which combo
is valid:

  - ``ChecksumVerified``, ``FormatValidated``, ``BitRotChecked`` ->
    ``distribution_id`` REQUIRED (these attest a specific byte copy).
  - ``ConformsToValidated`` -> ``distribution_id`` FORBIDDEN (a
    profile claim about the logical Dataset content, scope-orthogonal
    to any single byte-copy).

## Closed StrEnums day-one

``AttestationKind`` ships with all 4 values day-one; only
``ChecksumVerified`` is reachable in this slice (the other three
raise ``AttestationKindNotYetSupportedError`` at the handler tier).
``AttestationOutcome`` ships with all 3 values day-one. Closed
StrEnums avoid the additive-enum migration trap and lock the wire
shape day-one. ``AttestationStatus`` ships with one value
(``Recorded``); the StrEnum form is kept (not collapsed to a
constant) for symmetry with every other CORA aggregate per
[[project_lifecycle_status_naming]].
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.data.aggregates.dataset.state import (
    DATASET_CHECKSUM_ALGORITHM_SHA256,
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
)
from cora.shared.identity import ActorId

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

#: Maximum length for the ``verifier_kind`` provenance string inside
#: ``ChecksumVerifiedEvidence``. Bounded to keep payload sizes
#: predictable; verifier-kind strings are short adapter names
#: (e.g. ``"HttpRangeChecksum"``, ``"PosixMmapChecksum"``).
ATTESTATION_VERIFIER_KIND_MAX_LENGTH = 64

#: Maximum length for the ``error_detail`` field inside
#: ``ChecksumVerifiedEvidence`` (populated on ``Unreachable``).
ATTESTATION_ERROR_DETAIL_MAX_LENGTH = 500


# ----------------------------------------------------------------------
# Status enum (closed; 1 value day-one per L4)
# ----------------------------------------------------------------------


class AttestationStatus(StrEnum):
    """The Attestation's lifecycle state.

    Single value today (``Recorded``); the aggregate is terminal at
    genesis. Future W3 widening (``Superseded`` after a corrective
    Attestation lands) would land additively. Kept as a StrEnum
    (not a constant) for symmetry with every other CORA aggregate
    per [[project_lifecycle_status_naming]].

    Member name SCREAMING_SNAKE per Python ``StrEnum`` / PEP 8;
    string value PascalCase per CORA's BC-status-vocabulary fitness
    expectation.
    """

    RECORDED = "Recorded"


# ----------------------------------------------------------------------
# AttestationKind enum (closed; 4 values day-one per L5)
# ----------------------------------------------------------------------


class AttestationKind(StrEnum):
    """What property of a Dataset / Distribution was attested.

    Closed StrEnum with all 4 values day-one to lock the wire shape
    and avoid additive-enum migration. Only ``ChecksumVerified`` is
    reachable today; the other three trigger
    ``AttestationKindNotYetSupportedError`` at the handler tier.

    Member name SCREAMING_SNAKE; string value PascalCase.
    """

    CHECKSUM_VERIFIED = "ChecksumVerified"
    FORMAT_VALIDATED = "FormatValidated"
    CONFORMS_TO_VALIDATED = "ConformsToValidated"
    BIT_ROT_CHECKED = "BitRotChecked"


# ----------------------------------------------------------------------
# AttestationOutcome enum (closed; 3 values day-one per L6)
# ----------------------------------------------------------------------


class AttestationOutcome(StrEnum):
    """The outcome of a verifier run.

    Closed StrEnum with all 3 values day-one. Other outcomes (Pending,
    Partial, Error) are exception-shaped failures, not recorded
    outcomes.

      - ``Match``: verifier completed AND observed value byte-equals
        the canonical value.
      - ``Mismatch``: verifier completed AND observed value disagrees
        with the canonical value.
      - ``Unreachable``: verifier could not complete (transport
        timeout, 5xx, missing credentials). Distinct from
        ``Mismatch`` because bytes' integrity is unknown, not
        refuted.
    """

    MATCH = "Match"
    MISMATCH = "Mismatch"
    UNREACHABLE = "Unreachable"


# ----------------------------------------------------------------------
# Error classes (per L13 don't-hoist convention; per-BC isinstance)
# ----------------------------------------------------------------------


class InvalidAttestationKindError(Exception):
    """Raised when an ``AttestationKind`` value is outside the closed enum.

    Defensive decider-side re-check for in-process callers bypassing
    the Pydantic boundary; also raised by ``AttestationKind``
    reconstruction inside ``from_stored`` and wrapped as
    ``MalformedAttestationRecorded``.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid AttestationKind value {value!r}: "
            f"not in {sorted(k.value for k in AttestationKind)!r}"
        )
        self.value = value


class InvalidAttestationOutcomeError(Exception):
    """Raised when an ``AttestationOutcome`` value is outside the closed enum."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid AttestationOutcome value {value!r}: "
            f"not in {sorted(o.value for o in AttestationOutcome)!r}"
        )
        self.value = value


class InvalidAttestationEvidenceError(Exception):
    """Raised when a ``ChecksumVerifiedEvidence`` value fails validation.

    Covers algorithm, expected/computed checksum shape, verifier-supply
    identity, verifier-kind text, and error-detail bounds. The
    outcome-evidence cross-validation lives on the decider; this
    class is the VO-shape error.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Attestation evidence: {reason}")
        self.reason = reason


class AttestationKindNotYetSupportedError(Exception):
    """Raised when a command names a kind other than ``ChecksumVerified``.

    Handler-tier rejection: the kind value is well-formed (422 does
    not fire) but its evidence VO and adapter path are not yet
    implemented. 501 would imply "never going to support" which is
    wrong; 400 with a clear body is the operator-actionable shape.
    """

    def __init__(self, kind: str) -> None:
        super().__init__(
            f"AttestationKind {kind!r} is not yet supported; "
            "only 'ChecksumVerified' is implemented today."
        )
        self.kind = kind


class AttestationTreeChecksumNotYetSupportedError(Exception):
    """Raised when attesting a Distribution whose checksum is ``sha256-tree``.

    The shipped checksum verifier hashes a whole file; a directory
    (``sha256-tree``) Distribution's stored digest is a manifest hash, so
    whole-file evidence would spuriously Mismatch and flip the
    Distribution to ``Stale``. Recording is refused until the directory
    ChecksumVerifier ships (deferred). Like
    ``AttestationKindNotYetSupportedError`` this is a deferral, not a
    permanent rejection, so it lifts to HTTP 400 with an actionable body.
    """

    def __init__(self, distribution_id: UUID, algorithm: str) -> None:
        super().__init__(
            f"Distribution {distribution_id} has checksum algorithm {algorithm!r}, "
            "which the whole-file checksum verifier cannot verify; "
            "tree-checksum attestation is not yet supported."
        )
        self.distribution_id = distribution_id
        self.algorithm = algorithm


class AttestationDistributionNotFoundError(Exception):
    """Raised when ``command.distribution_id`` does not resolve.

    Data-BC-local class (mirrors ``DistributionSupplyNotFoundError``
    precedent). Lifts to HTTP 404. Only fires when ``distribution_id``
    is not None.
    """

    def __init__(self, distribution_id: UUID) -> None:
        super().__init__(
            f"Cannot record Attestation: distribution_id {distribution_id} does not exist"
        )
        self.distribution_id = distribution_id


class AttestationKindRequiresDistributionError(Exception):
    """Raised when the kind requires a ``distribution_id`` but the command omits it.

    Applies to ``ChecksumVerified``, ``FormatValidated``, and
    ``BitRotChecked``; each of these attests a specific byte-copy.
    Lifts to HTTP 409 per the ``Attestation.Cannot<Verb>`` family.
    """

    def __init__(self, kind: str) -> None:
        super().__init__(
            f"AttestationKind {kind!r} requires a distribution_id but none was provided"
        )
        self.kind = kind


class AttestationKindRejectsDistributionError(Exception):
    """Raised when the kind forbids a ``distribution_id`` but the command supplies one.

    Applies to ``ConformsToValidated`` only; the conforms-to claim is
    a property of the Dataset's logical content, not of any single
    byte-copy. Lifts to HTTP 409. Naming uses ``Rejects`` rather than
    ``Forbids`` to keep the verb form symmetric with the existing
    ``Requires`` half (Requires/Rejects pair).
    """

    def __init__(self, kind: str) -> None:
        super().__init__(f"AttestationKind {kind!r} forbids a distribution_id but one was provided")
        self.kind = kind


class AttestationDistributionDatasetMismatchError(Exception):
    """Raised when the loaded Distribution's parent Dataset disagrees with the command.

    Dual-binding invariant: every Attestation that names a Distribution
    must also name that Distribution's parent Dataset. Lifts to HTTP
    409.
    """

    def __init__(
        self,
        distribution_id: UUID,
        expected_dataset_id: UUID,
        actual_dataset_id: UUID,
    ) -> None:
        super().__init__(
            f"Attestation distribution_id {distribution_id} belongs to Dataset "
            f"{actual_dataset_id} but command declared dataset_id {expected_dataset_id}"
        )
        self.distribution_id = distribution_id
        self.expected_dataset_id = expected_dataset_id
        self.actual_dataset_id = actual_dataset_id


class AttestationChecksumEvidenceMismatchError(Exception):
    """Raised when verifier evidence contradicts the canonical Distribution checksum.

    Belt-and-braces consistency check (L10): fires when
    ``kind=ChecksumVerified`` AND ``outcome=Match`` but
    ``evidence.computed_checksum != loaded_distribution.checksum.value``
    (verifier-adapter bug producing a false Match). Lifts to HTTP
    409. The projection-side Distribution.status flip is
    downstream-visible, so a false Match must be caught at write time.
    """

    def __init__(
        self,
        distribution_id: UUID,
        canonical_checksum: str,
        evidence_checksum: str | None,
    ) -> None:
        super().__init__(
            f"Attestation evidence contradicts Distribution {distribution_id} canonical "
            f"checksum: canonical={canonical_checksum!r}, evidence={evidence_checksum!r}"
        )
        self.distribution_id = distribution_id
        self.canonical_checksum = canonical_checksum
        self.evidence_checksum = evidence_checksum


class AttestationAlreadyExistsError(Exception):
    """Raised when the Attestation stream at ``attestation_id`` is non-empty.

    Genesis-only same-stream-id guard. Strict-not-idempotent per L14:
    re-issuing the same ``attestation_id`` raises rather than silent
    no-op. Lifts to HTTP 409 (Aggregate-AlreadyExists family).
    """

    def __init__(self, attestation_id: UUID) -> None:
        super().__init__(f"Attestation {attestation_id} already exists")
        self.attestation_id = attestation_id


# ----------------------------------------------------------------------
# ChecksumVerifiedEvidence value object (per L8; only concrete arm today)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ChecksumVerifiedEvidence:
    """Discriminated evidence VO for ``AttestationKind.CHECKSUM_VERIFIED``.

    Carries the verifier adapter's report:

      - ``expected_checksum``: canonical 64-char lowercase sha256 hex.
        Forward-compatible with future algorithms; today only sha256
        is accepted (``algorithm == "sha256"``).
      - ``computed_checksum``: what the verifier actually computed.
        ``None`` ONLY when ``outcome == Unreachable`` (no digest to
        record); the decider enforces this cross-axis invariant.
      - ``algorithm``: today fixed to ``"sha256"``.
      - ``verifier_supply_id``: identifies the storage-supply (or other
        adapter-resident endpoint) the verifier walked. Forensic
        provenance.
      - ``verifier_kind``: short adapter name (e.g.
        ``"HttpRangeChecksum"``). Forensic provenance.
      - ``error_detail``: human-readable failure summary populated on
        ``Unreachable``; ``None`` otherwise. The decider checks the
        pairing.

    Field names use ``expected_checksum`` / ``computed_checksum``
    (rather than the on-disk-payload ``algorithm`` / ``value`` keys)
    because the in-memory VO is a richer dual-checksum record than
    the wire payload (the wire keeps ``algorithm`` plus a single
    ``value`` discriminated by ``outcome``; the in-memory VO keeps
    both halves for fold + invariant clarity).
    """

    expected_checksum: str
    computed_checksum: str | None
    algorithm: str
    verifier_supply_id: UUID
    verifier_kind: str
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if self.algorithm != DATASET_CHECKSUM_ALGORITHM_SHA256:
            raise InvalidAttestationEvidenceError(
                f"only {DATASET_CHECKSUM_ALGORITHM_SHA256!r} algorithm is supported today, "
                f"got {self.algorithm!r}"
            )
        _validate_sha256_hex(self.expected_checksum, "expected_checksum")
        if self.computed_checksum is not None:
            _validate_sha256_hex(self.computed_checksum, "computed_checksum")
        verifier_kind_trimmed = self.verifier_kind.strip()
        if not verifier_kind_trimmed:
            raise InvalidAttestationEvidenceError("verifier_kind empty or whitespace-only")
        if len(verifier_kind_trimmed) > ATTESTATION_VERIFIER_KIND_MAX_LENGTH:
            raise InvalidAttestationEvidenceError(
                f"verifier_kind exceeds {ATTESTATION_VERIFIER_KIND_MAX_LENGTH} chars"
            )
        object.__setattr__(self, "verifier_kind", verifier_kind_trimmed)
        if self.error_detail is not None:
            error_detail_trimmed = self.error_detail.strip()
            if not error_detail_trimmed:
                raise InvalidAttestationEvidenceError(
                    "error_detail empty or whitespace-only (use None for absence)"
                )
            if len(error_detail_trimmed) > ATTESTATION_ERROR_DETAIL_MAX_LENGTH:
                raise InvalidAttestationEvidenceError(
                    f"error_detail exceeds {ATTESTATION_ERROR_DETAIL_MAX_LENGTH} chars"
                )
            object.__setattr__(self, "error_detail", error_detail_trimmed)


def _validate_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != DATASET_CHECKSUM_SHA256_HEX_LENGTH:
        raise InvalidAttestationEvidenceError(
            f"{field_name} must be {DATASET_CHECKSUM_SHA256_HEX_LENGTH} hex chars, got {len(value)}"
        )
    if not all(c in "0123456789abcdef" for c in value):
        raise InvalidAttestationEvidenceError(f"{field_name} must be lowercase hex (0-9, a-f)")


#: Discriminated evidence union. Only the ChecksumVerified arm is
#: concrete today; future kinds add additional arms (each its own
#: future slice). The type alias provides a stable annotation site for
#: decider + handler + state plumbing.
AttestationEvidence = ChecksumVerifiedEvidence


# ----------------------------------------------------------------------
# Attestation aggregate root
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Attestation:
    """Aggregate root: one recorded fact about a Dataset (and optionally a Distribution).

    Frozen dataclass; all fields set-once at genesis (single
    ``AttestationRecorded`` event per stream). The aggregate is
    terminal at genesis; ``status`` is always ``Recorded``.

    Per [[project_fold_cost_principles]] slim-aggregate: per-Attestation
    streams are exactly one event long; state IS the event-folded
    value.

    Field shape:

      - ``id``: UUIDv7; stream id is the same UUID (no uuid5
        derivation).
      - ``dataset_id``: always required (every Attestation names its
        Dataset).
      - ``distribution_id``: required for byte-level kinds, None for
        ``ConformsToValidated``.
      - ``kind``: closed ``AttestationKind``.
      - ``outcome``: closed ``AttestationOutcome``.
      - ``evidence``: discriminated VO; today only
        ``ChecksumVerifiedEvidence`` is concrete.
      - ``attested_at`` / ``attested_by``: fold-symmetry attribution
        pair per [[project_fold_symmetry_design]].
      - ``status``: terminal at ``Recorded``; defaulted for symmetry
        with sibling aggregates.
    """

    id: UUID
    dataset_id: UUID
    distribution_id: UUID | None
    kind: AttestationKind
    outcome: AttestationOutcome
    evidence: AttestationEvidence
    attested_at: datetime
    attested_by: ActorId
    status: AttestationStatus = field(default=AttestationStatus.RECORDED)
