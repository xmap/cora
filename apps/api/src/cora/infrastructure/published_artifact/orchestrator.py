"""Verify-then-apply orchestrator for federated PublishedArtifact.

The orchestrator is the Generic Subdomain shared-kernel coordinator
that runs the 13-stage verification sequence per
project_federation_port_design.md. It composes:

  - BEFORE-gates: payload_type_trusted, content_hash, required-receipt
    presence (run synchronously; short-circuit Rejected on hard fails)
  - Arm-specific stages delegated to `SignaturePort.verify(...)`:
    signature, key_resolution, issuer_match,
    transparency_log_inclusion (per-arm), key_validity_at_sign_time
  - AFTER-gates: payload_type_known (deferred), abi_tier, expires_at,
    head_pointer_fresh (deferred), replay_cache (deferred), dco_chain

The orchestrator does NOT consult the EventStore, does NOT apply
the artifact to any home aggregate, and does NOT acquire any
locks. Application is the caller's responsibility: the per-BC
`pull_<artifact>` slice handler reads the orchestrator's return,
short-circuits on Rejected / Unverifiable, and append_streams
the matching `<Artifact>Imported` event on Verified.

Per AH#17 (TOCTOU defense): the `PullPort` adapter is responsible
for raising `FederationPublicationContentDriftError` BEFORE the
artifact reaches the orchestrator. The orchestrator's
`content_hash` stage is the defense-in-depth recompute when the
pull adapter did not.

Per arch-2 (SignaturePort delegates to ByteSigner): this
orchestrator delegates the arm-specific stages to
`SignaturePort.verify`. It NEVER invokes a crypto library
directly; the matching adapter under
`cora/federation/adapters/<family>_signature_port.py` calls
ByteSigner.sign/verify.
"""

from datetime import datetime

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.ports.canonicalizer import (
    UnsupportedCanonicalizationVersionError,
)
from cora.infrastructure.ports.federation.signature_port import SignaturePort
from cora.infrastructure.ports.federation.value_types import (
    FederationTrustContext,
    PublishedArtifact,
    Rejected,
    RejectionReason,
    StageResult,
    UnverifiabilityReason,
    Unverifiable,
    VerificationOutcome,
    Verified,
)
from cora.infrastructure.published_artifact._stages import (
    check_abi_tier,
    check_content_hash,
    check_dco_chain,
    check_expires_at,
    check_payload_type_trusted,
    check_required_receipts_present,
    deferred_stage,
)


async def verify_then_apply(
    artifact: PublishedArtifact,
    *,
    trust_context: FederationTrustContext,
    signature_port: SignaturePort,
    canonicalization_registry: CanonicalizationRegistry,
    now: datetime,
) -> VerificationOutcome:
    """Run the 13-stage verification sequence; return a VerificationOutcome.

    Caller composes the routing (which SignaturePort adapter to use
    for the artifact's envelope kind) and resolves the trust context
    from the matching inbound-direction Permit. The orchestrator
    runs the stages in order, short-circuits on hard fails, and
    returns the synthesized outcome. The caller's pull-slice handler
    decides whether to apply the artifact (on Verified) or surface a
    diagnostic (on Rejected / Unverifiable).
    """
    stage_results: list[StageResult] = []

    payload_type_result = check_payload_type_trusted(artifact, trust_context)
    stage_results.append(payload_type_result)
    if payload_type_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(
                failed_stage="payload_type_trusted",
                reason=payload_type_result.detail,
            ),
        )

    try:
        canonicalization_adapter = canonicalization_registry.resolve(
            artifact.canonicalization_version
        )
    except UnsupportedCanonicalizationVersionError as exc:
        stage_results.append(
            StageResult(
                stage="content_hash",
                outcome="skip",
                detail=(
                    f"canonicalization_version "
                    f"{artifact.canonicalization_version!r} not registered: {exc}"
                ),
            )
        )
        return Unverifiable(
            stage_results=tuple(stage_results),
            unverifiability=UnverifiabilityReason(
                failed_stage="content_hash",
                reason="canonicalization adapter not registered",
            ),
        )

    content_hash_result = check_content_hash(artifact, canonicalization_adapter)
    stage_results.append(content_hash_result)
    if content_hash_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(
                failed_stage="content_hash",
                reason=content_hash_result.detail,
            ),
        )

    receipt_result = check_required_receipts_present(artifact.signature_envelope, trust_context)
    stage_results.append(receipt_result)
    if receipt_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(
                failed_stage="transparency_log_inclusion",
                reason=receipt_result.detail,
            ),
        )

    arm_outcome = await signature_port.verify(artifact, trust_context)
    stage_results.extend(arm_outcome.stage_results)
    if isinstance(arm_outcome, Rejected):
        return Rejected(stage_results=tuple(stage_results), rejection=arm_outcome.rejection)
    if isinstance(arm_outcome, Unverifiable):
        return Unverifiable(
            stage_results=tuple(stage_results), unverifiability=arm_outcome.unverifiability
        )

    stage_results.append(
        deferred_stage(
            "payload_type_known",
            "payload-type plugin registry deferred; treat as skip until per-BC slices land",
        )
    )

    abi_tier_result = check_abi_tier(artifact, trust_context)
    stage_results.append(abi_tier_result)
    if abi_tier_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(failed_stage="abi_tier", reason=abi_tier_result.detail),
        )

    expires_at_result = check_expires_at(artifact, now=now)
    stage_results.append(expires_at_result)
    if expires_at_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(failed_stage="expires_at", reason=expires_at_result.detail),
        )

    stage_results.append(
        deferred_stage(
            "head_pointer_fresh",
            "Seal head-pointer freshness check deferred to a future iteration",
        )
    )
    stage_results.append(
        deferred_stage(
            "replay_cache",
            "replay cache deferred to a future iteration",
        )
    )

    dco_chain_result = check_dco_chain(artifact)
    stage_results.append(dco_chain_result)
    if dco_chain_result.outcome == "fail":
        return Rejected(
            stage_results=tuple(stage_results),
            rejection=RejectionReason(failed_stage="dco_chain", reason=dco_chain_result.detail),
        )

    return Verified(stage_results=tuple(stage_results))


__all__ = ["verify_then_apply"]
