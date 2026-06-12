"""ChecksumVerifier: Data BC's per-distribution byte-integrity port.

Used by the ``record_attestation`` handler to compute a checksum over
a Distribution's bytes at its declared URI, returning a discriminated
result the decider translates into ``AttestationOutcome`` plus
``ChecksumVerifiedEvidence``. The port encapsulates the
scheme-specific transport (HTTP range-read, POSIX mmap, Globus
server-side, S3 ETag, ...); the handler dispatches on
``Distribution.uri`` scheme to the registered adapter.

## Convention

Single-consumer per-BC port (Data BC owns; Data BC only consumer).
Lives at ``cora.data.ports.checksum_verifier`` per the per-BC port
location convention. Multiple test stubs ship alongside the Protocol
so unit and contract tests can dial in specific outcomes without
spinning up the real adapter.

## Discriminated result

The port returns a discriminated dataclass union
(``Match | Mismatch | Unreachable``) rather than a (outcome, value)
tuple. This makes the "Match must carry a computed_checksum;
Unreachable must NOT" invariant a type-checker concern at every call
site that pattern-matches on the result, rather than a runtime check
the handler has to duplicate.

## Rule-of-three

Today ships one adapter (``HttpRangeChecksumAdapter``). Generalization
of the port to a multi-scheme dispatcher waits until the 3rd adapter
lands per [[feedback_port_generalization_trigger]] (POSIX-mmap +
Globus server-side + S3-ETag are the likely next three).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class Match:
    """Verifier completed AND the observed value byte-equals the expected.

    Carries the computed checksum so the decider can perform the
    belt-and-braces consistency check against the Distribution row.
    """

    computed_checksum: str


@dataclass(frozen=True)
class Mismatch:
    """Verifier completed AND the observed value disagrees with the expected.

    Carries the computed checksum so the operator-facing forensic
    record shows WHAT the bytes actually digested to (that IS the
    value of recording a Mismatch).
    """

    computed_checksum: str


@dataclass(frozen=True)
class Unreachable:
    """Verifier could not complete (transport timeout, 5xx, missing credentials).

    Distinct from ``Mismatch`` because the bytes' integrity is
    unknown, not refuted. Carries an ``error_detail`` human-readable
    summary the operator-facing UI surfaces and the projection writer
    leaves the Distribution status alone (transient).
    """

    error_detail: str


ChecksumVerificationResult = Match | Mismatch | Unreachable


class ChecksumVerifier(Protocol):
    """Data BC port: compute a checksum over a Distribution's bytes."""

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        """Walk the bytes at ``distribution_uri`` and return the verification result.

        Implementations MUST:

          - Compute sha256 over the byte stream (today's only supported
            algorithm).
          - Return ``Match(computed_checksum=...)`` when computed
            equals expected.
          - Return ``Mismatch(computed_checksum=...)`` when computed
            differs from expected.
          - Return ``Unreachable(error_detail=...)`` on any I/O error
            (timeout, 5xx, missing credentials, malformed URI). They
            MUST NOT raise on transport errors; the handler converts
            ``Unreachable`` into an ``AttestationOutcome.UNREACHABLE``
            recorded fact.

        ``supply_id`` is passed through to the implementation for
        forensic logging; some adapters resolve credentials per Supply.
        """
        ...


class ChecksumVerifierUnsupportedSchemeError(Exception):
    """Raised by the handler when no adapter is registered for a URI scheme.

    Today only HTTPS is supported (``HttpRangeChecksumAdapter``); a
    ``globus://`` or ``s3://`` URI lands here until those adapters
    ship. Lifts to HTTP 400 per the handler-tier
    ``Invalid<X>`` family.
    """

    def __init__(self, scheme: str) -> None:
        super().__init__(f"No ChecksumVerifier adapter registered for URI scheme {scheme!r}")
        self.scheme = scheme


class AlwaysMatchingChecksumVerifier:
    """Test stub: every ``verify`` call returns ``Match(expected_checksum)``."""

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        _ = distribution_uri, supply_id
        return Match(computed_checksum=expected_checksum)


class AlwaysMismatchingChecksumVerifier:
    """Test stub: every ``verify`` call returns ``Mismatch`` with a fixed digest.

    The fixed digest differs from any plausible ``expected_checksum``
    a caller might pass (64 ``f`` chars). Tests that need a specific
    mismatch shape use ``ConfiguredChecksumVerifier``.
    """

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        _ = distribution_uri, expected_checksum, supply_id
        return Mismatch(computed_checksum="f" * 64)


class AlwaysUnreachableChecksumVerifier:
    """Test stub: every ``verify`` call returns ``Unreachable``."""

    def __init__(self, error_detail: str = "stub: always unreachable") -> None:
        self._error_detail = error_detail

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        _ = distribution_uri, expected_checksum, supply_id
        return Unreachable(error_detail=self._error_detail)


class ConfiguredChecksumVerifier:
    """Test stub: returns a per-URI configured outcome.

    Construct with a mapping ``{distribution_uri: result}``; unmapped
    URIs raise ``KeyError`` (loud surface for test misconfiguration).
    """

    def __init__(self, configured_results: dict[str, ChecksumVerificationResult]) -> None:
        self._configured = dict(configured_results)

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        _ = expected_checksum, supply_id
        return self._configured[distribution_uri]


__all__ = [
    "AlwaysMatchingChecksumVerifier",
    "AlwaysMismatchingChecksumVerifier",
    "AlwaysUnreachableChecksumVerifier",
    "ChecksumVerificationResult",
    "ChecksumVerifier",
    "ChecksumVerifierUnsupportedSchemeError",
    "ConfiguredChecksumVerifier",
    "Match",
    "Mismatch",
    "Unreachable",
]
