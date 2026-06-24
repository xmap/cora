"""Federation port-tier value types: domain-shaped, substrate-neutral.

These are the vocabulary the three federation ports (`PublishPort`,
`PullPort`, `SignaturePort`) speak in. None of the names here mention
DSSE, COSE, JWS, Sigstore, Fulcio, Rekor, SCITT, JWKS, or CBOR (per
anti-hooks #1 + #3): wire-tier vocabulary is owned by the adapters
under `cora/federation/adapters/*` and `cora/infrastructure/adapters/*`.

`abi_tier` is typed `str` at this tier for now; the closed-enum
`AbiTier(Testing | Stable | Obsolete | Removed)` lives at BC-tier in
`cora.federation.aggregates.permit.state.AbiTier` and will hoist to
this module in a follow-up iteration once the BC-tier import sites
are refactored (~9 files). The string discipline is documented but
not enforced at the port boundary today.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CredentialRef:
    """Opaque reference to a Federation BC `Credential` aggregate id.

    The verifier uses `credential_id` to look up the public-key
    material via the SecretStore-backed federation adapter. The port
    surface never carries raw key bytes, only the reference.
    """

    credential_id: UUID


@dataclass(frozen=True, slots=True)
class Receipt:
    """Transparency-log inclusion proof or COSE Receipt.

    Opaque at the port. `bytes_` is the raw receipt payload; the
    matching adapter (Sigstore/Rekor, SCITT, TS) parses and verifies
    it. The `kind` discriminator routes verification to the right
    receipt parser.
    """

    kind: Literal["scitt", "rekor_sct", "ts_authority"]
    bytes_: bytes


@dataclass(frozen=True, slots=True)
class DsseStaticJwksEnvelope:
    """SignatureEnvelope arm for DSSE + static JWKS adapter.

    The arm-specific payload fields are owned by Memo 2 (adapter
    design). At the port tier we only need the discriminator + the
    `signing_version` cross-tier link to the canonicalization
    recipe. `payload_bytes` is opaque to the port.
    """

    signing_version: str
    payload_bytes: bytes
    kind: Literal["dsse_static_jwks"] = "dsse_static_jwks"
    receipts: tuple[Receipt, ...] = ()


@dataclass(frozen=True, slots=True)
class DsseSigstoreKeylessEnvelope:
    """SignatureEnvelope arm for DSSE + Sigstore-keyless adapter."""

    signing_version: str
    payload_bytes: bytes
    kind: Literal["dsse_sigstore_keyless"] = "dsse_sigstore_keyless"
    receipts: tuple[Receipt, ...] = ()


@dataclass(frozen=True, slots=True)
class CoseSign1ScittEnvelope:
    """SignatureEnvelope arm for COSE_Sign1 + SCITT adapter."""

    signing_version: str
    payload_bytes: bytes
    kind: Literal["cose_sign1_scitt"] = "cose_sign1_scitt"
    receipts: tuple[Receipt, ...] = ()


SignatureEnvelope = DsseStaticJwksEnvelope | DsseSigstoreKeylessEnvelope | CoseSign1ScittEnvelope
"""Discriminated tagged union over `kind`. Consumers dispatch via
`isinstance` or by matching on `envelope.kind`. The three arms are
the locked v1 set per the memo; new arms expand the union and add a
new `kind` literal."""


@dataclass(frozen=True, slots=True)
class SignedOffBy:
    """Human Signed-off-by attribution; the only DCO arm that closes the chain.

    Per the Linux-kernel `coding-assistants.rst` invariant transplant,
    AI actors cannot Signed-off-by. The federation decider enforces
    that `actor_id` resolves to `Actor.kind == human`; an Agent
    actor_id raises `DcoChainMissingHumanSignoffError`.
    """

    actor_id: UUID
    signed_at: datetime


@dataclass(frozen=True, slots=True)
class AssistedBy:
    """AI contribution short of authorship.

    `model_ref` is a free-form string today; future iterations may
    restructure to a typed VO reusing the shipped `ModelRef`
    vocabulary in subscriber code. `citation` carries the prompt /
    decision-id provenance link.
    """

    agent_id: UUID
    model_ref: str
    assisted_at: datetime
    citation: str


@dataclass(frozen=True, slots=True)
class CoDevelopedBy:
    """Collaborative attribution between TWO HUMAN actors.

    Mirrors the Linux kernel `CO-DEVELOPED-BY` convention. Both
    `actor_id_a` and `actor_id_b` MUST resolve to `Actor.kind ==
    human`; Agent actor_ids raise `CoDevelopedByForbidsAgentError`
    at the decider.
    """

    actor_id_a: UUID
    actor_id_b: UUID
    co_developed_at: datetime


DcoEntry = SignedOffBy | AssistedBy | CoDevelopedBy
"""DCO chain entry discriminated union. The chain MUST contain at
least one `SignedOffBy` entry resolving to a human actor; AI agents
ride exclusively on `AssistedBy`."""


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    """Domain-shaped artifact ready to publish or verify.

    The port boundary carries everything a peer facility needs to
    verify the artifact end-to-end: the canonical bytes, the
    signature envelope, the canonicalization recipe identifier,
    the DCO chain, the ABI tier + lifecycle slots. No wire-tier
    vocabulary leaks through.

    `abi_tier` is `str` at this tier (see module docstring).
    `canonicalization_version` is the recipe identifier per
    [[project_canonicalization_port_design]]; the verifier
    dispatches to the matching adapter via
    `CanonicalizationRegistry.resolve(version)`.
    """

    content_hash: bytes
    canonical_bytes: bytes
    payload_type: str
    signature_envelope: SignatureEnvelope
    source_facility_id: UUID
    published_at: datetime
    expires_at: datetime | None
    abi_tier: str
    dco_chain: tuple[DcoEntry, ...]
    schema_version: int
    canonicalization_version: str


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Opaque pointer to a `PublishedArtifact` on a peer facility.

    Security-load-bearing equality is on `content_hash + payload_type`,
    NOT on `hint_locator`. The locator is the adapter's hint for how
    to reach the bytes (HTTP URL, IPFS CID, registry-prefix path);
    the verifier always recomputes the hash from the fetched bytes
    and rejects on drift via `FederationPublicationContentDriftError`.
    """

    content_hash: bytes
    payload_type: str
    source_facility_id: UUID
    hint_locator: str


@dataclass(frozen=True, slots=True)
class PublishReceipt:
    """Receipt the peer-facing PublishPort hands back on success.

    `receipt_bytes` is opaque at the port. The Federation BC's
    `record_receipt` slice persists it on the matching outbound-
    direction `Permit` for later third-party verification. The
    hints describe shape for diagnostics; no parsing required.
    """

    receipt_bytes: bytes
    receipt_format_hint: str
    transparency_log_hint: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class FetchProvenance:
    """Audit trail for a `PullPort.fetch` call.

    Captures what the adapter actually negotiated on the wire so
    replays can prove integrity beyond byte-content equality:
    the locator used (may differ from the reference's hint if the
    adapter rewrote), the wire content-type, fetch duration, byte
    count.
    """

    locator_used: str
    wire_content_type: str
    fetch_duration_ms: int
    byte_count: int


@dataclass(frozen=True, slots=True)
class PulledArtifact:
    """The verified artifact plus the provenance of how it arrived."""

    artifact: PublishedArtifact
    fetch_provenance: FetchProvenance


@dataclass(frozen=True, slots=True)
class FederationTrustContext:
    """Policy under which a federation verification runs.

    Composed at verify time from the matching inbound-direction
    `Permit` (per arch-7, the aggregate's `InboundTerms` variant
    carries flat fields, not a `FederationTrustContext` field, to
    avoid Permit -> FederationTrustContext -> Permit circular
    containment).

    `accept_yanked: Literal[False]` is structural: there is no
    `accept_expired` override, period (AH#19). The verifier never
    accepts a yanked publication; only an explicit `unyank`
    operator action restores it.

    `required_receipt_kinds` is the consumer-side floor for
    transparency-log evidence per arm; default empty for backward
    compat. When non-empty, the verifier raises
    `FederationReceiptMissingError` if `envelope.receipts` does
    not contain at least one receipt matching each required kind.
    """

    permit_id: UUID
    allowed_credentials: frozenset[CredentialRef]
    allowed_payload_types: frozenset[str]
    abi_tier_floor: str
    accept_yanked: Literal[False] = False
    required_receipt_kinds: frozenset[Literal["scitt", "rekor_sct", "ts_authority"]] = field(
        default_factory=lambda: frozenset[Literal["scitt", "rekor_sct", "ts_authority"]]()
    )


StageName = Literal[
    "payload_type_trusted",
    "content_hash",
    "signature",
    "key_resolution",
    "issuer_match",
    "transparency_log_inclusion",
    "key_validity_at_sign_time",
    "payload_type_known",
    "abi_tier",
    "expires_at",
    "head_pointer_fresh",
    "replay_cache",
    "dco_chain",
]
"""Closed enum of verifier stage names. Covers all three envelope arms;
new arms may add new stages at the end of the literal union."""


@dataclass(frozen=True, slots=True)
class StageResult:
    """Per-stage verification result.

    `outcome` is closed: pass | fail | skip. `detail` is opaque
    forensics; never parsed by callers (mirrors
    `Measurement.quality_detail` in ControlPort).
    """

    stage: StageName
    outcome: Literal["pass", "fail", "skip"]
    detail: str = ""


@dataclass(frozen=True, slots=True)
class RejectionReason:
    """Detail attached to a `Rejected` verification outcome.

    `failed_stage` names the first stage that flipped to `fail`;
    `reason` is opaque human-readable context for operator logs.
    """

    failed_stage: StageName
    reason: str


@dataclass(frozen=True, slots=True)
class UnverifiabilityReason:
    """Detail attached to an `Unverifiable` verification outcome.

    Distinct from `RejectionReason` because the verifier could not
    run the math at all (key gone, algorithm not implemented,
    transient outage); a future retry may succeed where a `Rejected`
    outcome would not.
    """

    failed_stage: StageName
    reason: str


@dataclass(frozen=True, slots=True)
class Verified:
    """The verifier ran every stage and all passed (or were skipped)."""

    stage_results: tuple[StageResult, ...]


@dataclass(frozen=True, slots=True)
class Rejected:
    """The verifier ran the math and the artifact failed a stage."""

    stage_results: tuple[StageResult, ...]
    rejection: RejectionReason


@dataclass(frozen=True, slots=True)
class Unverifiable:
    """The verifier could not run a stage to completion."""

    stage_results: tuple[StageResult, ...]
    unverifiability: UnverifiabilityReason


VerificationOutcome = Verified | Rejected | Unverifiable
"""Discriminated union over verifier outcome. Callers branch via
`isinstance`. The three arms map exactly to the SignatureVerification
verdict triple on the kernel-tier ByteSigner:
Verified ≅ Valid, Rejected ≅ Invalid, Unverifiable ≅ Unverifiable."""


PublicationStatus = Literal["Live", "Yanked", "Withdrawn", "Expired", "AbiTierObsoleteOrRemoved"]
"""Closed enum for `FederationAdoptionWindowClosedError.publication_status`.
The first three mirror the publication-lifecycle FSM; `Expired` covers
time-based windows; `AbiTierObsoleteOrRemoved` covers the ABI ladder
edges that close the adoption window without retiring the bytes."""


def is_envelope_kind(envelope: SignatureEnvelope, kind: str) -> bool:
    """Match an envelope against a `kind` literal without isinstance dispatch.

    Helper for routing code that holds a `kind` string from a config
    or a wire payload and wants to verify it matches the envelope's
    own discriminator. Keeps the dispatch out of `if/elif` ladders.
    """
    return envelope.kind == kind


def envelope_signing_version(envelope: SignatureEnvelope) -> str:
    """Extract `signing_version` regardless of arm.

    Equivalent to `envelope.signing_version` since every arm carries
    it; provided as a function so future arms that need access via a
    different attribute name can be funnelled through one helper.
    """
    return envelope.signing_version


def stage_results_outcome_counts(
    stage_results: Sequence[StageResult],
) -> dict[str, int]:
    """Return a counts dict per outcome label for logging/diagnostics."""
    counts = {"pass": 0, "fail": 0, "skip": 0}
    for r in stage_results:
        counts[r.outcome] = counts[r.outcome] + 1
    return counts


__all__ = [
    "ArtifactReference",
    "AssistedBy",
    "CoDevelopedBy",
    "CoseSign1ScittEnvelope",
    "CredentialRef",
    "DcoEntry",
    "DsseSigstoreKeylessEnvelope",
    "DsseStaticJwksEnvelope",
    "FederationTrustContext",
    "FetchProvenance",
    "PublicationStatus",
    "PublishReceipt",
    "PublishedArtifact",
    "PulledArtifact",
    "Receipt",
    "Rejected",
    "RejectionReason",
    "SignatureEnvelope",
    "SignedOffBy",
    "StageName",
    "StageResult",
    "UnverifiabilityReason",
    "Unverifiable",
    "VerificationOutcome",
    "Verified",
    "envelope_signing_version",
    "is_envelope_kind",
    "stage_results_outcome_counts",
]
