"""SupplyName + SupplyReason VOs + status / scope / trigger enums + Supply aggregate.

`InvalidSupplyKindError` (no VO) is raised by the `register_supply`
decider via `validate_bounded_text`; its empty / too-long paths are
pinned in `test_register_supply_decider.py`. Same for the cross-
aggregate guards (`SupplyAlreadyExistsError` / `SupplyNotFoundError`
/ `SupplyCannotMarkAvailableError`) — raised by deciders / handlers
and tested at those layers.
"""

from uuid import uuid4

import pytest

from cora.shared.facility_code import FacilityCode
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    InvalidSupplyNameError,
    InvalidSupplyReasonError,
    Supply,
    SupplyName,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)

_FACILITY_CODE = FacilityCode("aps")

# ---------- SupplyName VO ----------


@pytest.mark.unit
def test_supply_name_accepts_normal_string() -> None:
    name = SupplyName("2-BM LN2 drop")
    assert name.value == "2-BM LN2 drop"


@pytest.mark.unit
def test_supply_name_trims_whitespace() -> None:
    name = SupplyName("  Central LN2 plant  ")
    assert name.value == "Central LN2 plant"


@pytest.mark.unit
def test_supply_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidSupplyNameError):
        SupplyName("")


@pytest.mark.unit
def test_supply_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidSupplyNameError):
        SupplyName("   \t\n   ")


@pytest.mark.unit
def test_supply_name_rejects_too_long() -> None:
    with pytest.raises(InvalidSupplyNameError):
        SupplyName("a" * 201)


@pytest.mark.unit
def test_supply_name_accepts_max_length() -> None:
    name = SupplyName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_supply_name_is_frozen() -> None:
    name = SupplyName("Central LN2")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- SupplyReason VO ----------


@pytest.mark.unit
def test_supply_reason_accepts_normal_string() -> None:
    reason = SupplyReason("operator walkdown confirms LN2 flowing")
    assert reason.value == "operator walkdown confirms LN2 flowing"


@pytest.mark.unit
def test_supply_reason_trims_whitespace() -> None:
    reason = SupplyReason("  control room reports beam delivered  ")
    assert reason.value == "control room reports beam delivered"


@pytest.mark.unit
def test_supply_reason_rejects_empty_string() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        SupplyReason("")


@pytest.mark.unit
def test_supply_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        SupplyReason("   ")


@pytest.mark.unit
def test_supply_reason_rejects_too_long() -> None:
    with pytest.raises(InvalidSupplyReasonError):
        SupplyReason("a" * 501)


@pytest.mark.unit
def test_supply_reason_accepts_max_length() -> None:
    reason = SupplyReason("a" * 500)
    assert len(reason.value) == 500


# ---------- Supply aggregate dataclass ----------


@pytest.mark.unit
def test_supply_aggregate_is_frozen() -> None:
    """Supply is a `@dataclass(frozen=True)`; attribute assignment must raise.
    Locks the slim-aggregate immutability used by the additive-state
    pattern (future watch-item facets land as new fields with defaults)."""
    supply = Supply(
        id=uuid4(),
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
        status=SupplyStatus.UNKNOWN,
    )
    with pytest.raises(AttributeError):
        supply.status = SupplyStatus.AVAILABLE  # type: ignore[misc]


@pytest.mark.unit
def test_supply_status_defaults_to_unknown_at_construction() -> None:
    """The dataclass default mirrors the genesis-evolver-sets-Unknown convention."""
    supply = Supply(
        id=uuid4(),
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
    )
    assert supply.status == SupplyStatus.UNKNOWN


# ---------- Length-constant locks ----------


@pytest.mark.unit
def test_max_length_constants_are_pinned() -> None:
    """Public exports; silent shrinkage would be invisible to consumers."""
    assert SUPPLY_KIND_MAX_LENGTH == 50
    assert SUPPLY_NAME_MAX_LENGTH == 200
    assert REASON_MAX_LENGTH == 500


# ---------- SupplyStatus enum (5 health states + Decommissioned terminal) ----------


@pytest.mark.unit
def test_supply_status_has_six_locked_values() -> None:
    assert {s.value for s in SupplyStatus} == {
        "Unknown",
        "Available",
        "Degraded",
        "Unavailable",
        "Recovering",
        "Decommissioned",
    }


@pytest.mark.unit
def test_supply_status_unknown_is_initial() -> None:
    assert SupplyStatus.UNKNOWN.value == "Unknown"


# ---------- TriggerSource enum (3-value lock day one for forward-compat) ----------


@pytest.mark.unit
def test_trigger_source_has_three_locked_values() -> None:
    assert {t.value for t in TriggerSource} == {"Operator", "Monitor", "Auto"}


@pytest.mark.unit
def test_trigger_source_enum_values_round_trip_verbatim() -> None:
    """All three TriggerSource enum values are currently in use; Monitor + Auto
    are reserved for future slice families per project_supply_design."""
    assert TriggerSource.OPERATOR.value == "Operator"
    assert TriggerSource.MONITOR.value == "Monitor"
    assert TriggerSource.AUTO.value == "Auto"
