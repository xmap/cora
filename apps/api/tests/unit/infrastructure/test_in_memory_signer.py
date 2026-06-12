"""Unit tests for the in-memory Ed25519 `Signer` adapter.

The adapter is the shipped default for the event-provenance `Signer`
port: it must produce a signature the shared `verify_signature` path
accepts, fail closed on tampering, and round-trip its own public key.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.adapters.in_memory_signer import InMemorySigner
from cora.infrastructure.signing import SignatureInvalidError, verify_signature


def _payload() -> dict[str, object]:
    return {"decision_id": str(uuid4()), "choice": "approve", "reasoning": "looks sound"}


@pytest.mark.unit
async def test_in_memory_signer_signature_verifies_against_shared_verify_path() -> None:
    signer = InMemorySigner()
    payload = _payload()
    signature, kid, _ = await signer.sign(
        event_type="DecisionRegistered", payload=payload, actor_id=uuid4()
    )
    await verify_signature(
        event_type="DecisionRegistered",
        payload=payload,
        signature=signature,
        kid=kid,
        resolve_public_key=signer.resolve_public_key,
    )


@pytest.mark.unit
async def test_in_memory_signer_tampered_payload_fails_verification() -> None:
    signer = InMemorySigner()
    payload = _payload()
    signature, kid, _ = await signer.sign(
        event_type="DecisionRegistered", payload=payload, actor_id=uuid4()
    )
    tampered = {**payload, "choice": "reject"}
    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="DecisionRegistered",
            payload=tampered,
            signature=signature,
            kid=kid,
            resolve_public_key=signer.resolve_public_key,
        )


@pytest.mark.unit
async def test_in_memory_signer_returns_64_byte_signature_kid_and_v1_version() -> None:
    signer = InMemorySigner()
    signature, kid, version = await signer.sign(
        event_type="DecisionRegistered", payload=_payload(), actor_id=uuid4()
    )
    assert isinstance(signature, bytes)
    assert len(signature) == 64
    assert kid == signer.kid
    assert version == "cora/v1"


@pytest.mark.unit
async def test_in_memory_signer_signs_for_any_actor_with_its_single_key() -> None:
    signer = InMemorySigner()
    payload = _payload()
    for _ in range(3):
        signature, kid, _ = await signer.sign(
            event_type="DecisionRegistered", payload=payload, actor_id=uuid4()
        )
        assert kid == signer.kid
        await verify_signature(
            event_type="DecisionRegistered",
            payload=payload,
            signature=signature,
            kid=kid,
            resolve_public_key=signer.resolve_public_key,
        )


@pytest.mark.unit
async def test_in_memory_signer_resolve_public_key_unknown_kid_raises() -> None:
    signer = InMemorySigner()
    assert await signer.resolve_public_key(signer.kid) == signer.public_key_bytes
    with pytest.raises(KeyError):
        await signer.resolve_public_key("some-other-kid")


@pytest.mark.unit
async def test_in_memory_signer_distinct_instances_use_distinct_keys() -> None:
    first = InMemorySigner()
    second = InMemorySigner()
    payload = _payload()
    signature, kid, _ = await first.sign(
        event_type="DecisionRegistered", payload=payload, actor_id=uuid4()
    )
    # A signature from `first` must not verify under `second`'s key.
    with pytest.raises(SignatureInvalidError):
        await verify_signature(
            event_type="DecisionRegistered",
            payload=payload,
            signature=signature,
            kid=kid,
            resolve_public_key=second.resolve_public_key,
        )
