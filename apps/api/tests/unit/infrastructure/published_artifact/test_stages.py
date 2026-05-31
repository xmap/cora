"""Unit tests for individual verifier stage helpers."""

from datetime import UTC, datetime
from uuid import uuid4

from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.ports.federation.value_types import (
    AssistedBy,
    CoseSign1ScittEnvelope,
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    PublishedArtifact,
    Receipt,
    SignedOffBy,
)
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


def _trust_context(
    *,
    allowed_payload_types: frozenset[str] | None = None,
    abi_tier_floor: str = "Stable",
    required_receipt_kinds: frozenset[str] | None = None,
) -> FederationTrustContext:
    return FederationTrustContext(
        permit_id=uuid4(),
        allowed_credentials=frozenset(),
        allowed_payload_types=(
            allowed_payload_types
            if allowed_payload_types is not None
            else frozenset({"application/vnd.cora.test+json"})
        ),
        abi_tier_floor=abi_tier_floor,
        required_receipt_kinds=(  # type: ignore[arg-type]
            required_receipt_kinds if required_receipt_kinds is not None else frozenset()
        ),
    )


def _artifact(
    *,
    payload_type: str = "application/vnd.cora.test+json",
    abi_tier: str = "Stable",
    expires_at: datetime | None = None,
    canonical_bytes: bytes = b"",
    content_hash: bytes | None = None,
    canonicalization_version: str = "cora/v1",
    dco_chain: tuple[object, ...] | None = None,
) -> PublishedArtifact:
    if dco_chain is None:
        dco_chain = (SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),)
    return PublishedArtifact(
        content_hash=content_hash if content_hash is not None else b"\x00" * 32,
        canonical_bytes=canonical_bytes,
        payload_type=payload_type,
        signature_envelope=DsseStaticJwksEnvelope(
            signing_version="cora/v1", payload_bytes=b"opaque"
        ),
        source_facility_id=uuid4(),
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        expires_at=expires_at,
        abi_tier=abi_tier,
        dco_chain=dco_chain,  # type: ignore[arg-type]
        schema_version=1,
        canonicalization_version=canonicalization_version,
    )


def test_check_payload_type_trusted_passes_when_payload_type_in_allowlist() -> None:
    result = check_payload_type_trusted(_artifact(), _trust_context())
    assert result.outcome == "pass"


def test_check_payload_type_trusted_fails_when_payload_type_outside_allowlist() -> None:
    result = check_payload_type_trusted(
        _artifact(payload_type="application/vnd.cora.other+json"), _trust_context()
    )
    assert result.outcome == "fail"
    assert "not in trust context" in result.detail


def test_check_payload_type_trusted_fails_when_allowlist_is_empty() -> None:
    result = check_payload_type_trusted(
        _artifact(), _trust_context(allowed_payload_types=frozenset())
    )
    assert result.outcome == "fail"
    assert "empty" in result.detail


def test_check_content_hash_passes_when_recomputed_hex_matches_claimed() -> None:
    canonical_bytes = b"DSSEv1 ..."
    import hashlib

    h = hashlib.sha256(canonical_bytes).digest()
    artifact = _artifact(canonical_bytes=canonical_bytes, content_hash=h)
    result = check_content_hash(artifact, DefaultCanonicalizationAdapter())
    assert result.outcome == "pass"


def test_check_content_hash_fails_on_drift_between_canonical_bytes_and_claimed_hash() -> None:
    artifact = _artifact(canonical_bytes=b"DSSEv1 ...", content_hash=b"\xff" * 32)
    result = check_content_hash(artifact, DefaultCanonicalizationAdapter())
    assert result.outcome == "fail"
    assert "claimed" in result.detail


def test_check_content_hash_skips_when_canonical_bytes_empty() -> None:
    artifact = _artifact(canonical_bytes=b"")
    result = check_content_hash(artifact, DefaultCanonicalizationAdapter())
    assert result.outcome == "skip"


def test_check_content_hash_skips_when_adapter_version_differs_from_artifact() -> None:
    artifact = _artifact(canonical_bytes=b"DSSEv1 ...", canonicalization_version="cora/v2-cose")
    result = check_content_hash(artifact, DefaultCanonicalizationAdapter())
    assert result.outcome == "skip"
    assert "does not match" in result.detail


def test_check_required_receipts_present_skips_when_no_kinds_required() -> None:
    envelope = DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"")
    result = check_required_receipts_present(envelope, _trust_context())
    assert result.outcome == "skip"


def test_check_required_receipts_present_passes_when_all_required_kinds_present() -> None:
    envelope = CoseSign1ScittEnvelope(
        signing_version="cora/v2-cose",
        payload_bytes=b"",
        receipts=(Receipt(kind="scitt", bytes_=b"x"),),
    )
    result = check_required_receipts_present(
        envelope,
        _trust_context(required_receipt_kinds=frozenset({"scitt"})),  # type: ignore[arg-type]
    )
    assert result.outcome == "pass"


def test_check_required_receipts_present_fails_when_required_kind_missing() -> None:
    envelope = DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"")
    result = check_required_receipts_present(
        envelope,
        _trust_context(required_receipt_kinds=frozenset({"scitt"})),  # type: ignore[arg-type]
    )
    assert result.outcome == "fail"
    assert "missing" in result.detail


def test_check_abi_tier_passes_when_artifact_tier_equals_floor() -> None:
    result = check_abi_tier(_artifact(abi_tier="Stable"), _trust_context(abi_tier_floor="Stable"))
    assert result.outcome == "pass"


def test_check_abi_tier_passes_when_artifact_tier_above_floor() -> None:
    result = check_abi_tier(_artifact(abi_tier="Obsolete"), _trust_context(abi_tier_floor="Stable"))
    assert result.outcome == "pass"


def test_check_abi_tier_fails_when_artifact_tier_below_floor() -> None:
    result = check_abi_tier(_artifact(abi_tier="Testing"), _trust_context(abi_tier_floor="Stable"))
    assert result.outcome == "fail"
    assert "below trust" in result.detail


def test_check_abi_tier_always_fails_when_artifact_tier_is_removed() -> None:
    result = check_abi_tier(_artifact(abi_tier="Removed"), _trust_context(abi_tier_floor="Removed"))
    assert result.outcome == "fail"
    assert "withdrawn" in result.detail


def test_check_abi_tier_skips_on_unrecognized_tier_string() -> None:
    result = check_abi_tier(_artifact(abi_tier="Bogus"), _trust_context(abi_tier_floor="Stable"))
    assert result.outcome == "skip"


def test_check_expires_at_passes_when_artifact_has_no_expiry() -> None:
    result = check_expires_at(_artifact(expires_at=None), now=datetime(2026, 5, 31, tzinfo=UTC))
    assert result.outcome == "pass"


def test_check_expires_at_passes_when_now_before_expires_at() -> None:
    result = check_expires_at(
        _artifact(expires_at=datetime(2027, 1, 1, tzinfo=UTC)),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert result.outcome == "pass"


def test_check_expires_at_fails_when_now_at_or_after_expires_at() -> None:
    result = check_expires_at(
        _artifact(expires_at=datetime(2026, 1, 1, tzinfo=UTC)),
        now=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert result.outcome == "fail"
    assert "expired" in result.detail


def test_check_dco_chain_passes_when_signed_off_by_present() -> None:
    artifact = _artifact()
    result = check_dco_chain(artifact)
    assert result.outcome == "pass"


def test_check_dco_chain_fails_when_chain_is_empty() -> None:
    artifact = _artifact(dco_chain=())
    result = check_dco_chain(artifact)
    assert result.outcome == "fail"
    assert "empty" in result.detail


def test_check_dco_chain_fails_when_only_ai_entries_present_no_human_signoff() -> None:
    artifact = _artifact(
        dco_chain=(
            AssistedBy(
                agent_id=uuid4(),
                model_ref="claude-opus-4-7",
                assisted_at=datetime(2026, 5, 31, tzinfo=UTC),
                citation="x",
            ),
        )
    )
    result = check_dco_chain(artifact)
    assert result.outcome == "fail"
    assert "AI-only" in result.detail


def test_deferred_stage_returns_skip_outcome_with_reason_detail() -> None:
    result = deferred_stage("payload_type_known", "registry not wired yet")
    assert result.outcome == "skip"
    assert result.detail == "registry not wired yet"


def test_dco_chain_has_human_actor_detects_signed_off_by_entry() -> None:
    chain = (SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),)
    assert dco_chain_has_human_actor(chain) is True  # type: ignore[arg-type]


def test_dco_chain_has_human_actor_returns_false_for_ai_only_chain() -> None:
    chain = (
        AssistedBy(
            agent_id=uuid4(),
            model_ref="m",
            assisted_at=datetime(2026, 5, 31, tzinfo=UTC),
            citation="x",
        ),
    )
    assert dco_chain_has_human_actor(chain) is False  # type: ignore[arg-type]


def test_is_terminal_publication_status_returns_true_for_each_terminal_value() -> None:
    for status in ("Yanked", "Withdrawn", "Expired", "AbiTierObsoleteOrRemoved"):
        assert is_terminal_publication_status(status) is True  # type: ignore[arg-type]


def test_is_terminal_publication_status_returns_false_for_live_status() -> None:
    assert is_terminal_publication_status("Live") is False  # type: ignore[arg-type]
