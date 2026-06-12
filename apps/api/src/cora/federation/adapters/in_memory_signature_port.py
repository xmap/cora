"""In-memory SignaturePort adapter for tests and dev fixtures.

Dict-backed, no crypto. Test entry verbs:

  - `set_verification_outcome(content_hash, outcome)`: prime a
    `VerificationOutcome` to return on the next `verify(artifact, ...)`
    call whose `artifact.content_hash` matches.
  - `simulate_signature_invalid(content_hash, failed_stage)`: next
    `verify` for an artifact with that content_hash returns a
    `Rejected` outcome carrying the named failed stage.
  - `set_sign_envelope(canonicalization_version, envelope)`: prime
    a fresh envelope to return on `sign(canonicalized, ...)` when
    `canonicalized.adapter_version` matches.

Note on the arch-2 delegation invariant: the IN-MEMORY adapter
does NOT need a ByteSigner instance because it does no crypto;
it returns canned outcomes for testing. The architecture-fitness
test `test_signature_port_delegates_to_signing_port.py` (lands at
the same time as the first wire-tier adapter) walks PRODUCTION
adapters under `cora/federation/adapters/<family>_signature_port.py`,
not this in-memory test fixture.
"""

import contextlib

from cora.infrastructure.ports.canonicalizer import CanonicalizedBytes
from cora.infrastructure.ports.federation import (
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    PublishedArtifact,
    Rejected,
    RejectionReason,
    SignatureEnvelope,
    StageName,
    StageResult,
    VerificationOutcome,
    Verified,
)


class InMemorySignaturePort:
    """Dict-backed SignaturePort with simulate_* test entry points.

    Default verify outcome is `Verified` with all stages passing;
    `simulate_signature_invalid` flips that for specific
    content_hashes. Default sign outcome is a placeholder
    `DsseStaticJwksEnvelope`; `set_sign_envelope` overrides per
    canonicalization version.
    """

    def __init__(self) -> None:
        self._verification_outcomes: dict[bytes, VerificationOutcome] = {}
        self._sign_envelopes: dict[str, SignatureEnvelope] = {}

    async def verify(
        self,
        artifact: PublishedArtifact,
        trust_context: FederationTrustContext,
    ) -> VerificationOutcome:
        _ = trust_context
        primed = self._verification_outcomes.get(artifact.content_hash)
        if primed is not None:
            return primed
        return Verified(
            stage_results=(
                StageResult(stage="content_hash", outcome="pass"),
                StageResult(stage="signature", outcome="pass"),
            )
        )

    async def sign(
        self,
        canonicalized: CanonicalizedBytes,
        trust_context: FederationTrustContext,
    ) -> SignatureEnvelope:
        _ = trust_context
        primed = self._sign_envelopes.get(canonicalized.adapter_version)
        if primed is not None:
            return primed
        return DsseStaticJwksEnvelope(
            signing_version=canonicalized.adapter_version,
            payload_bytes=b"in-memory-signature-over:" + canonicalized.bytes_,
        )

    def set_verification_outcome(self, content_hash: bytes, outcome: VerificationOutcome) -> None:
        self._verification_outcomes[content_hash] = outcome

    def simulate_signature_invalid(self, content_hash: bytes, failed_stage: StageName) -> None:
        self._verification_outcomes[content_hash] = Rejected(
            stage_results=(StageResult(stage=failed_stage, outcome="fail"),),
            rejection=RejectionReason(
                failed_stage=failed_stage,
                reason="in-memory simulate_signature_invalid",
            ),
        )

    def set_sign_envelope(self, canonicalization_version: str, envelope: SignatureEnvelope) -> None:
        self._sign_envelopes[canonicalization_version] = envelope

    def clear_simulations(self) -> None:
        self._verification_outcomes.clear()
        self._sign_envelopes.clear()

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            self._verification_outcomes.clear()
            self._sign_envelopes.clear()


__all__ = ["InMemorySignaturePort"]
