"""Unit tests for the `register_facility` slice's pure decider.

Pin the genesis-collision guard, the Site-no-parent and
Area-must-have-parent structural invariants, every-arm kind acceptance,
purity (same inputs -> same outputs), and handler-injected
facility_id / code / registered_by / now capture per the
non-determinism principle (capture, don't recompute).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityAlreadyExistsError,
    FacilityAreaMustHaveParentError,
    FacilityAreaParentMustBeSiteError,
    FacilityKind,
    FacilityName,
    FacilityParentNotFoundError,
    FacilitySiteCannotHaveParentError,
    FacilityStatus,
)
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.ports import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000fed101"))
_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000fed102"))
_PARENT_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000fed103"))
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000fed199"))
_CODE = FacilityCode("aps")
_AREA_CODE = FacilityCode("2-bm")
_DEFAULT_PARENT_LOOKUP_CODE = FacilityCode("aps")


def _site_command(**overrides: object) -> RegisterFacility:
    base: dict[str, object] = {
        "code": "aps",
        "display_name": "Advanced Photon Source",
        "kind": FacilityKind.SITE,
        "parent_id": None,
    }
    base.update(overrides)
    return RegisterFacility(**base)  # type: ignore[arg-type]


def _area_command(**overrides: object) -> RegisterFacility:
    base: dict[str, object] = {
        "code": "2-bm",
        "display_name": "2-BM Beamline",
        "kind": FacilityKind.AREA,
        "parent_id": _PARENT_FACILITY_ID,
    }
    base.update(overrides)
    return RegisterFacility(**base)  # type: ignore[arg-type]


def _site_parent_lookup(
    *,
    facility_id: FacilityId = _PARENT_FACILITY_ID,
    code: FacilityCode = _DEFAULT_PARENT_LOOKUP_CODE,
    kind: str = FacilityKind.SITE.value,
    status: str = FacilityStatus.ACTIVE.value,
) -> FacilityLookupResult:
    """Test helper: build a Site-tier parent FacilityLookupResult.

    Default values match the most common Area-with-Site-parent case.
    Override `kind` / `status` for invariant-violation paths.
    """
    return FacilityLookupResult(
        id=facility_id,
        code=code,
        kind=kind,
        status=status,
        trust_anchor_credential_ids=frozenset(),
    )


def _existing_site_state() -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_NOW,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


# ---------- genesis-collision guard ----------


@pytest.mark.unit
def test_register_facility_rejects_when_state_already_exists() -> None:
    """Genesis-only: a non-None state surfaces FacilityAlreadyExistsError."""
    with pytest.raises(FacilityAlreadyExistsError) as exc:
        register_facility.decide(
            state=_existing_site_state(),
            command=_site_command(),
            now=_NOW,
            facility_id=_FACILITY_ID,
            code=_CODE,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.code == _CODE


# ---------- Site invariant: kind=Site implies parent_id is None ----------


@pytest.mark.unit
def test_register_facility_accepts_site_without_parent() -> None:
    events = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.kind is FacilityKind.SITE
    assert event.parent_id is None


@pytest.mark.unit
def test_register_facility_rejects_site_with_non_null_parent() -> None:
    with pytest.raises(FacilitySiteCannotHaveParentError) as exc:
        register_facility.decide(
            state=None,
            command=_site_command(parent_id=_PARENT_FACILITY_ID),
            now=_NOW,
            facility_id=_FACILITY_ID,
            code=_CODE,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.code == _CODE
    assert exc.value.parent_id == _PARENT_FACILITY_ID


# ---------- Area invariant: kind=Area implies parent_id is non-None ----------


@pytest.mark.unit
def test_register_facility_accepts_area_with_parent() -> None:
    events = register_facility.decide(
        state=None,
        command=_area_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_AREA_CODE,
        registered_by=_PRINCIPAL_ID,
        parent_lookup_result=_site_parent_lookup(),
    )
    assert len(events) == 1
    event = events[0]
    assert event.kind is FacilityKind.AREA
    assert event.parent_id == _PARENT_FACILITY_ID


@pytest.mark.unit
def test_register_facility_rejects_area_with_missing_parent() -> None:
    """Slice 6 Sub-Slice A: when parent_lookup_result is None, raise
    FacilityParentNotFoundError (404)."""
    with pytest.raises(FacilityParentNotFoundError) as exc:
        register_facility.decide(
            state=None,
            command=_area_command(),
            now=_NOW,
            facility_id=_FACILITY_ID,
            code=_AREA_CODE,
            registered_by=_PRINCIPAL_ID,
            parent_lookup_result=None,
        )
    assert exc.value.code == _AREA_CODE
    assert exc.value.parent_id == _PARENT_FACILITY_ID


@pytest.mark.unit
def test_register_facility_rejects_area_with_area_parent() -> None:
    """Slice 6 Sub-Slice A: when parent.kind is Area (not Site), raise
    FacilityAreaParentMustBeSiteError (422)."""
    area_parent = _site_parent_lookup(kind=FacilityKind.AREA.value)
    with pytest.raises(FacilityAreaParentMustBeSiteError) as exc:
        register_facility.decide(
            state=None,
            command=_area_command(),
            now=_NOW,
            facility_id=_FACILITY_ID,
            code=_AREA_CODE,
            registered_by=_PRINCIPAL_ID,
            parent_lookup_result=area_parent,
        )
    assert exc.value.code == _AREA_CODE
    assert exc.value.parent_id == _PARENT_FACILITY_ID
    assert exc.value.parent_kind == FacilityKind.AREA.value


@pytest.mark.unit
def test_register_facility_accepts_area_with_decommissioned_site_parent() -> None:
    """A Decommissioned Site is structurally still a Site; the decider does
    NOT filter on parent.status (operator chose to keep the lineage visible)."""
    decommissioned_parent = _site_parent_lookup(
        status=FacilityStatus.DECOMMISSIONED.value,
    )
    events = register_facility.decide(
        state=None,
        command=_area_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_AREA_CODE,
        registered_by=_PRINCIPAL_ID,
        parent_lookup_result=decommissioned_parent,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_register_facility_rejects_area_with_null_parent() -> None:
    with pytest.raises(FacilityAreaMustHaveParentError) as exc:
        register_facility.decide(
            state=None,
            command=_area_command(parent_id=None),
            now=_NOW,
            facility_id=_FACILITY_ID,
            code=_AREA_CODE,
            registered_by=_PRINCIPAL_ID,
        )
    assert exc.value.code == _AREA_CODE


# ---------- event payload completeness ----------


@pytest.mark.unit
def test_register_facility_event_carries_command_fields_verbatim() -> None:
    events = register_facility.decide(
        state=None,
        command=_site_command(display_name="Advanced Photon Source"),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    event = events[0]
    assert event.facility_id == _FACILITY_ID
    assert event.code == _CODE
    assert event.display_name == "Advanced Photon Source"
    assert event.kind is FacilityKind.SITE
    assert event.registered_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW
    assert event.alternate_identifiers == frozenset()


@pytest.mark.unit
@pytest.mark.parametrize("kind", list(FacilityKind))
def test_register_facility_accepts_every_kind_arm(kind: FacilityKind) -> None:
    """The decider validates the closed enum at the Pydantic boundary; both
    Site and Area arms must reach the event verbatim (Site with null parent,
    Area with non-null parent)."""
    parent_lookup: FacilityLookupResult | None
    if kind is FacilityKind.SITE:
        command = _site_command(kind=kind)
        code = _CODE
        parent_lookup = None
    else:
        command = _area_command(kind=kind)
        code = _AREA_CODE
        parent_lookup = _site_parent_lookup()
    events = register_facility.decide(
        state=None,
        command=command,
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=code,
        registered_by=_PRINCIPAL_ID,
        parent_lookup_result=parent_lookup,
    )
    assert events[0].kind is kind


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_register_facility_is_pure_same_inputs_same_outputs() -> None:
    first = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    second = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_register_facility_uses_handler_injected_facility_id_verbatim() -> None:
    injected = FacilityId(uuid4())
    events = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=injected,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].facility_id == injected


@pytest.mark.unit
def test_register_facility_uses_handler_injected_code_verbatim() -> None:
    injected = FacilityCode("maxiv")
    events = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=injected,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].code == injected


@pytest.mark.unit
def test_register_facility_uses_handler_injected_actor_id_verbatim() -> None:
    injected = ActorId(uuid4())
    events = register_facility.decide(
        state=None,
        command=_site_command(),
        now=_NOW,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=injected,
    )
    assert events[0].registered_by == injected


@pytest.mark.unit
def test_register_facility_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2027, 1, 15, 9, 30, 0, tzinfo=UTC)
    events = register_facility.decide(
        state=None,
        command=_site_command(),
        now=custom_now,
        facility_id=_FACILITY_ID,
        code=_CODE,
        registered_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
