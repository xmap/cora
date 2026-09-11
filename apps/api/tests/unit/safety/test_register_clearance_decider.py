"""Pure-decider tests for `register_clearance` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
    ClearanceTemplateStatusValue,
)
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceAlreadyExistsError,
    ClearanceFacilityNotFoundError,
    ClearanceTitle,
    HazardDeclaration,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalIdError,
    InvalidClearanceTitleError,
    InvalidClearanceValidityWindowError,
    RunBinding,
    SubjectBinding,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    ClearanceTemplateNotBindableError,
    ClearanceTemplateNotFoundError,
    clearance_template_stream_id,
)
from cora.safety.features import register_clearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.shared.facility_code import FacilityCode

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _lookup_result(code: str = "aps") -> FacilityLookupResult:
    """Build a stub FacilityLookupResult for the given facility slug."""
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


def _template_lookup_result(
    template_id: UUID,
    facility_code: str = "aps",
    code: str = "ESAF",
    *,
    status: ClearanceTemplateStatusValue = "Active",
    version: int = 1,
) -> ClearanceTemplateLookupResult:
    """Build a stub ClearanceTemplateLookupResult for decider tests."""
    return ClearanceTemplateLookupResult(
        id=template_id,
        facility_code=facility_code,
        code=code,
        status=status,
        version=version,
    )


def _template_id(facility_code: str = "aps", code: str = "ESAF") -> ClearanceTemplateId:
    """Deterministic ClearanceTemplateId matching the auto-seed namespace."""
    return ClearanceTemplateId(clearance_template_stream_id(facility_code, code))


@pytest.mark.unit
def test_decide_emits_clearance_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    rid = uuid4()
    tid = _template_id("aps", "ESAF")
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="Pilot ESAF",
            bindings=frozenset({RunBinding(run_id=rid)}),
        ),
        now=_NOW,
        new_id=new_id,
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
    )
    assert len(events) == 1
    event = events[0]
    assert event.clearance_id == new_id
    assert event.template_id == tid
    assert event.template_code == "ESAF"
    assert event.facility_code == "aps"
    assert event.title == "Pilot ESAF"
    assert event.bindings == ({"kind": "Run", "id": str(rid)},)
    assert event.declarations == ()
    assert event.risk_band is None
    assert event.external_id is None
    assert event.valid_from is None
    assert event.valid_until is None
    assert event.parent_id is None
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_serializes_multi_binding() -> None:
    sid, aid, rid = uuid4(), uuid4(), uuid4()
    tid = _template_id("aps", "SAF")
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="Multi",
            bindings=frozenset({SubjectBinding(subject_id=sid), RunBinding(run_id=rid)}),
        ),
        now=_NOW,
        new_id=aid,
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "SAF"),
    )
    binding_kinds = {b["kind"] for b in events[0].bindings}
    assert binding_kinds == {"Subject", "Run"}


@pytest.mark.unit
def test_decide_serializes_declaration_with_classifications() -> None:
    sid = uuid4()
    tid = _template_id("aps", "ESAF")
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="With hazards",
            bindings=frozenset({SubjectBinding(subject_id=sid)}),
            declarations=frozenset(
                {
                    HazardDeclaration(
                        target=SubjectBinding(subject_id=sid),
                        classifications=frozenset({RiskBand.YELLOW}),
                        mitigations=frozenset({"ppe:gloves"}),
                    )
                }
            ),
            risk_band=RiskBand.YELLOW,
        ),
        now=_NOW,
        new_id=uuid4(),
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
    )
    assert len(events[0].declarations) == 1
    assert events[0].risk_band == "Yellow"


@pytest.mark.unit
def test_decide_trims_external_id() -> None:
    tid = _template_id("aps", "ESAF")
    events = register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="t",
            bindings=frozenset({RunBinding(run_id=uuid4())}),
            external_id="  ESAF-12345  ",
        ),
        now=_NOW,
        new_id=uuid4(),
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
    )
    assert events[0].external_id == "ESAF-12345"


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    tid = _template_id("aps", "ESAF")
    existing = Clearance(
        id=uuid4(),
        template_id=tid,
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("existing"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
    )
    with pytest.raises(ClearanceAlreadyExistsError) as exc_info:
        register_clearance.decide(
            state=existing,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="other",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )
    assert exc_info.value.clearance_id == existing.id


@pytest.mark.unit
def test_decide_rejects_unknown_facility_code() -> None:
    """When the handler's FacilityLookup miss surfaces as
    facility_lookup_result=None, the decider raises
    ClearanceFacilityNotFoundError carrying the original slug from the
    command. Mirrors the Slice 8A register_asset precedent."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceFacilityNotFoundError) as exc_info:
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="unknown",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=None,
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )
    assert exc_info.value.facility_code == "unknown"


@pytest.mark.unit
def test_decide_rejects_unknown_template_id() -> None:
    """When the handler's ClearanceTemplateLookup miss surfaces as
    template_lookup_result=None, the decider raises
    ClearanceTemplateNotFoundError carrying the original template_id from
    the command. Mirrors the facility-lookup precedent."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceTemplateNotFoundError) as exc_info:
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=None,
        )
    assert exc_info.value.template_id == tid


@pytest.mark.unit
def test_decide_rejects_non_active_template() -> None:
    """A template exists but is not Active (Draft / Deprecated /
    Withdrawn): the decider raises ClearanceTemplateNotBindableError so
    operators can only bind to live templates."""
    tid = _template_id("aps", "ESAF")
    with pytest.raises(ClearanceTemplateNotBindableError) as exc_info:
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF", status="Draft"),
        )
    assert exc_info.value.template_id == tid


@pytest.mark.unit
def test_decide_rejects_empty_title() -> None:
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceTitleError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="   ",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_title() -> None:
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceTitleError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="a" * 201,
                bindings=frozenset({RunBinding(run_id=uuid4())}),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_empty_bindings() -> None:
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceBindingsError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset(),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_empty_external_id() -> None:
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceExternalIdError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                external_id="   ",
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_external_id() -> None:
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceExternalIdError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                external_id="a" * 101,
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_inverted_validity_window() -> None:
    later = datetime(2026, 5, 16, tzinfo=UTC)
    earlier = datetime(2026, 5, 15, tzinfo=UTC)
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceValidityWindowError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                valid_from=later,
                valid_until=earlier,
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_accepts_validity_window_when_only_one_side_provided() -> None:
    """Half-bounded windows are valid; only the inverted-both-sides case fails."""
    tid = _template_id("aps", "ESAF")
    register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="t",
            bindings=frozenset({RunBinding(run_id=uuid4())}),
            valid_from=_NOW,
            valid_until=None,
        ),
        now=_NOW,
        new_id=uuid4(),
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
    )


@pytest.mark.unit
def test_decide_rejects_zero_duration_validity_window() -> None:
    """`valid_from == valid_until` is degenerate (zero-duration window can never
    be Active); rejected at decider for the same reason as inverted windows."""
    instant = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceValidityWindowError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({RunBinding(run_id=uuid4())}),
                valid_from=instant,
                valid_until=instant,
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_rejects_declaration_target_not_in_bindings() -> None:
    """A HazardDeclaration whose target binding is NOT in the Clearance's
    bindings set is incoherent (the Clearance can't gate against an out-of-
    scope target). Rejected at decider per the subset-semantic invariant."""
    in_set_subject = uuid4()
    out_of_set_subject = uuid4()
    tid = _template_id("aps", "ESAF")
    with pytest.raises(InvalidClearanceDeclarationTargetError):
        register_clearance.decide(
            state=None,
            command=RegisterClearance(
                template_id=tid,
                facility_code="aps",
                title="t",
                bindings=frozenset({SubjectBinding(subject_id=in_set_subject)}),
                declarations=frozenset(
                    {
                        HazardDeclaration(
                            target=SubjectBinding(subject_id=out_of_set_subject),
                        )
                    }
                ),
            ),
            now=_NOW,
            new_id=uuid4(),
            facility_lookup_result=_lookup_result("aps"),
            template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
        )


@pytest.mark.unit
def test_decide_accepts_declaration_target_when_in_bindings() -> None:
    """Counterpart to the rejection test: target IN bindings is the happy path."""
    sid = uuid4()
    tid = _template_id("aps", "ESAF")
    register_clearance.decide(
        state=None,
        command=RegisterClearance(
            template_id=tid,
            facility_code="aps",
            title="t",
            bindings=frozenset({SubjectBinding(subject_id=sid)}),
            declarations=frozenset({HazardDeclaration(target=SubjectBinding(subject_id=sid))}),
        ),
        now=_NOW,
        new_id=uuid4(),
        facility_lookup_result=_lookup_result("aps"),
        template_lookup_result=_template_lookup_result(tid, "aps", "ESAF"),
    )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    rid = uuid4()
    tid = _template_id("aps", "ESAF")
    cmd = RegisterClearance(
        template_id=tid,
        facility_code="aps",
        title="repeatable",
        bindings=frozenset({RunBinding(run_id=rid)}),
    )
    lookup = _lookup_result("aps")
    template_lookup = _template_lookup_result(tid, "aps", "ESAF")
    first = register_clearance.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=new_id,
        facility_lookup_result=lookup,
        template_lookup_result=template_lookup,
    )
    second = register_clearance.decide(
        state=None,
        command=cmd,
        now=_NOW,
        new_id=new_id,
        facility_lookup_result=lookup,
        template_lookup_result=template_lookup,
    )
    assert first == second
