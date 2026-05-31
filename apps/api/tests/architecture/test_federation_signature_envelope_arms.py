"""Architecture fitness: SignatureEnvelope structural completeness.

Per project_federation_port_design.md: "The three placeholder arms
are named in this lock so the architecture-fitness tests can
assert structural completeness; the arm-specific field shapes
are owned by Memo 2."

This fitness pins the three v1 arm classes by name:
DsseStaticJwksEnvelope, DsseSigstoreKeylessEnvelope,
CoseSign1ScittEnvelope. Removing any arm without updating this
test signals an unannounced port-shape change and MUST fail CI.

The fitness also asserts that every arm:
  - carries the locked `signing_version: str` field
  - carries the locked `payload_bytes: bytes` field
  - carries the optional `receipts: tuple[Receipt, ...]` slot
  - declares a `kind: Literal[...]` discriminator with a value
    matching the locked set

The arm-specific payload fields beyond these basics are owned by
the adapter memo, not the port, so this fitness does NOT pin them.
"""

from dataclasses import fields

from cora.infrastructure.ports.federation.value_types import (
    CoseSign1ScittEnvelope,
    DsseSigstoreKeylessEnvelope,
    DsseStaticJwksEnvelope,
    SignatureEnvelope,
)

_LOCKED_ARM_CLASSES = (
    DsseStaticJwksEnvelope,
    DsseSigstoreKeylessEnvelope,
    CoseSign1ScittEnvelope,
)

_LOCKED_ARM_KINDS = {
    DsseStaticJwksEnvelope: "dsse_static_jwks",
    DsseSigstoreKeylessEnvelope: "dsse_sigstore_keyless",
    CoseSign1ScittEnvelope: "cose_sign1_scitt",
}


def test_signature_envelope_carries_exactly_three_locked_v1_arms() -> None:
    union_members = getattr(SignatureEnvelope, "__args__", None)
    assert union_members is not None, (
        "SignatureEnvelope must be a typing.Union of the locked arms; "
        "it appears to be a single class which would lose the discriminated-"
        "union shape pinned in the memo."
    )
    assert set(union_members) == set(_LOCKED_ARM_CLASSES), (
        f"SignatureEnvelope arm set drifted from the lock memo. "
        f"Expected: {[c.__name__ for c in _LOCKED_ARM_CLASSES]}; "
        f"Got: {[c.__name__ for c in union_members]}."
    )


def test_every_signature_envelope_arm_carries_locked_field_set() -> None:
    required = {"signing_version", "payload_bytes", "kind", "receipts"}
    for arm_class in _LOCKED_ARM_CLASSES:
        field_names = {f.name for f in fields(arm_class)}
        missing = required - field_names
        assert not missing, (
            f"{arm_class.__name__} missing locked fields {sorted(missing)}; "
            f"got fields {sorted(field_names)}."
        )


def test_every_signature_envelope_arm_kind_default_matches_locked_discriminator() -> None:
    for arm_class, expected_kind in _LOCKED_ARM_KINDS.items():
        instance = arm_class(signing_version="cora/v1", payload_bytes=b"")
        assert instance.kind == expected_kind, (
            f"{arm_class.__name__}.kind defaulted to {instance.kind!r} "
            f"but the locked discriminator is {expected_kind!r}."
        )


def test_every_signature_envelope_arm_receipts_default_is_empty_tuple() -> None:
    for arm_class in _LOCKED_ARM_CLASSES:
        instance = arm_class(signing_version="cora/v1", payload_bytes=b"")
        assert instance.receipts == (), (
            f"{arm_class.__name__}.receipts default drifted from empty tuple; "
            f"changing the default lets the receipt-suppression downgrade "
            f"per sec-1 land silently."
        )
