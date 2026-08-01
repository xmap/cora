"""Unit tests for the `deprecate_family` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Deprecated`. Same
source-set as version_family but the target is terminal.
Re-deprecating raises (strict-not-idempotent).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import (
    Family,
    FamilyCannotDeprecateError,
    FamilyDeprecated,
    FamilyName,
    FamilyNotFoundError,
    FamilyStatus,
)
from cora.equipment.features import deprecate_family
from cora.equipment.features.deprecate_family import DeprecateFamily
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _capability(
    *,
    status: FamilyStatus = FamilyStatus.DEFINED,
    version: str | None = None,
) -> Family:
    return Family(
        id=uuid4(),
        name=FamilyName("Tomography"),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [FamilyStatus.DEFINED, FamilyStatus.VERSIONED],
)
def test_decide_emits_capability_deprecated_for_each_allowed_source_status(
    source: FamilyStatus,
) -> None:
    state = _capability(status=source)
    events = deprecate_family.decide(
        state=state,
        command=DeprecateFamily(reason=DeprecationReason.SUPERSEDED, family_id=state.id),
        now=_NOW,
    )
    assert events == [FamilyDeprecated(reason="Superseded", family_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(FamilyNotFoundError) as exc_info:
        deprecate_family.decide(
            state=None,
            command=DeprecateFamily(reason=DeprecationReason.SUPERSEDED, family_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.family_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    state = _capability(status=FamilyStatus.DEPRECATED)
    with pytest.raises(FamilyCannotDeprecateError) as exc_info:
        deprecate_family.decide(
            state=state,
            command=DeprecateFamily(reason=DeprecationReason.SUPERSEDED, family_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.family_id == state.id
    assert exc_info.value.current_status is FamilyStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _capability(status=FamilyStatus.DEPRECATED)
    with pytest.raises(FamilyCannotDeprecateError) as exc_info:
        deprecate_family.decide(
            state=state,
            command=DeprecateFamily(reason=DeprecationReason.SUPERSEDED, family_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _capability()
    command = DeprecateFamily(reason=DeprecationReason.SUPERSEDED, family_id=state.id)
    first = deprecate_family.decide(state=state, command=command, now=_NOW)
    second = deprecate_family.decide(state=state, command=command, now=_NOW)
    assert first == second
