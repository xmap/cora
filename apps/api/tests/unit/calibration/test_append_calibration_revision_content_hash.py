"""Content-hash plumbing for the `append_calibration_revision` slice.

Pins the Candidate A adoption on the CalibrationRevision VO per
[[project_content_addressed_identity_design]]. The decider computes a
SHA-256 of the canonical body bytes for the revision's content subset
(`value + status + source_kind + source_id + decided_by_decision_id +
supersedes_revision_id`) and pins it in the emitted
CalibrationRevisionAppended event. Tests in this module cover:

  - golden vectors that detect any drift in the canonicalization
    pipeline (Pydantic dump, NFC, sort-keys, PAE wrap, SHA-256)
  - equivalence semantics (same content subset -> same hash;
    re-attestation preserved)
  - content sensitivity (different subset -> different hash) across
    each hashed field
  - exclusion guarantees (excluded fields do NOT affect the hash):
    revision_id, established_at, established_by

Lifecycle and validation guards live in test_append_calibration_revision_decider.py
to keep this file focused on the hash itself.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    Calibration,
    CalibrationRevision,
    CalibrationStatus,
    ComputedSource,
    MeasuredSource,
)
from cora.calibration.aggregates.calibration.state import CalibrationSource
from cora.calibration.features import append_calibration_revision
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.shared.content_hash import compute_content_hash
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca2001"))
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca2002")
_CAL_ID = UUID("01900000-0000-7000-8000-000000ca2003")
_REV_ID_1 = UUID("01900000-0000-7000-8000-000000ca2004")
_NEW_REV_ID = UUID("01900000-0000-7000-8000-000000ca2006")
_PROC_ID = UUID("01900000-0000-7000-8000-000000ca2007")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000ca2008")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000ca2009")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca200a"))

# Golden vectors precomputed via `compute_content_hash(
#     event_type_to_payload_type("CalibrationRevisionAppended"), <subset>)`.
# Pinned here so future Pydantic / canonicalization / payloadType-scheme
# drift trips a single fixture rather than every consumer test.
_GOLDEN_MINIMAL = "88d1f29939cb4f1ee027b754adafbe3b64df991cca9beeb42f716b2293accdae"
_GOLDEN_POPULATED = "2488d38f28ee0806e25722a7799adbbede185b80c20871fe272528a5baf836d8"


def _prior_revision(*, revision_id: UUID = _REV_ID_1) -> CalibrationRevision:
    return CalibrationRevision(
        revision_id=revision_id,
        value={"center": 1.0},
        status=CalibrationStatus.PROVISIONAL,
        source=MeasuredSource(procedure_id=_PROC_ID),
        established_at=_NOW,
        established_by=_PRINCIPAL_ID,
        decided_by_decision_id=None,
        supersedes_revision_id=None,
    )


def _state(*, revisions: tuple[CalibrationRevision, ...] = ()) -> Calibration:
    return Calibration(
        id=_CAL_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy": 25.0, "optics_config": "5x"},
        description=None,
        revisions=revisions,
        defined_at=_NOW,
        defined_by=_PRINCIPAL_ID,
    )


def _decide(
    *,
    value: dict[str, Any] | None = None,
    status: CalibrationStatus = CalibrationStatus.PROVISIONAL,
    source: CalibrationSource | None = None,
    decided_by_decision_id: UUID | None = None,
    supersedes_revision_id: UUID | None = None,
    revisions: tuple[CalibrationRevision, ...] = (),
    new_revision_id: UUID = _NEW_REV_ID,
    established_by: ActorId = _PRINCIPAL_ID,
) -> Any:
    cmd = AppendCalibrationRevision(
        calibration_id=_CAL_ID,
        value=value if value is not None else {"center": 1024.5},
        status=status,
        source=source if source is not None else MeasuredSource(procedure_id=_PROC_ID),
        decided_by_decision_id=decided_by_decision_id,
        supersedes_revision_id=supersedes_revision_id,
    )
    events = append_calibration_revision.decide(
        state=_state(revisions=revisions),
        command=cmd,
        now=_NOW,
        new_revision_id=new_revision_id,
        established_by=established_by,
    )
    return events[0]


# ---------- Golden vectors ----------


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_minimal_revision() -> None:
    """Minimal revision (measured source, provisional, no optionals)
    must hash to the pinned golden vector. Drift in any layer of the
    canonicalization pipeline (Pydantic, NFC, sort-keys, PAE, SHA-256)
    or in the locked content-subset shape moves this hash."""
    event = _decide()
    assert event.content_hash == _GOLDEN_MINIMAL


@pytest.mark.unit
def test_decide_content_hash_matches_golden_for_populated_revision() -> None:
    """Populated revision with every hashed field non-default. Catches
    any refactor that drops or reorders a content-subset member."""
    event = _decide(
        value={"center": 1024.5, "uncertainty": 0.3},
        status=CalibrationStatus.VERIFIED,
        source=ComputedSource(dataset_id=_DATASET_ID),
        decided_by_decision_id=_DECISION_ID,
        supersedes_revision_id=_REV_ID_1,
        revisions=(_prior_revision(),),
    )
    assert event.content_hash == _GOLDEN_POPULATED


# ---------- Shape ----------


@pytest.mark.unit
def test_decide_content_hash_is_64_char_lowercase_hex() -> None:
    event = _decide()
    assert event.content_hash is not None
    assert len(event.content_hash) == 64
    assert event.content_hash == event.content_hash.lower()
    assert all(c in "0123456789abcdef" for c in event.content_hash)


@pytest.mark.unit
def test_decide_content_hash_matches_helper_output_directly() -> None:
    """The decider's hash must equal the helper invoked on the locked
    content subset. Locks the contract that the decider does NOT add
    or rename fields beyond the documented subset."""
    event = _decide(
        value={"center": 1024.5},
        source=AssertedSource(asserted_by=_ACTOR_ID),
    )
    expected = compute_content_hash(
        "application/vnd.cora.calibration-revision-appended+json",
        {
            "value": {"center": 1024.5},
            "status": "Provisional",
            "source_kind": "asserted",
            "source_id": str(_ACTOR_ID),
            "decided_by_decision_id": None,
            "supersedes_revision_id": None,
        },
    )
    assert event.content_hash == expected


# ---------- Equivalence (same content -> same hash) ----------


@pytest.mark.unit
def test_decide_re_attestation_yields_same_content_hash() -> None:
    """Appending two revisions with identical content (different
    revision_id + envelope) yields the same content hash. Equivalence-
    detection semantic (Bazel input/output split): same content, same
    hash, recoverable across attestations."""
    first = _decide(new_revision_id=_NEW_REV_ID)
    second = _decide(new_revision_id=uuid4())
    assert first.content_hash == second.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_revision_id() -> None:
    """revision_id is identity, not content. Same content under two
    different revision_ids must produce the same hash."""
    event_a = _decide(new_revision_id=_NEW_REV_ID)
    event_b = _decide(new_revision_id=uuid4())
    assert event_a.content_hash == event_b.content_hash


@pytest.mark.unit
def test_decide_hash_invariant_under_established_by() -> None:
    """established_by is envelope metadata (analog of
    PlanVersioned.versioned_by), not content. Same content
    decided by two different actors must produce the same hash."""
    event_a = _decide(established_by=_PRINCIPAL_ID)
    event_b = _decide(established_by=ActorId(uuid4()))
    assert event_a.content_hash == event_b.content_hash


# ---------- Sensitivity (different content -> different hash) ----------


@pytest.mark.unit
def test_decide_hash_sensitive_to_value() -> None:
    a = _decide(value={"center": 1024.5})
    b = _decide(value={"center": 1025.0})
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_status() -> None:
    a = _decide(status=CalibrationStatus.PROVISIONAL)
    b = _decide(status=CalibrationStatus.VERIFIED)
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_source_kind() -> None:
    """Switching arm of the polymorphic source union changes both
    source_kind and source_id slots in the subset; hash must move."""
    a = _decide(source=MeasuredSource(procedure_id=_PROC_ID))
    b = _decide(source=ComputedSource(dataset_id=_PROC_ID))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_source_id_within_same_kind() -> None:
    a = _decide(source=MeasuredSource(procedure_id=_PROC_ID))
    b = _decide(source=MeasuredSource(procedure_id=uuid4()))
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_decided_by_decision_id() -> None:
    a = _decide(decided_by_decision_id=None)
    b = _decide(decided_by_decision_id=_DECISION_ID)
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_sensitive_to_supersedes_revision_id() -> None:
    """supersedes_revision_id is a derivation edge that materially
    changes the revision's meaning; hash must distinguish."""
    a = _decide()
    b = _decide(
        supersedes_revision_id=_REV_ID_1,
        revisions=(_prior_revision(),),
    )
    assert a.content_hash != b.content_hash


@pytest.mark.unit
def test_decide_hash_distinguishes_empty_vs_non_empty_value_keys() -> None:
    """Adding a key to the value dict changes the payload bytes at the
    JSON object level even when existing keys are unchanged."""
    a = _decide(value={"center": 1024.5})
    b = _decide(value={"center": 1024.5, "uncertainty": 0.3})
    assert a.content_hash != b.content_hash
