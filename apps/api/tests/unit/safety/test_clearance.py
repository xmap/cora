"""ClearanceTitle VO + ClearanceBinding + HazardDeclaration + ReviewStep + Clearance + enums."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    CLEARANCE_HAZARD_NOTES_MAX_LENGTH,
    CLEARANCE_MITIGATION_REF_MAX_LENGTH,
    CLEARANCE_TITLE_MAX_LENGTH,
    AssetBinding,
    Clearance,
    ClearanceKind,
    ClearanceStatus,
    ClearanceTitle,
    ExternalRefBinding,
    HazardDeclaration,
    InvalidClearanceHazardNotesError,
    InvalidClearanceMitigationRefError,
    InvalidClearanceTitleError,
    ProcedureBinding,
    ReviewStep,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance.hazard_classification import NFPA704Rating, RiskBand
from cora.shared.identifier import Identifier, InvalidIdentifierError
from cora.shared.identity import ActorId

# ---------- ClearanceTitle VO ----------


@pytest.mark.unit
def test_clearance_title_accepts_normal_string() -> None:
    title = ClearanceTitle("Pilot ESAF for 2-BM tomography")
    assert title.value == "Pilot ESAF for 2-BM tomography"


@pytest.mark.unit
def test_clearance_title_trims_whitespace() -> None:
    title = ClearanceTitle("  Test ESAF  ")
    assert title.value == "Test ESAF"


@pytest.mark.unit
def test_clearance_title_rejects_empty() -> None:
    with pytest.raises(InvalidClearanceTitleError):
        ClearanceTitle("")


@pytest.mark.unit
def test_clearance_title_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidClearanceTitleError):
        ClearanceTitle("   \t\n   ")


@pytest.mark.unit
def test_clearance_title_rejects_too_long() -> None:
    with pytest.raises(InvalidClearanceTitleError):
        ClearanceTitle("a" * (CLEARANCE_TITLE_MAX_LENGTH + 1))


@pytest.mark.unit
def test_clearance_title_accepts_max_length() -> None:
    title = ClearanceTitle("a" * CLEARANCE_TITLE_MAX_LENGTH)
    assert len(title.value) == CLEARANCE_TITLE_MAX_LENGTH


# ---------- ClearanceBinding union variants ----------


@pytest.mark.unit
def test_subject_binding_carries_subject_id() -> None:
    sid = uuid4()
    b = SubjectBinding(subject_id=sid)
    assert b.subject_id == sid


@pytest.mark.unit
def test_asset_binding_carries_asset_id() -> None:
    aid = uuid4()
    b = AssetBinding(asset_id=aid)
    assert b.asset_id == aid


@pytest.mark.unit
def test_run_binding_carries_run_id() -> None:
    rid = uuid4()
    b = RunBinding(run_id=rid)
    assert b.run_id == rid


@pytest.mark.unit
def test_procedure_binding_carries_procedure_id() -> None:
    pid = uuid4()
    b = ProcedureBinding(procedure_id=pid)
    assert b.procedure_id == pid


@pytest.mark.unit
def test_external_ref_binding_accepts_valid_pair() -> None:
    b = ExternalRefBinding(ref=Identifier(scheme="proposal", value="GUP-12345"))
    assert b.ref.scheme == "proposal"
    assert b.ref.value == "GUP-12345"


@pytest.mark.unit
def test_external_ref_binding_trims_fields() -> None:
    b = ExternalRefBinding(ref=Identifier(scheme="  proposal  ", value="  GUP-12345  "))
    assert b.ref.scheme == "proposal"
    assert b.ref.value == "GUP-12345"


@pytest.mark.unit
def test_external_ref_binding_rejects_empty_scheme() -> None:
    with pytest.raises(InvalidIdentifierError):
        ExternalRefBinding(ref=Identifier(scheme="   ", value="x"))


@pytest.mark.unit
def test_external_ref_binding_rejects_empty_value() -> None:
    with pytest.raises(InvalidIdentifierError):
        ExternalRefBinding(ref=Identifier(scheme="x", value="   "))


# ---------- HazardDeclaration ----------


@pytest.mark.unit
def test_hazard_declaration_accepts_minimal_form() -> None:
    sid = uuid4()
    d = HazardDeclaration(target=SubjectBinding(subject_id=sid))
    assert d.target == SubjectBinding(subject_id=sid)
    assert d.classifications == frozenset()
    assert d.mitigations == frozenset()
    assert d.notes is None


@pytest.mark.unit
def test_hazard_declaration_accepts_classifications_and_mitigations() -> None:
    sid = uuid4()
    rating = NFPA704Rating(health=2, flammability=1, instability=0)
    d = HazardDeclaration(
        target=SubjectBinding(subject_id=sid),
        classifications=frozenset({rating, RiskBand.YELLOW}),
        mitigations=frozenset({"training:hazcom-2026", "ppe:nitrile_gloves"}),
        notes="W-C alignment phantom",
    )
    assert RiskBand.YELLOW in d.classifications
    assert rating in d.classifications
    assert "training:hazcom-2026" in d.mitigations
    assert d.notes == "W-C alignment phantom"


@pytest.mark.unit
def test_hazard_declaration_rejects_empty_mitigation_ref() -> None:
    sid = uuid4()
    with pytest.raises(InvalidClearanceMitigationRefError):
        HazardDeclaration(
            target=SubjectBinding(subject_id=sid),
            mitigations=frozenset({"   "}),
        )


@pytest.mark.unit
def test_hazard_declaration_rejects_oversized_mitigation_ref() -> None:
    sid = uuid4()
    with pytest.raises(InvalidClearanceMitigationRefError):
        HazardDeclaration(
            target=SubjectBinding(subject_id=sid),
            mitigations=frozenset({"x" * (CLEARANCE_MITIGATION_REF_MAX_LENGTH + 1)}),
        )


@pytest.mark.unit
def test_hazard_declaration_rejects_oversized_notes() -> None:
    sid = uuid4()
    with pytest.raises(InvalidClearanceHazardNotesError):
        HazardDeclaration(
            target=SubjectBinding(subject_id=sid),
            notes="x" * (CLEARANCE_HAZARD_NOTES_MAX_LENGTH + 1),
        )


@pytest.mark.unit
def test_hazard_declaration_normalizes_whitespace_only_notes_to_none() -> None:
    sid = uuid4()
    d = HazardDeclaration(target=SubjectBinding(subject_id=sid), notes="   ")
    assert d.notes is None


# ---------- ReviewStep ----------


@pytest.mark.unit
def test_reviewer_step_carries_all_fields() -> None:
    actor = ActorId(uuid4())
    now = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    step = ReviewStep(
        step_index=0,
        role="BeamlineScientist",
        decided_by=actor,
        decision="Approved",
        decided_at=now,
        notes="LGTM",
    )
    assert step.step_index == 0
    assert step.role == "BeamlineScientist"
    assert step.decided_by == actor
    assert step.decision == "Approved"
    assert step.notes == "LGTM"


# ---------- Clearance aggregate ----------


@pytest.mark.unit
def test_clearance_is_frozen() -> None:
    c = Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("test"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )
    with pytest.raises((AttributeError, TypeError)):
        c.status = ClearanceStatus.ACTIVE  # type: ignore[misc]


@pytest.mark.unit
def test_clearance_status_defaults_to_defined() -> None:
    c = Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("test"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )
    assert c.status == ClearanceStatus.DEFINED


@pytest.mark.unit
def test_clearance_optional_fields_default_to_none_or_empty() -> None:
    c = Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("test"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )
    assert c.declarations == frozenset()
    assert c.risk_band is None
    assert c.review_steps == ()
    assert c.external_id is None
    assert c.parent_id is None
    assert c.valid_from is None
    assert c.valid_until is None
    assert c.next_review_due_at is None


# ---------- Enum locks ----------


@pytest.mark.unit
def test_clearance_status_has_eight_locked_values() -> None:
    assert {s.value for s in ClearanceStatus} == {
        "Defined",
        "Submitted",
        "UnderReview",
        "Approved",
        "Active",
        "Expired",
        "Rejected",
        "Superseded",
    }


@pytest.mark.unit
def test_clearance_kind_has_twelve_locked_values() -> None:
    """12 values cover the 9 surveyed facilities (some have two coexisting forms)."""
    assert {k.value for k in ClearanceKind} == {
        "ESAF",
        "SAF",
        "AForm",
        "DUO",
        "ESRA",
        "ERA",
        "PLHD",
        "DOOR",
        "BTR",
        "Form9",
    }
