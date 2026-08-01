"""Unit tests for the `deprecate_practice` slice's pure decider.

Mirror of `test_deprecate_method_decider.py`. Multi-source guard
`Defined | Versioned -> Deprecated`. Re-deprecating raises.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeCannotDeprecateError,
    PracticeDeprecated,
    PracticeName,
    PracticeNotFoundError,
    PracticeStatus,
)
from cora.recipe.features import deprecate_practice
from cora.recipe.features.deprecate_practice import DeprecatePractice
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _practice(
    *,
    status: PracticeStatus = PracticeStatus.DEFINED,
    version: str | None = None,
) -> Practice:
    return Practice(
        id=uuid4(),
        name=PracticeName("APS Standard Tomography"),
        method_id=uuid4(),
        site_id=uuid4(),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [PracticeStatus.DEFINED, PracticeStatus.VERSIONED],
)
def test_decide_emits_practice_deprecated_for_each_allowed_source_status(
    source: PracticeStatus,
) -> None:
    state = _practice(status=source)
    events = deprecate_practice.decide(
        state=state,
        command=DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=state.id),
        now=_NOW,
    )
    assert events == [
        PracticeDeprecated(reason="Superseded", practice_id=state.id, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_raises_practice_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(PracticeNotFoundError) as exc_info:
        deprecate_practice.decide(
            state=None,
            command=DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.practice_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    state = _practice(status=PracticeStatus.DEPRECATED)
    with pytest.raises(PracticeCannotDeprecateError) as exc_info:
        deprecate_practice.decide(
            state=state,
            command=DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.practice_id == state.id
    assert exc_info.value.current_status is PracticeStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _practice(status=PracticeStatus.DEPRECATED)
    with pytest.raises(PracticeCannotDeprecateError) as exc_info:
        deprecate_practice.decide(
            state=state,
            command=DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _practice()
    command = DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=state.id)
    first = deprecate_practice.decide(state=state, command=command, now=_NOW)
    second = deprecate_practice.decide(state=state, command=command, now=_NOW)
    assert first == second
