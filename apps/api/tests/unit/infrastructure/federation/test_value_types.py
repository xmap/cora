"""Unit tests for federation port-tier value types."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.federation.value_types import (
    ArtifactReference,
    AssistedBy,
    CoDevelopedBy,
    CoseSign1ScittEnvelope,
    CredentialRef,
    DcoEntry,
    DsseSigstoreKeylessEnvelope,
    DsseStaticJwksEnvelope,
    FederationTrustContext,
    FetchProvenance,
    PublishedArtifact,
    PublishReceipt,
    PulledArtifact,
    Receipt,
    Rejected,
    RejectionReason,
    SignatureEnvelope,
    SignedOffBy,
    StageResult,
    UnverifiabilityReason,
    Unverifiable,
    VerificationOutcome,
    Verified,
    envelope_signing_version,
    is_envelope_kind,
    stage_results_outcome_counts,
)


def _envelope() -> SignatureEnvelope:
    return DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"opaque")


def _published_artifact() -> PublishedArtifact:
    return PublishedArtifact(
        content_hash=b"\x01" * 32,
        canonical_bytes=b"DSSEv1 ...",
        payload_type="application/vnd.cora.test-event+json",
        signature_envelope=_envelope(),
        source_facility_id=UUID("00000000-0000-0000-0000-00000000aaaa"),
        published_at=datetime(2026, 5, 31, tzinfo=UTC),
        expires_at=None,
        abi_tier="Stable",
        dco_chain=(SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),),
        schema_version=1,
        canonicalization_version="cora/v1",
    )


def test_credential_ref_carries_credential_id_and_is_frozen() -> None:
    cid = uuid4()
    ref = CredentialRef(credential_id=cid)
    assert ref.credential_id == cid
    with pytest.raises(AttributeError):
        ref.credential_id = uuid4()  # type: ignore[misc]


def test_receipt_carries_kind_and_opaque_bytes() -> None:
    r = Receipt(kind="scitt", bytes_=b"opaque")
    assert r.kind == "scitt"
    assert r.bytes_ == b"opaque"


def test_dsse_static_jwks_envelope_carries_locked_kind_discriminator() -> None:
    env = DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b"x")
    assert env.kind == "dsse_static_jwks"
    assert env.signing_version == "cora/v1"
    assert env.receipts == ()


def test_dsse_sigstore_keyless_envelope_carries_locked_kind_discriminator() -> None:
    env = DsseSigstoreKeylessEnvelope(signing_version="cora/v1", payload_bytes=b"x")
    assert env.kind == "dsse_sigstore_keyless"


def test_cose_sign1_scitt_envelope_carries_locked_kind_discriminator() -> None:
    env = CoseSign1ScittEnvelope(signing_version="cora/v2-cose", payload_bytes=b"x")
    assert env.kind == "cose_sign1_scitt"


def test_signature_envelope_union_accepts_all_three_arms() -> None:
    envs: list[SignatureEnvelope] = [
        DsseStaticJwksEnvelope(signing_version="cora/v1", payload_bytes=b""),
        DsseSigstoreKeylessEnvelope(signing_version="cora/v1", payload_bytes=b""),
        CoseSign1ScittEnvelope(signing_version="cora/v2-cose", payload_bytes=b""),
    ]
    kinds = {e.kind for e in envs}
    assert kinds == {"dsse_static_jwks", "dsse_sigstore_keyless", "cose_sign1_scitt"}


def test_signed_off_by_requires_actor_id_and_signed_at() -> None:
    s = SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC))
    assert s.actor_id is not None


def test_assisted_by_carries_model_ref_and_citation() -> None:
    a = AssistedBy(
        agent_id=uuid4(),
        model_ref="claude-opus-4-7",
        assisted_at=datetime(2026, 5, 31, tzinfo=UTC),
        citation="decision-abc-123",
    )
    assert a.model_ref == "claude-opus-4-7"


def test_co_developed_by_carries_two_actor_ids() -> None:
    a, b = uuid4(), uuid4()
    c = CoDevelopedBy(actor_id_a=a, actor_id_b=b, co_developed_at=datetime(2026, 5, 31, tzinfo=UTC))
    assert c.actor_id_a == a
    assert c.actor_id_b == b


def test_dco_entry_union_accepts_all_three_arms() -> None:
    entries: list[DcoEntry] = [
        SignedOffBy(actor_id=uuid4(), signed_at=datetime(2026, 5, 31, tzinfo=UTC)),
        AssistedBy(
            agent_id=uuid4(),
            model_ref="m",
            assisted_at=datetime(2026, 5, 31, tzinfo=UTC),
            citation="c",
        ),
        CoDevelopedBy(
            actor_id_a=uuid4(),
            actor_id_b=uuid4(),
            co_developed_at=datetime(2026, 5, 31, tzinfo=UTC),
        ),
    ]
    assert len(entries) == 3


def test_published_artifact_carries_locked_fields() -> None:
    a = _published_artifact()
    assert a.canonicalization_version == "cora/v1"
    assert a.abi_tier == "Stable"
    assert a.schema_version == 1


def test_artifact_reference_security_equality_is_on_hash_and_payload_type() -> None:
    a = ArtifactReference(
        content_hash=b"\x01" * 32,
        payload_type="application/vnd.cora.test+json",
        source_facility_id=uuid4(),
        hint_locator="https://peer/x",
    )
    b = ArtifactReference(
        content_hash=b"\x01" * 32,
        payload_type="application/vnd.cora.test+json",
        source_facility_id=a.source_facility_id,
        hint_locator="ipfs://different",
    )
    assert a.content_hash == b.content_hash
    assert a.payload_type == b.payload_type


def test_publish_receipt_carries_opaque_bytes_and_hints() -> None:
    r = PublishReceipt(
        receipt_bytes=b"opaque",
        receipt_format_hint="rekor-bundle/v1",
        transparency_log_hint="rekor:prod",
        recorded_at=datetime(2026, 5, 31, tzinfo=UTC),
    )
    assert r.receipt_bytes == b"opaque"


def test_pulled_artifact_carries_both_artifact_and_fetch_provenance_fields() -> None:
    p = PulledArtifact(
        artifact=_published_artifact(),
        fetch_provenance=FetchProvenance(
            locator_used="https://peer/x",
            wire_content_type="application/dsse+json",
            fetch_duration_ms=42,
            byte_count=1024,
        ),
    )
    assert p.fetch_provenance.byte_count == 1024


def test_federation_trust_context_accept_yanked_is_structurally_false() -> None:
    ctx = FederationTrustContext(
        permit_id=uuid4(),
        allowed_credentials=frozenset({CredentialRef(credential_id=uuid4())}),
        allowed_payload_types=frozenset({"application/vnd.cora.test+json"}),
        abi_tier_floor="Stable",
    )
    assert ctx.accept_yanked is False
    assert ctx.required_receipt_kinds == frozenset()


def test_federation_trust_context_required_receipt_kinds_accepts_known_kinds() -> None:
    ctx = FederationTrustContext(
        permit_id=uuid4(),
        allowed_credentials=frozenset(),
        allowed_payload_types=frozenset(),
        abi_tier_floor="Stable",
        required_receipt_kinds=frozenset({"scitt", "rekor_sct"}),
    )
    assert ctx.required_receipt_kinds == frozenset({"scitt", "rekor_sct"})


def test_verified_outcome_carries_stage_results_tuple() -> None:
    v: VerificationOutcome = Verified(
        stage_results=(StageResult(stage="content_hash", outcome="pass"),)
    )
    assert isinstance(v, Verified)
    assert v.stage_results[0].outcome == "pass"


def test_rejected_outcome_carries_failed_stage_in_rejection_reason() -> None:
    r: VerificationOutcome = Rejected(
        stage_results=(StageResult(stage="signature", outcome="fail", detail="Ed25519 rejected"),),
        rejection=RejectionReason(failed_stage="signature", reason="Ed25519 verify returned False"),
    )
    assert isinstance(r, Rejected)
    assert r.rejection.failed_stage == "signature"


def test_unverifiable_outcome_distinct_from_rejected() -> None:
    u: VerificationOutcome = Unverifiable(
        stage_results=(
            StageResult(stage="key_resolution", outcome="skip", detail="JWKS rotation in flight"),
        ),
        unverifiability=UnverifiabilityReason(
            failed_stage="key_resolution", reason="JWKS not reachable"
        ),
    )
    assert isinstance(u, Unverifiable)
    assert not isinstance(u, Rejected)


def test_is_envelope_kind_helper_matches_arm() -> None:
    env = _envelope()
    assert is_envelope_kind(env, "dsse_static_jwks") is True
    assert is_envelope_kind(env, "cose_sign1_scitt") is False


def test_envelope_signing_version_helper_works_across_arms() -> None:
    for arm_class, sv in (
        (DsseStaticJwksEnvelope, "cora/v1"),
        (DsseSigstoreKeylessEnvelope, "cora/v1"),
        (CoseSign1ScittEnvelope, "cora/v2-cose"),
    ):
        env = arm_class(signing_version=sv, payload_bytes=b"")
        assert envelope_signing_version(env) == sv


def test_stage_results_outcome_counts_returns_counts_dict() -> None:
    results = (
        StageResult(stage="content_hash", outcome="pass"),
        StageResult(stage="signature", outcome="pass"),
        StageResult(stage="dco_chain", outcome="skip"),
    )
    counts = stage_results_outcome_counts(results)
    assert counts == {"pass": 2, "fail": 0, "skip": 1}
