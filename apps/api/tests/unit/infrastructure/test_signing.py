"""Unit tests for `cora.infrastructure.signing` + `ports.signing`.

Coverage:
  - `event_type_to_payload_type` CamelCase to kebab-case mapping
  - `SIGNED_EVENT_TYPES` contains the initial event types per design lock
  - `verify_signature` happy path: signature signed over the same PAE
    bytes verifies successfully
  - `verify_signature` failure modes: tampered payload, wrong event_type
    (payloadType binding via PAE), wrong public key, wrong signature
    bytes, wrong kid via resolver-returns-different-key
  - Error class constructors: `SignatureInvalidError`,
    `SignatureMissingError`, `SignerKeyNotFoundError`,
    `SignerKeyInactiveError`, `SignerUnavailableError`
  - `Signer` Protocol shape: importable, has the expected async method

Test-only Ed25519 signer is inline. No production adapter ships in
iteration 2; production signing adapters land in a future iteration
behind the Signer port.
"""

import inspect
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.ports.signer import (
    Signer,
    SignerKeyInactiveError,
    SignerKeyNotFoundError,
    SignerUnavailableError,
)
from cora.infrastructure.signing import (
    SIGNED_EVENT_TYPES,
    SignatureInvalidError,
    SignatureMissingError,
    event_type_to_payload_type,
    verify_signature,
    verify_stream,
)
from cora.shared.content_hash import canonical_body_bytes, pae_bytes

# ---------- event_type_to_payload_type ----------


@pytest.mark.unit
def test_event_type_to_payload_type_maps_camelcase_to_kebab() -> None:
    assert event_type_to_payload_type("CautionProposed") == (
        "application/vnd.cora.caution-proposed+json"
    )


@pytest.mark.unit
def test_event_type_to_payload_type_maps_decision_registered() -> None:
    assert event_type_to_payload_type("DecisionRegistered") == (
        "application/vnd.cora.decision-registered+json"
    )


@pytest.mark.unit
def test_event_type_to_payload_type_lower_first_char_does_not_emit_leading_dash() -> None:
    """`event_type_to_payload_type("Foo")` is `application/vnd.cora.foo+json`
    not `application/vnd.cora.-foo+json`. Pinned because a regression
    in the loop guard would produce malformed media types."""
    assert event_type_to_payload_type("Foo") == "application/vnd.cora.foo+json"


@pytest.mark.unit
def test_event_type_to_payload_type_handles_multi_word_camelcase() -> None:
    assert event_type_to_payload_type("CautionDrafterProposed") == (
        "application/vnd.cora.caution-drafter-proposed+json"
    )


@pytest.mark.unit
def test_event_type_to_payload_type_handles_acronym_prefix() -> None:
    """Future event names that lead with an acronym (`MCPSessionOpened`,
    `PIIVaultErased`, `HTTPMessageReceived`) must kebab-case correctly,
    not as `m-c-p-session-opened`. Pinned to prevent malformed media
    types when the SIGNED_EVENT_TYPES set grows past today's two."""
    assert event_type_to_payload_type("MCPSessionOpened") == (
        "application/vnd.cora.mcp-session-opened+json"
    )
    assert event_type_to_payload_type("PIIVaultErased") == (
        "application/vnd.cora.pii-vault-erased+json"
    )
    assert event_type_to_payload_type("HTTPMessageReceived") == (
        "application/vnd.cora.http-message-received+json"
    )


@pytest.mark.unit
def test_event_type_to_payload_type_handles_all_caps_and_single_char_cases() -> None:
    """Boundary cases for the kebab-conversion: pure-acronym name, single
    char, and a CamelCase boundary right after an acronym."""
    assert event_type_to_payload_type("XML") == "application/vnd.cora.xml+json"
    assert event_type_to_payload_type("A") == "application/vnd.cora.a+json"
    assert event_type_to_payload_type("ABCFoo") == ("application/vnd.cora.abc-foo+json")


# ---------- SIGNED_EVENT_TYPES ----------


@pytest.mark.unit
def test_signed_event_types_contains_decision_registered() -> None:
    assert "DecisionRegistered" in SIGNED_EVENT_TYPES


@pytest.mark.unit
def test_signed_event_types_is_frozenset() -> None:
    """Closed set; mutation at module load would be a regression."""
    assert isinstance(SIGNED_EVENT_TYPES, frozenset)


@pytest.mark.unit
def test_signed_event_types_excludes_caution_proposed() -> None:
    """Regression guard for the errata: `CautionProposed` was an
    invented event name in an earlier draft of the design lock; it
    does not exist as a CORA event type. CautionDrafter signing
    routes through `DecisionRegistered` plus the Agent-actor
    discriminator. Pinning the exclusion prevents the bogus entry
    sneaking back."""
    assert "CautionProposed" not in SIGNED_EVENT_TYPES


# ---------- verify_signature happy path ----------


def _sign_with_ed25519(
    event_type: str, payload: Mapping[str, object], signer: Ed25519PrivateKey
) -> bytes:
    """Test helper: produce a signature exactly the way a real Signer
    adapter would, so the verify path is exercised end-to-end."""
    payload_type = event_type_to_payload_type(event_type)
    body = canonical_body_bytes(payload)
    pae = pae_bytes(payload_type, body)
    return signer.sign(pae)


def _public_bytes(signer: Ed25519PrivateKey) -> bytes:
    return signer.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_with_matching_key_and_payload_succeeds() -> None:
    signer = Ed25519PrivateKey.generate()
    payload = {"caution_id": str(uuid4()), "severity": "warning"}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)
    pub = _public_bytes(signer)

    async def resolver(_kid: str) -> bytes:
        return pub

    await verify_signature(
        event_type="CautionProposed",
        payload=payload,
        signature=signature,
        kid="test-kid",
        resolve_public_key=resolver,
    )


# ---------- verify_signature failure modes ----------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_tampered_payload() -> None:
    """A single-byte change to the payload after signing breaks verification.
    Critical: this is the integrity guarantee CORA relies on."""
    signer = Ed25519PrivateKey.generate()
    payload = {"caution_id": str(uuid4()), "severity": "warning"}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)
    tampered = {"caution_id": payload["caution_id"], "severity": "critical"}
    pub = _public_bytes(signer)

    async def resolver(_kid: str) -> bytes:
        return pub

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload=tampered,
            signature=signature,
            kid="test-kid",
            resolve_public_key=resolver,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_wrong_event_type() -> None:
    """PayloadType binding via PAE prevents cross-event-type collisions.
    A signature signed under `CautionProposed` does NOT verify when
    the verifier is told the event was `DecisionRegistered`, even if
    the payload bytes are identical."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)
    pub = _public_bytes(signer)

    async def resolver(_kid: str) -> bytes:
        return pub

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="DecisionRegistered",
            payload=payload,
            signature=signature,
            kid="test-kid",
            resolve_public_key=resolver,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_wrong_public_key() -> None:
    """Verifier resolves the WRONG public key (rotation drift, mis-keyed
    JWKS entry). Must raise loudly, not silently accept."""
    signer = Ed25519PrivateKey.generate()
    other_signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)
    wrong_pub = _public_bytes(other_signer)

    async def resolver(_kid: str) -> bytes:
        return wrong_pub

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload=payload,
            signature=signature,
            kid="test-kid",
            resolve_public_key=resolver,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_random_signature_bytes() -> None:
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    pub = _public_bytes(signer)
    random_sig = b"\x00" * 64

    async def resolver(_kid: str) -> bytes:
        return pub

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload=payload,
            signature=random_sig,
            kid="test-kid",
            resolve_public_key=resolver,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_wrong_length_signature() -> None:
    """Ed25519 signatures are exactly 64 bytes; a 63- or 65-byte
    signature must raise SignatureInvalidError loudly, not crash with
    a raw cryptography exception."""
    signer = Ed25519PrivateKey.generate()
    pub = _public_bytes(signer)

    async def resolver(_kid: str) -> bytes:
        return pub

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload={"x": 1},
            signature=b"\x00" * 63,
            kid="test-kid",
            resolve_public_key=resolver,
        )
    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload={"x": 1},
            signature=b"\x00" * 65,
            kid="test-kid",
            resolve_public_key=resolver,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_raises_on_wrong_length_public_key() -> None:
    """A resolver that returns non-32-byte bytes (corrupt JWKS entry,
    keystore bug) must surface as SignatureInvalidError with detail,
    not as a raw ValueError from cryptography. Pins the typed-error
    contract for downstream incident handlers."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)

    async def resolver_returning_too_few_bytes(_kid: str) -> bytes:
        return b"\x00" * 16

    async def resolver_returning_too_many_bytes(_kid: str) -> bytes:
        return b"\x00" * 64

    with pytest.raises(SignatureInvalidError) as exc_info:
        await verify_signature(
            event_type="CautionProposed",
            payload=payload,
            signature=signature,
            kid="test-kid",
            resolve_public_key=resolver_returning_too_few_bytes,
        )
    assert "public key malformed" in exc_info.value.detail

    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="CautionProposed",
            payload=payload,
            signature=signature,
            kid="test-kid",
            resolve_public_key=resolver_returning_too_many_bytes,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_signature_passes_kid_to_resolver() -> None:
    """Pin that the kid string the verifier receives is exactly what
    gets passed to the resolver. A regression that munged the kid
    (lowercased, trimmed, etc.) would silently route to the wrong
    key in production."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("CautionProposed", payload, signer)
    pub = _public_bytes(signer)
    seen: list[str] = []

    async def resolver(kid: str) -> bytes:
        seen.append(kid)
        return pub

    await verify_signature(
        event_type="CautionProposed",
        payload=payload,
        signature=signature,
        kid="opaque-kid-12345",
        resolve_public_key=resolver,
    )
    assert seen == ["opaque-kid-12345"]


# ---------- error class constructors ----------


@pytest.mark.unit
def test_signature_invalid_error_carries_event_type_and_kid() -> None:
    err = SignatureInvalidError("CautionProposed", "kid-xyz", "bad bytes")
    assert err.event_type == "CautionProposed"
    assert err.kid == "kid-xyz"
    assert err.detail == "bad bytes"
    assert "CautionProposed" in str(err)
    assert "kid-xyz" in str(err)


@pytest.mark.unit
def test_signature_missing_error_carries_event_type() -> None:
    err = SignatureMissingError("CautionProposed")
    assert err.event_type == "CautionProposed"
    assert "CautionProposed" in str(err)


@pytest.mark.unit
def test_signer_key_not_found_error_carries_actor_id() -> None:
    actor_id = uuid4()
    err = SignerKeyNotFoundError(actor_id, "key vault empty")
    assert err.actor_id == actor_id
    assert err.detail == "key vault empty"
    assert str(actor_id) in str(err)


@pytest.mark.unit
def test_signer_key_inactive_error_carries_kid() -> None:
    err = SignerKeyInactiveError("kid-retired", "rotation in progress")
    assert err.kid == "kid-retired"
    assert err.detail == "rotation in progress"
    assert "kid-retired" in str(err)


@pytest.mark.unit
def test_signer_unavailable_error_carries_backend() -> None:
    err = SignerUnavailableError("sigstore-fulcio", "504 from fulcio")
    assert err.backend == "sigstore-fulcio"
    assert err.detail == "504 from fulcio"
    assert "sigstore-fulcio" in str(err)


# ---------- Signer Protocol shape ----------


@pytest.mark.unit
def test_signer_protocol_has_locked_sign_signature() -> None:
    """The Signer port is the abstract contract for future adapters
    (Sigstore Fulcio, SPIFFE, KMS, local keystore). Pinned at the
    parameter-name level so a regression that renamed kwargs would
    silently break every planned adapter."""
    assert hasattr(Signer, "sign")
    sig = inspect.signature(Signer.sign)
    param_names = list(sig.parameters.keys())
    assert param_names == ["self", "event_type", "payload", "actor_id"]
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only; positional args break adapter call-site safety"
        )


# ---------- verify_stream (audit-mode opt-in) ----------


def _stored(
    *,
    event_type: str = "DecisionRegistered",
    payload: dict[str, Any] | None = None,
    signature: bytes | None = None,
    signature_kid: str | None = None,
) -> StoredEvent:
    """Build a minimal StoredEvent for verify_stream tests."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Decision",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload or {"x": 1},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=datetime(2026, 5, 24, tzinfo=UTC),
        recorded_at=datetime(2026, 5, 24, tzinfo=UTC),
        signature=signature,
        signature_kid=signature_kid,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_accepts_empty_sequence() -> None:
    """Empty stream is a no-op; no resolver calls, no raises."""
    calls: list[str] = []

    async def _resolver(kid: str) -> bytes:
        calls.append(kid)
        return b"\x00" * 32

    await verify_stream([], resolve_public_key=_resolver, strict=True)
    assert calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_skips_unsigned_events_in_non_strict_mode() -> None:
    """Default non-strict mode: unsigned events pass through silently
    (legitimate pre-rollout + human-actor rows)."""
    events = [
        _stored(event_type="DecisionRegistered"),  # unsigned, in SIGNED_EVENT_TYPES
        _stored(event_type="RunStarted"),  # unsigned, not in SIGNED_EVENT_TYPES
    ]
    calls: list[str] = []

    async def _resolver(kid: str) -> bytes:
        calls.append(kid)
        return b"\x00" * 32

    await verify_stream(events, resolve_public_key=_resolver)
    assert calls == []  # no signed events; resolver never invoked


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_strict_mode_raises_on_unsigned_signed_event_type() -> None:
    """Strict audit mode: an event with type in SIGNED_EVENT_TYPES that
    lacks a signature is the canary for a misconfigured signer (no
    signed event should ever land without a signature). Raises
    SignatureMissingError so audit dashboards surface the gap."""
    events = [_stored(event_type="DecisionRegistered")]  # in SIGNED_EVENT_TYPES, unsigned

    async def _resolver(_kid: str) -> bytes:
        return b"\x00" * 32

    with pytest.raises(SignatureMissingError) as exc_info:
        await verify_stream(events, resolve_public_key=_resolver, strict=True)
    assert exc_info.value.event_type == "DecisionRegistered"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_strict_mode_passes_unsigned_non_signed_type() -> None:
    """Strict mode is a per-event check; events whose type is NOT in
    SIGNED_EVENT_TYPES pass through unsigned even with strict=True
    (they're legitimately unsigned by design)."""
    events = [_stored(event_type="RunStarted")]

    async def _resolver(_kid: str) -> bytes:
        return b"\x00" * 32

    await verify_stream(events, resolve_public_key=_resolver, strict=True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_verifies_signed_events_against_resolver() -> None:
    """Happy path: a stream with one signed event verifies cleanly."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("DecisionRegistered", payload, signer)
    pub = _public_bytes(signer)
    events = [
        _stored(
            event_type="DecisionRegistered",
            payload=payload,
            signature=signature,
            signature_kid="kid-A",
        )
    ]

    async def _resolver(kid: str) -> bytes:
        assert kid == "kid-A"
        return pub

    await verify_stream(events, resolve_public_key=_resolver)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_raises_on_first_invalid_signature() -> None:
    """When one of many events fails verification, the call raises
    immediately; later events are not checked. Pinning the
    fail-fast semantic so audit consumers can surface the offending
    row promptly."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    valid_sig = _sign_with_ed25519("DecisionRegistered", payload, signer)
    pub = _public_bytes(signer)
    events = [
        _stored(  # valid
            event_type="DecisionRegistered",
            payload=payload,
            signature=valid_sig,
            signature_kid="kid-A",
        ),
        _stored(  # tampered: signature doesn't match this payload
            event_type="DecisionRegistered",
            payload={"x": 99},
            signature=valid_sig,
            signature_kid="kid-A",
        ),
        _stored(  # would also fail, but never reached
            event_type="DecisionRegistered",
            payload={"x": 100},
            signature=valid_sig,
            signature_kid="kid-A",
        ),
    ]

    async def _resolver(_kid: str) -> bytes:
        return pub

    with pytest.raises(SignatureInvalidError):
        await verify_stream(events, resolve_public_key=_resolver)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_stream_mixed_signed_and_unsigned_in_strict_mode() -> None:
    """Realistic audit replay: a stream contains both pre-rollout
    unsigned events (event_type not in SIGNED_EVENT_TYPES) and newly
    signed Agent-emitted events. Strict mode verifies the signed
    ones and allows the unsigned non-signed-type rows."""
    signer = Ed25519PrivateKey.generate()
    payload = {"x": 1}
    signature = _sign_with_ed25519("DecisionRegistered", payload, signer)
    pub = _public_bytes(signer)
    events = [
        _stored(event_type="RunStarted"),  # legitimately unsigned
        _stored(
            event_type="DecisionRegistered",
            payload=payload,
            signature=signature,
            signature_kid="kid-A",
        ),
        _stored(event_type="RunCompleted"),  # legitimately unsigned
    ]

    async def _resolver(_kid: str) -> bytes:
        return pub

    await verify_stream(events, resolve_public_key=_resolver, strict=True)
