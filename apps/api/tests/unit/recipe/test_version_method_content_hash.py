"""Content-hash plumbing for the `version_method` slice.

Pins the Candidate A adoption on the Method aggregate per
[[project_content_addressed_identity_design]]. The decider computes a
SHA-256 of the canonical body bytes for the Method's content subset
(`name + parameters_schema + capability_id + needed_family_ids +
needed_supplies + needed_assembly_ids`) and pins it in the emitted
MethodVersioned event.
Tests in this module cover:

  - golden vectors that detect any drift in the canonicalization
    pipeline (Pydantic dump, NFC, sort-keys, PAE wrap, SHA-256)
  - equivalence semantics (same content subset -> same hash;
    re-attestation preserved)
  - content sensitivity (different subset -> different hash) across
    each hashed field
  - exclusion guarantees (excluded fields do NOT affect the hash):
    version_tag, status, id

Lifecycle guards live in test_version_method_decider.py to keep this
file focused on the hash itself.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    ExecutionPattern,
    Method,
    MethodName,
    MethodStatus,
    MethodVersioned,
)
from cora.recipe.features import version_method
from cora.recipe.features.version_method import VersionMethod
from cora.shared.content_hash import compute_content_hash

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_FIXED_METHOD_ID = UUID("01900000-0000-7000-8000-000000000001")
_FIXED_CAP_ID = UUID("01900000-0000-7000-8000-00000000c1da")
_FIXED_FAMILY_A = UUID("01900000-0000-7000-8000-000000000111")
_FIXED_FAMILY_B = UUID("01900000-0000-7000-8000-000000000222")

# Golden vectors precomputed via `compute_content_hash(
#     event_type_to_payload_type("MethodVersioned"), <content_subset>)`.
# Pinned here so future Pydantic / canonicalization / payloadType-scheme
# drift trips a single fixture rather than every consumer test.
_GOLDEN_EMPTY = "8f6d8b2624bd6c85a9d64e54d8f4c38ef4ec0f7f551758ca5ef7ecf1b2c36998"
_GOLDEN_POPULATED = "1d11f2289aa538f30845959aef39ed789d8d769a9aa4fc6d27e7dc00aab1bedf"

_FIXED_ASM_A = UUID("01900000-0000-7000-8000-0000a0a0a0a1")
_FIXED_ASM_B = UUID("01900000-0000-7000-8000-0000a0a0a0a2")


def _method(
    *,
    name: str = "XRF Mapping",
    parameters_schema: dict[str, Any] | None = None,
    capability_id: UUID | None = None,
    needed_family_ids: frozenset[UUID] = frozenset(),
    needed_supplies: frozenset[str] = frozenset(),
    needed_assembly_ids: frozenset[UUID] = frozenset(),
    execution_pattern: ExecutionPattern | None = None,
    monotone_quality: bool = False,
    resumable_from_checkpoint: bool = False,
    status: MethodStatus = MethodStatus.DEFINED,
    version: str | None = None,
) -> Method:
    return Method(
        id=_FIXED_METHOD_ID,
        name=MethodName(name),
        needed_family_ids=needed_family_ids,
        status=status,
        version=version,
        parameters_schema=parameters_schema,
        capability_id=capability_id,
        needed_supplies=needed_supplies,
        needed_assembly_ids=needed_assembly_ids,
        execution_pattern=execution_pattern,
        monotone_quality=monotone_quality,
        resumable_from_checkpoint=resumable_from_checkpoint,
    )


def _decide(state: Method, *, tag: str = "v2") -> MethodVersioned:
    events = version_method.decide(
        state=state,
        command=VersionMethod(method_id=state.id, version_tag=tag),
        now=_NOW,
    )
    event = events[0]
    assert isinstance(event, MethodVersioned)
    return event


# ---------- Golden vectors ----------


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_minimal_method() -> None:
    """Minimal Method (no schema, no capability, no families, no supplies)
    must hash to the pinned golden vector. Drift in any layer of the
    canonicalization pipeline (Pydantic, NFC, sort-keys, PAE, SHA-256)
    or in the locked content-subset shape moves this hash."""
    state = _method()
    event = _decide(state)
    assert event.content_hash == _GOLDEN_EMPTY


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_populated_method() -> None:
    """Populated Method with every hashed field non-default. Catches any
    refactor that drops or reorders a content-subset member."""
    state = _method(
        name="XRF Fly Mapping",
        parameters_schema={
            "type": "object",
            "properties": {"energy": {"type": "number"}},
        },
        capability_id=_FIXED_CAP_ID,
        needed_family_ids=frozenset({_FIXED_FAMILY_A, _FIXED_FAMILY_B}),
        needed_supplies=frozenset({"nitrogen"}),
    )
    event = _decide(state)
    assert event.content_hash == _GOLDEN_POPULATED


# ---------- Shape ----------


@pytest.mark.unit
def test_decide_content_hash_is_64_char_lowercase_hex() -> None:
    state = _method()
    event = _decide(state)
    assert event.content_hash is not None
    assert len(event.content_hash) == 64
    assert event.content_hash == event.content_hash.lower()
    assert all(c in "0123456789abcdef" for c in event.content_hash)


@pytest.mark.unit
def test_decide_content_hash_matches_helper_output_directly() -> None:
    """The decider's hash must equal the helper invoked on the locked
    content subset. Locks the contract that the decider does NOT add
    or rename fields beyond the documented subset."""
    state = _method(
        name="XRF Fly Mapping",
        capability_id=_FIXED_CAP_ID,
        needed_family_ids=frozenset({_FIXED_FAMILY_A}),
        needed_supplies=frozenset({"nitrogen"}),
    )
    event = _decide(state)
    expected = compute_content_hash(
        "application/vnd.cora.method-versioned+json",
        {
            "name": "XRF Fly Mapping",
            "parameters_schema": None,
            "capability_id": str(_FIXED_CAP_ID),
            "needed_family_ids": [str(_FIXED_FAMILY_A)],
            "needed_supplies": ["nitrogen"],
            "needed_assembly_ids": [],
            # compute classification joined the content subset; rendered
            # unconditionally (execution_pattern as the enum value or
            # None, the two claims as bools).
            "execution_pattern": None,
            "monotone_quality": False,
            "resumable_from_checkpoint": False,
            # required_roles joined the content subset when the
            # positional role-tagging slice landed; empty list for a
            # Method that hasn't declared any roles.
            "required_roles": [],
            # launch_spec joined the content subset for the vetted-launch
            # work; None for a Method that carries no launch recipe.
            "launch_spec": None,
        },
    )
    assert event.content_hash == expected


# ---------- Equivalence (same content -> same hash) ----------


@pytest.mark.unit
def test_decide_re_attestation_yields_same_content_hash() -> None:
    """Re-versioning the same Method (Versioned -> Versioned with same
    tag) emits a fresh event but the hash is identical because content
    is identical. Equivalence-detection semantic (Bazel input/output
    split): same content, same hash, recoverable across attestations."""
    state = _method(status=MethodStatus.VERSIONED, version="v2")
    first = _decide(state, tag="v2")
    second = _decide(state, tag="v2")
    assert first.content_hash == second.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_version_tag_change() -> None:
    """version_tag is the revision INDEX, not content. Same content
    under two different tags must produce the same hash."""
    state = _method()
    event_v2 = _decide(state, tag="v2")
    event_v3 = _decide(state, tag="v3")
    assert event_v2.content_hash == event_v3.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_source_status() -> None:
    """Lifecycle (derived in evolver from event type) does not enter
    the hash. Versioning from Defined vs from Versioned with the same
    content subset must produce the same hash."""
    defined_state = _method(status=MethodStatus.DEFINED)
    versioned_state = _method(status=MethodStatus.VERSIONED, version="v1")
    from_defined = _decide(defined_state, tag="v2")
    from_versioned = _decide(versioned_state, tag="v2")
    assert from_defined.content_hash == from_versioned.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_needed_family_ids_ordering() -> None:
    """Set-typed fields are unordered; canonicalization sorts members
    so the hash is independent of iteration order across processes."""
    state_a = _method(needed_family_ids=frozenset({_FIXED_FAMILY_A, _FIXED_FAMILY_B}))
    state_b = _method(needed_family_ids=frozenset({_FIXED_FAMILY_B, _FIXED_FAMILY_A}))
    assert _decide(state_a).content_hash == _decide(state_b).content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_needed_assembly_ids_ordering() -> None:
    """needed_assembly_ids is set-typed; content_subset sorts by UUID
    string form so the hash is iteration-order-invariant."""
    state_a = _method(needed_assembly_ids=frozenset({_FIXED_ASM_A, _FIXED_ASM_B}))
    state_b = _method(needed_assembly_ids=frozenset({_FIXED_ASM_B, _FIXED_ASM_A}))
    assert _decide(state_a).content_hash == _decide(state_b).content_hash


# ---------- Sensitivity (different content -> different hash) ----------


@pytest.mark.unit
def test_decide_hash_sensitive_to_name() -> None:
    a = _decide(_method(name="A"))
    b = _decide(_method(name="B"))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_parameters_schema() -> None:
    schema_a = {"type": "object", "properties": {"energy": {"type": "number"}}}
    schema_b = {"type": "object", "properties": {"energy": {"type": "integer"}}}
    a = _decide(_method(parameters_schema=schema_a))
    b = _decide(_method(parameters_schema=schema_b))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_capability_id() -> None:
    a = _decide(_method(capability_id=_FIXED_CAP_ID))
    b = _decide(_method(capability_id=uuid4()))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_needed_family_ids_membership() -> None:
    a = _decide(_method(needed_family_ids=frozenset({_FIXED_FAMILY_A})))
    b = _decide(_method(needed_family_ids=frozenset({_FIXED_FAMILY_A, _FIXED_FAMILY_B})))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_needed_supplies() -> None:
    a = _decide(_method(needed_supplies=frozenset({"nitrogen"})))
    b = _decide(_method(needed_supplies=frozenset({"helium"})))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_needed_assembly_ids_membership() -> None:
    """Adding an Assembly to the requirement set changes the hash;
    needed_assembly_ids participates in content identity (anti-hook #10)."""
    a = _decide(_method(needed_assembly_ids=frozenset({_FIXED_ASM_A})))
    b = _decide(_method(needed_assembly_ids=frozenset({_FIXED_ASM_A, _FIXED_ASM_B})))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_execution_pattern() -> None:
    """execution_pattern participates in content identity (L5):
    two Methods differing only in workload shape are different recipes,
    and an unclassified (None) Method differs from a classified one."""
    unclassified = _decide(_method(execution_pattern=None))
    batch = _decide(_method(execution_pattern=ExecutionPattern.BATCH))
    iterative = _decide(_method(execution_pattern=ExecutionPattern.ITERATIVE))
    assert unclassified.content_hash != batch.content_hash
    assert batch.content_hash != iterative.content_hash
    assert unclassified.content_hash != iterative.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_monotone_quality() -> None:
    """The anytime-algorithm claim is part of the recipe's content."""
    a = _decide(_method(execution_pattern=ExecutionPattern.ITERATIVE, monotone_quality=False))
    b = _decide(_method(execution_pattern=ExecutionPattern.ITERATIVE, monotone_quality=True))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_differs_by_resumable_from_checkpoint() -> None:
    """The checkpoint-resumability claim is part of the recipe's content."""
    a = _decide(_method(resumable_from_checkpoint=False))
    b = _decide(_method(resumable_from_checkpoint=True))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_distinguishes_none_schema_from_empty_schema() -> None:
    """None means "no contract declared"; `{}` means "operator declared
    no parameters". Distinct semantics, distinct hash."""
    a = _decide(_method(parameters_schema=None))
    b = _decide(_method(parameters_schema={}))
    assert a.content_hash != b.content_hash
