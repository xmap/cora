"""EnclosureName + EnclosureReason VOs + permit-status / lifecycle enums + Enclosure aggregate.

`InvalidEnclosureReasonError` empty / too-long paths exercised on the VO
here; transition-level reason validation (raised inside deciders via
`validate_bounded_text`) is pinned in the per-slice decider tests.
Cross-aggregate guards (`EnclosureAlreadyExistsError` /
`EnclosureNotFoundError` / `EnclosureCannot*Error`) are raised by
deciders / handlers and tested at those layers.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    ENCLOSURE_NAME_MAX_LENGTH,
    Enclosure,
    EnclosureLifecycle,
    EnclosureName,
    EnclosurePermitStatus,
    EnclosureReason,
    InvalidEnclosureNameError,
    InvalidEnclosureReasonError,
)
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_ENCLOSURE_ID = EnclosureId(UUID("01900000-0000-7000-8000-00000000e001"))
_CONTAINING_ASSET_ID = UUID("01900000-0000-7000-8000-00000000a501")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


# ---------- EnclosureName VO ----------


@pytest.mark.unit
def test_enclosure_name_accepts_normal_string() -> None:
    name = EnclosureName("2-BM Hutch A")
    assert name.value == "2-BM Hutch A"


@pytest.mark.unit
def test_enclosure_name_trims_whitespace() -> None:
    name = EnclosureName("  2-BM Hutch A  ")
    assert name.value == "2-BM Hutch A"


@pytest.mark.unit
def test_enclosure_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        EnclosureName("")


@pytest.mark.unit
def test_enclosure_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        EnclosureName("   \t\n   ")


@pytest.mark.unit
def test_enclosure_name_rejects_too_long() -> None:
    with pytest.raises(InvalidEnclosureNameError):
        EnclosureName("a" * 201)


@pytest.mark.unit
def test_enclosure_name_accepts_max_length() -> None:
    name = EnclosureName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_enclosure_name_is_frozen() -> None:
    name = EnclosureName("2-BM Hutch A")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]


# ---------- EnclosureReason VO ----------


@pytest.mark.unit
def test_enclosure_reason_accepts_normal_string() -> None:
    reason = EnclosureReason("PSS interlock cleared after walkdown")
    assert reason.value == "PSS interlock cleared after walkdown"


@pytest.mark.unit
def test_enclosure_reason_trims_whitespace() -> None:
    reason = EnclosureReason("  search-and-secure complete  ")
    assert reason.value == "search-and-secure complete"


@pytest.mark.unit
def test_enclosure_reason_rejects_empty_string() -> None:
    with pytest.raises(InvalidEnclosureReasonError):
        EnclosureReason("")


@pytest.mark.unit
def test_enclosure_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidEnclosureReasonError):
        EnclosureReason("   ")


@pytest.mark.unit
def test_enclosure_reason_rejects_too_long() -> None:
    with pytest.raises(InvalidEnclosureReasonError):
        EnclosureReason("a" * 501)


@pytest.mark.unit
def test_enclosure_reason_accepts_max_length() -> None:
    reason = EnclosureReason("a" * 500)
    assert len(reason.value) == 500


@pytest.mark.unit
def test_enclosure_reason_is_frozen() -> None:
    reason = EnclosureReason("PSS interlock cleared")
    with pytest.raises(AttributeError):
        reason.value = "Other"  # type: ignore[misc]


# ---------- Enclosure aggregate dataclass ----------


def _enclosure(
    *,
    permit_status: EnclosurePermitStatus = EnclosurePermitStatus.UNKNOWN,
    lifecycle: EnclosureLifecycle = EnclosureLifecycle.ACTIVE,
    decommissioned_at: datetime | None = None,
    decommissioned_by: ActorId | None = None,
) -> Enclosure:
    return Enclosure(
        id=_ENCLOSURE_ID,
        name=EnclosureName("2-BM Hutch A"),
        containing_asset_id=_CONTAINING_ASSET_ID,
        permit_status=permit_status,
        lifecycle=lifecycle,
        registered_at=_NOW,
        registered_by=_ACTOR_ID,
        decommissioned_at=decommissioned_at,
        decommissioned_by=decommissioned_by,
    )


@pytest.mark.unit
def test_enclosure_aggregate_is_frozen() -> None:
    """Enclosure is a `@dataclass(frozen=True)`; attribute assignment must raise.

    Locks the slim-aggregate immutability used by the additive-state
    pattern (future watch-item facets land as new fields with defaults).
    """
    enclosure = _enclosure()
    with pytest.raises(AttributeError):
        enclosure.permit_status = EnclosurePermitStatus.PERMITTED  # type: ignore[misc]


@pytest.mark.unit
def test_enclosure_terminal_attribution_pair_is_null_before_decommission() -> None:
    """Per fold-symmetry, `decommissioned_at` and `decommissioned_by` arrive together.

    Both remain None until the terminal `EnclosureDecommissioned` event
    folds them onto state in the same evolver arm.
    """
    enclosure = _enclosure()
    assert enclosure.decommissioned_at is None
    assert enclosure.decommissioned_by is None


@pytest.mark.unit
def test_enclosure_terminal_attribution_pair_populates_together() -> None:
    decommissioned_at = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
    enclosure = _enclosure(
        lifecycle=EnclosureLifecycle.DECOMMISSIONED,
        decommissioned_at=decommissioned_at,
        decommissioned_by=_ACTOR_ID,
    )
    assert enclosure.lifecycle is EnclosureLifecycle.DECOMMISSIONED
    assert enclosure.decommissioned_at == decommissioned_at
    assert enclosure.decommissioned_by == _ACTOR_ID


@pytest.mark.unit
def test_enclosure_containing_asset_id_is_bare_uuid() -> None:
    """Cross-BC pointer stays a bare UUID; no Enclosure-local NewType wraps it."""
    enclosure = _enclosure()
    assert isinstance(enclosure.containing_asset_id, UUID)
    assert enclosure.containing_asset_id == _CONTAINING_ASSET_ID


@pytest.mark.unit
def test_enclosure_id_is_a_newtype_over_uuid() -> None:
    """NewType wraps a UUID at type-check time; runtime identity stays UUID."""
    raw = uuid4()
    enclosure_id = EnclosureId(raw)
    assert isinstance(enclosure_id, UUID)
    assert enclosure_id == raw


@pytest.mark.unit
def test_enclosure_construction_with_genesis_defaults_lands_active_unknown() -> None:
    """Genesis evolver passes `UNKNOWN` + `ACTIVE` explicitly; this test
    pins the convention so a later default-shift on the enum source
    does not silently change registration semantics."""
    enclosure = _enclosure(
        permit_status=EnclosurePermitStatus.UNKNOWN,
        lifecycle=EnclosureLifecycle.ACTIVE,
    )
    assert enclosure.permit_status is EnclosurePermitStatus.UNKNOWN
    assert enclosure.lifecycle is EnclosureLifecycle.ACTIVE


# ---------- Length-constant locks ----------


@pytest.mark.unit
def test_max_length_constants_are_pinned() -> None:
    """Public exports; silent shrinkage would be invisible to consumers."""
    assert ENCLOSURE_NAME_MAX_LENGTH == 200
    assert REASON_MAX_LENGTH == 500


# ---------- EnclosurePermitStatus enum (observation axis only per D6.L2) ----------


@pytest.mark.unit
def test_enclosure_permit_status_has_three_locked_values() -> None:
    assert {s.value for s in EnclosurePermitStatus} == {
        "Permitted",
        "NotPermitted",
        "Unknown",
    }


@pytest.mark.unit
def test_enclosure_permit_status_unknown_is_initial() -> None:
    assert EnclosurePermitStatus.UNKNOWN.value == "Unknown"


@pytest.mark.unit
def test_enclosure_permit_status_values_are_pascal_case_strings() -> None:
    assert EnclosurePermitStatus.PERMITTED.value == "Permitted"
    assert EnclosurePermitStatus.NOT_PERMITTED.value == "NotPermitted"
    assert EnclosurePermitStatus.UNKNOWN.value == "Unknown"


# ---------- EnclosureLifecycle enum (Active -> Decommissioned terminal) ----------


@pytest.mark.unit
def test_enclosure_lifecycle_has_two_locked_values() -> None:
    assert {lc.value for lc in EnclosureLifecycle} == {"Active", "Decommissioned"}


@pytest.mark.unit
def test_enclosure_lifecycle_is_closed_at_two_arms() -> None:
    assert set(EnclosureLifecycle) == {
        EnclosureLifecycle.ACTIVE,
        EnclosureLifecycle.DECOMMISSIONED,
    }


@pytest.mark.unit
def test_enclosure_lifecycle_active_is_initial() -> None:
    assert EnclosureLifecycle.ACTIVE.value == "Active"


@pytest.mark.unit
def test_enclosure_dataclass_is_marked_frozen() -> None:
    """`__dataclass_params__.frozen` locks immutability at the decorator level.

    Catches a future-added mutable field that the existing single-field
    mutation test would miss (mutation tests only cover the fields they
    name).
    """
    assert Enclosure.__dataclass_params__.frozen is True  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
