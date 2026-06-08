"""Content-hash plumbing for the `version_plan` slice.

Pins the Candidate A adoption on the Plan aggregate per
[[project_content_addressed_identity_design]]. The decider computes a
SHA-256 of the canonical body bytes for the Plan's content subset
(`name + method_id + practice_id + asset_ids + default_parameters +
wires`) and pins it in the emitted PlanVersioned event. Tests in this
module cover:

  - golden vectors that detect any drift in the canonicalization
    pipeline (Pydantic dump, NFC, sort-keys, PAE wrap, SHA-256)
  - equivalence semantics (same content subset -> same hash;
    re-attestation preserved)
  - content sensitivity (different subset -> different hash) across
    each hashed field
  - exclusion guarantees (excluded fields do NOT affect the hash):
    version_tag, status, id

Lifecycle guards live in test_version_plan_decider.py to keep this
file focused on the hash itself.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanStatus,
    PlanVersioned,
    Wire,
)
from cora.recipe.features import version_plan
from cora.recipe.features.version_plan import VersionPlan
from cora.shared.content_hash import compute_content_hash

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_FIXED_PLAN_ID = UUID("01900000-0000-7000-8000-0000000000a1")
_FIXED_METHOD_ID = UUID("00000000-0000-0000-0000-000000000001")
_FIXED_PRACTICE_ID = UUID("00000000-0000-0000-0000-000000000002")
_FIXED_ASSET_X = UUID("00000000-0000-0000-0000-000000000003")
_FIXED_ASSET_Y = UUID("33333333-3333-3333-3333-333333333333")
_FIXED_ASSET_Z = UUID("44444444-4444-4444-4444-444444444444")

# Golden vectors precomputed via `compute_content_hash(
#     event_type_to_payload_type("PlanVersioned"), <content_subset>)`.
# Pinned here so future Pydantic / canonicalization / payloadType-scheme
# drift trips a single fixture rather than every consumer test.
_GOLDEN_EMPTY = "52d000aecd28a4180121ea8e9c64e18b41419e6a185b7fca35417328842c520d"
_GOLDEN_POPULATED = "72856a444564c736119999e3160ad7724f303c0d2630269cb3ba480a0d47ffce"


def _plan(
    *,
    name: str = "EmptyPlan",
    method_id: UUID | None = _FIXED_METHOD_ID,
    practice_id: UUID = _FIXED_PRACTICE_ID,
    asset_ids: frozenset[UUID] = frozenset({_FIXED_ASSET_X}),
    default_parameters: dict[str, Any] | None = None,
    wires: frozenset[Wire] = frozenset(),
    status: PlanStatus = PlanStatus.DEFINED,
    version: str | None = None,
) -> Plan:
    return Plan(
        id=_FIXED_PLAN_ID,
        name=PlanName(name),
        practice_id=practice_id,
        asset_ids=asset_ids,
        status=status,
        version=version,
        method_id=method_id,
        default_parameters=default_parameters if default_parameters is not None else {},
        wires=wires,
    )


def _decide(state: Plan, *, tag: str = "v2") -> PlanVersioned:
    events = version_plan.decide(
        state=state,
        command=VersionPlan(plan_id=state.id, version_tag=tag),
        now=_NOW,
    )
    event = events[0]
    assert isinstance(event, PlanVersioned)
    return event


# ---------- Golden vectors ----------


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_minimal_plan() -> None:
    """Minimal Plan (single asset, no defaults, no wires) must hash to
    the pinned golden vector. Drift in any layer of the canonicalization
    pipeline (Pydantic, NFC, sort-keys, PAE, SHA-256) or in the locked
    content-subset shape moves this hash."""
    state = _plan()
    event = _decide(state)
    assert event.content_hash == _GOLDEN_EMPTY


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_populated_plan() -> None:
    """Populated Plan with every hashed field non-default. Catches any
    refactor that drops or reorders a content-subset member."""
    state = _plan(
        name="TomographyOnUnit-32-ID",
        method_id=UUID("11111111-1111-1111-1111-111111111111"),
        practice_id=UUID("22222222-2222-2222-2222-222222222222"),
        asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}),
        default_parameters={"energy": 12.0, "angle_count": 1500},
        wires=frozenset(
            {
                Wire(
                    source_asset_id=_FIXED_ASSET_Y,
                    source_port_name="trigger_out",
                    target_asset_id=_FIXED_ASSET_Z,
                    target_port_name="trigger_in",
                ),
                Wire(
                    source_asset_id=_FIXED_ASSET_Z,
                    source_port_name="data_out",
                    target_asset_id=_FIXED_ASSET_Y,
                    target_port_name="data_in",
                ),
            }
        ),
    )
    event = _decide(state)
    assert event.content_hash == _GOLDEN_POPULATED


# ---------- Shape ----------


@pytest.mark.unit
def test_decide_content_hash_is_64_char_lowercase_hex() -> None:
    state = _plan()
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
    state = _plan(
        name="TomographyOnUnit-32-ID",
        default_parameters={"energy": 12.0},
    )
    event = _decide(state)
    expected = compute_content_hash(
        "application/vnd.cora.plan-versioned+json",
        {
            "name": "TomographyOnUnit-32-ID",
            "method_id": str(_FIXED_METHOD_ID),
            "practice_id": str(_FIXED_PRACTICE_ID),
            "asset_ids": [str(_FIXED_ASSET_X)],
            "default_parameters": {"energy": 12.0},
            "wires": [],
            # role_bindings joined the content subset when slice 2 of
            # positional role-tagging landed; empty list for a Plan
            # with no bindings.
            "role_bindings": [],
        },
    )
    assert event.content_hash == expected


# ---------- Equivalence (same content -> same hash) ----------


@pytest.mark.unit
def test_decide_re_attestation_yields_same_content_hash() -> None:
    """Re-versioning the same Plan (Versioned -> Versioned with same
    tag) emits a fresh event but the hash is identical because content
    is identical. Equivalence-detection semantic (Bazel input/output
    split): same content, same hash, recoverable across attestations."""
    state = _plan(status=PlanStatus.VERSIONED, version="v2")
    first = _decide(state, tag="v2")
    second = _decide(state, tag="v2")
    assert first.content_hash == second.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_version_tag_change() -> None:
    """version_tag is the revision INDEX, not content. Same content
    under two different tags must produce the same hash."""
    state = _plan()
    event_v2 = _decide(state, tag="v2")
    event_v3 = _decide(state, tag="v3")
    assert event_v2.content_hash == event_v3.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_source_status() -> None:
    """Lifecycle (derived in evolver from event type) does not enter
    the hash. Versioning from Defined vs from Versioned with the same
    content subset must produce the same hash."""
    defined_state = _plan(status=PlanStatus.DEFINED)
    versioned_state = _plan(status=PlanStatus.VERSIONED, version="v1")
    from_defined = _decide(defined_state, tag="v2")
    from_versioned = _decide(versioned_state, tag="v2")
    assert from_defined.content_hash == from_versioned.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_asset_ids_ordering() -> None:
    """Set-typed fields are unordered; canonicalization sorts members
    so the hash is independent of iteration order across processes."""
    state_a = _plan(asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}))
    state_b = _plan(asset_ids=frozenset({_FIXED_ASSET_Z, _FIXED_ASSET_Y}))
    assert _decide(state_a).content_hash == _decide(state_b).content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_wires_ordering() -> None:
    """Wires is a frozenset; canonicalization sorts the rendered
    4-tuples so the hash is independent of iteration order."""
    wire_a = Wire(
        source_asset_id=_FIXED_ASSET_Y,
        source_port_name="out_a",
        target_asset_id=_FIXED_ASSET_Z,
        target_port_name="in_a",
    )
    wire_b = Wire(
        source_asset_id=_FIXED_ASSET_Y,
        source_port_name="out_b",
        target_asset_id=_FIXED_ASSET_Z,
        target_port_name="in_b",
    )
    state_a = _plan(
        asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}),
        wires=frozenset({wire_a, wire_b}),
    )
    state_b = _plan(
        asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}),
        wires=frozenset({wire_b, wire_a}),
    )
    assert _decide(state_a).content_hash == _decide(state_b).content_hash


# ---------- Sensitivity (different content -> different hash) ----------


@pytest.mark.unit
def test_decide_hash_sensitive_to_name() -> None:
    a = _decide(_plan(name="A"))
    b = _decide(_plan(name="B"))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_method_id() -> None:
    a = _decide(_plan(method_id=_FIXED_METHOD_ID))
    b = _decide(_plan(method_id=uuid4()))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_practice_id() -> None:
    a = _decide(_plan(practice_id=_FIXED_PRACTICE_ID))
    b = _decide(_plan(practice_id=uuid4()))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_asset_ids_membership() -> None:
    a = _decide(_plan(asset_ids=frozenset({_FIXED_ASSET_X})))
    b = _decide(_plan(asset_ids=frozenset({_FIXED_ASSET_X, _FIXED_ASSET_Y})))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_default_parameters() -> None:
    a = _decide(_plan(default_parameters={"energy": 12.0}))
    b = _decide(_plan(default_parameters={"energy": 14.0}))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_wires_membership() -> None:
    wire = Wire(
        source_asset_id=_FIXED_ASSET_Y,
        source_port_name="trigger_out",
        target_asset_id=_FIXED_ASSET_Z,
        target_port_name="trigger_in",
    )
    a = _decide(_plan(asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}), wires=frozenset()))
    b = _decide(
        _plan(asset_ids=frozenset({_FIXED_ASSET_Y, _FIXED_ASSET_Z}), wires=frozenset({wire}))
    )
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_distinguishes_empty_vs_non_empty_default_parameters() -> None:
    """Empty defaults and a one-key dict produce distinct hashes — the
    payload bytes differ at the JSON object level."""
    a = _decide(_plan(default_parameters={}))
    b = _decide(_plan(default_parameters={"energy": 12.0}))
    assert a.content_hash != b.content_hash
