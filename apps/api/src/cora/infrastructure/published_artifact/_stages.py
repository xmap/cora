"""Verifier stage helpers: pure functions, one per non-arm-specific gate.

The verify-then-apply orchestrator at
`cora.infrastructure.published_artifact.orchestrator` composes
these helpers around the arm-specific SignaturePort.verify call.
Each helper returns a StageResult so the orchestrator can build
the final `VerificationOutcome.stage_results` tuple without
re-implementing the per-stage shape.

Closed-set semantics on every helper:
  - "pass" means the gate evaluated and accepted
  - "fail" means the gate evaluated and rejected (rejection path)
  - "skip" means the gate could not run (unverifiable path) OR
    is deferred to a future iteration

`detail` carries forensics for operator logs; never parsed by
callers per the ControlPort `Reading.quality_detail` precedent.
"""

from datetime import datetime

from cora.infrastructure.ports.canonicalizer import (
    CanonicalizationFailedError,
    Canonicalizer,
)
from cora.infrastructure.ports.federation.value_types import (
    DcoEntry,
    FederationTrustContext,
    PublicationStatus,
    PublishedArtifact,
    Receipt,
    SignatureEnvelope,
    SignedOffBy,
    StageResult,
)

_ABI_TIER_ORDER: dict[str, int] = {
    "Testing": 1,
    "Stable": 2,
    "Obsolete": 3,
    "Removed": 4,
}


def check_payload_type_trusted(
    artifact: PublishedArtifact, trust_context: FederationTrustContext
) -> StageResult:
    """Pass when `artifact.payload_type` is in the trust context's allowlist."""
    if not trust_context.allowed_payload_types:
        return StageResult(
            stage="payload_type_trusted",
            outcome="fail",
            detail="trust context allowed_payload_types is empty",
        )
    if artifact.payload_type in trust_context.allowed_payload_types:
        return StageResult(stage="payload_type_trusted", outcome="pass")
    return StageResult(
        stage="payload_type_trusted",
        outcome="fail",
        detail=(
            f"payload_type={artifact.payload_type!r} not in trust context "
            f"allowed set of size {len(trust_context.allowed_payload_types)}"
        ),
    )


def check_content_hash(
    artifact: PublishedArtifact, canonicalization_adapter: Canonicalizer
) -> StageResult:
    """Recompute the content hash via the matching canonicalization adapter.

    Returns `pass` when the recomputed hash equals the claimed one
    (encoded as hex against `artifact.content_hash.hex()`). Returns
    `fail` on mismatch; `skip` if the canonicalization payload is
    not derivable from the port-tier shape (placeholder: the v1
    orchestrator does not yet rehydrate payload from canonical_bytes;
    that work lands when the per-BC pull slice ships).
    """
    if not artifact.canonical_bytes:
        return StageResult(
            stage="content_hash",
            outcome="skip",
            detail="artifact carries no canonical_bytes; content-hash recompute deferred",
        )
    try:
        recomputed_hex = _hash_bytes(artifact.canonical_bytes)
    except CanonicalizationFailedError as exc:
        return StageResult(
            stage="content_hash",
            outcome="skip",
            detail=f"canonicalization adapter raised: {exc}",
        )
    if canonicalization_adapter.adapter_version != artifact.canonicalization_version:
        return StageResult(
            stage="content_hash",
            outcome="skip",
            detail=(
                f"canonicalization adapter version "
                f"{canonicalization_adapter.adapter_version!r} does not match "
                f"artifact canonicalization_version {artifact.canonicalization_version!r}; "
                f"orchestrator must resolve a matching adapter before calling"
            ),
        )
    claimed_hex = artifact.content_hash.hex()
    if recomputed_hex == claimed_hex:
        return StageResult(stage="content_hash", outcome="pass")
    return StageResult(
        stage="content_hash",
        outcome="fail",
        detail=f"claimed={claimed_hex} recomputed={recomputed_hex}",
    )


def check_required_receipts_present(
    envelope: SignatureEnvelope, trust_context: FederationTrustContext
) -> StageResult:
    """Pass when every required receipt kind is present (or no requirements).

    Per sec-1 / AH#19: when `trust_context.required_receipt_kinds`
    is non-empty AND `envelope.receipts` does not contain at least
    one of each required kind, the verifier rejects. Empty
    `required_receipt_kinds` (the default) is the legitimate
    backward-compat path; receipts are validated when present but
    not required.
    """
    if not trust_context.required_receipt_kinds:
        return StageResult(stage="transparency_log_inclusion", outcome="skip")
    observed = {r.kind for r in envelope.receipts}
    missing = trust_context.required_receipt_kinds - observed
    if missing:
        return StageResult(
            stage="transparency_log_inclusion",
            outcome="fail",
            detail=(
                f"required receipt kinds {sorted(trust_context.required_receipt_kinds)!r} "
                f"missing {sorted(missing)!r}; observed {sorted(observed)!r}"
            ),
        )
    return StageResult(stage="transparency_log_inclusion", outcome="pass")


def check_abi_tier(
    artifact: PublishedArtifact, trust_context: FederationTrustContext
) -> StageResult:
    """Pass when artifact tier is at or above the trust-context floor.

    Order: Testing(1) < Stable(2) < Obsolete(3) < Removed(4).
    `Removed` always fails regardless of floor (publication has
    been formally withdrawn from the ABI ladder; adopting it would
    contradict the lifecycle).
    """
    if artifact.abi_tier == "Removed":
        return StageResult(
            stage="abi_tier",
            outcome="fail",
            detail="artifact abi_tier=Removed; publication has been withdrawn",
        )
    artifact_rank = _ABI_TIER_ORDER.get(artifact.abi_tier)
    floor_rank = _ABI_TIER_ORDER.get(trust_context.abi_tier_floor)
    if artifact_rank is None or floor_rank is None:
        return StageResult(
            stage="abi_tier",
            outcome="skip",
            detail=(
                f"unrecognized abi_tier: artifact={artifact.abi_tier!r} "
                f"floor={trust_context.abi_tier_floor!r}"
            ),
        )
    if artifact_rank >= floor_rank:
        return StageResult(stage="abi_tier", outcome="pass")
    return StageResult(
        stage="abi_tier",
        outcome="fail",
        detail=(
            f"artifact abi_tier={artifact.abi_tier!r} below trust "
            f"context floor={trust_context.abi_tier_floor!r}"
        ),
    )


def check_expires_at(artifact: PublishedArtifact, *, now: datetime) -> StageResult:
    """Pass when artifact is not expired (or has no expiry)."""
    if artifact.expires_at is None:
        return StageResult(stage="expires_at", outcome="pass")
    if now < artifact.expires_at:
        return StageResult(stage="expires_at", outcome="pass")
    return StageResult(
        stage="expires_at",
        outcome="fail",
        detail=(f"artifact expired at {artifact.expires_at.isoformat()}; now={now.isoformat()}"),
    )


def check_dco_chain(artifact: PublishedArtifact) -> StageResult:
    """Pass when at least one SignedOffBy entry is present in the DCO chain.

    Per project_federation_port_design.md: the Linux-kernel
    `coding-assistants.rst` invariant transplant requires at least
    one human Signed-off-by. The decider enforces the deeper
    invariant (actor_id resolves to Actor.kind == human) at
    publish-time; this gate checks the chain shape at verify-time.
    """
    if not artifact.dco_chain:
        return StageResult(
            stage="dco_chain",
            outcome="fail",
            detail="DCO chain is empty; missing required SignedOffBy entry",
        )
    has_signed_off_by = any(isinstance(entry, SignedOffBy) for entry in artifact.dco_chain)
    if has_signed_off_by:
        return StageResult(stage="dco_chain", outcome="pass")
    return StageResult(
        stage="dco_chain",
        outcome="fail",
        detail=(
            f"DCO chain has {len(artifact.dco_chain)} entries but no "
            f"SignedOffBy; AI-only chains are forbidden"
        ),
    )


def deferred_stage(stage_name: str, reason: str) -> StageResult:
    """Build a skip StageResult for a stage deferred to a future iteration.

    Centralized so a future iteration that lands the deferred
    infrastructure (head pointer cache, replay cache, payload-type
    plugin registry) can promote each from skip to pass/fail via
    a single import-site update.
    """
    return StageResult(stage=stage_name, outcome="skip", detail=reason)  # type: ignore[arg-type]


def is_envelope_receipt_kind(receipt: Receipt, kind: str) -> bool:
    """Helper used by the orchestrator when filtering receipt arms."""
    return receipt.kind == kind


def dco_chain_has_human_actor(entries: tuple[DcoEntry, ...]) -> bool:
    """Helper exposed for the per-BC publish-slice deciders to reuse."""
    return any(isinstance(e, SignedOffBy) for e in entries)


def is_terminal_publication_status(status: PublicationStatus) -> bool:
    """Helper for adoption-window gating once head_pointer_fresh lands."""
    return status in ("Yanked", "Withdrawn", "Expired", "AbiTierObsoleteOrRemoved")


def _hash_bytes(canonical_bytes: bytes) -> str:
    """Sha256 hex of canonical_bytes; isolated so the verifier reuses one path."""
    import hashlib

    return hashlib.sha256(canonical_bytes).hexdigest()


__all__ = [
    "check_abi_tier",
    "check_content_hash",
    "check_dco_chain",
    "check_expires_at",
    "check_payload_type_trusted",
    "check_required_receipts_present",
    "dco_chain_has_human_actor",
    "deferred_stage",
    "is_envelope_receipt_kind",
    "is_terminal_publication_status",
]
