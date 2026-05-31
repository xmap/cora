"""Generic Subdomain shared-kernel for verify-then-apply on federation artifacts.

The verify-then-apply orchestrator at
`cora.infrastructure.published_artifact.orchestrator` is the
Generic Subdomain coordinator that the Federation BC and every
per-BC pull slice consume. It composes BEFORE-gates, the
arm-specific SignaturePort.verify dispatch, and AFTER-gates
into a single VerificationOutcome.

Per project_federation_port_design.md the orchestrator does not
apply the artifact; the caller's per-BC pull-slice handler reads
the outcome and either appends the matching `<Artifact>Imported`
event (on Verified) or surfaces a diagnostic to the operator (on
Rejected / Unverifiable).
"""

from cora.infrastructure.published_artifact._stages import (
    check_abi_tier,
    check_content_hash,
    check_dco_chain,
    check_expires_at,
    check_payload_type_trusted,
    check_required_receipts_present,
    dco_chain_has_human_actor,
    deferred_stage,
    is_terminal_publication_status,
)
from cora.infrastructure.published_artifact.orchestrator import verify_then_apply

__all__ = [
    "check_abi_tier",
    "check_content_hash",
    "check_dco_chain",
    "check_expires_at",
    "check_payload_type_trusted",
    "check_required_receipts_present",
    "dco_chain_has_human_actor",
    "deferred_stage",
    "is_terminal_publication_status",
    "verify_then_apply",
]
