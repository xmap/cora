"""Property-based tests for `deprecate_model.decide` (Equipment BC).

Mirrors the `version_model` decider-PBT pattern, adapted for the
multi-source `Defined | Versioned -> Deprecated` transition. Universal
claims across generated inputs:

  - state in {Defined, Versioned} + valid command emits exactly one
    ModelDeprecated carrying the trimmed reason and the injected
    `now` timestamp.
  - state=None always raises ModelNotFoundError, regardless of command.
  - state.status==Deprecated always raises ModelCannotDeprecateError.
  - Empty, whitespace-only, or over-long `reason` always raises
    InvalidModelDeprecationReasonError (via the ModelDeprecationReason VO).
  - Pure: same (state, command, now) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.model import (
    MODEL_DEPRECATION_REASON_MAX_LENGTH,
    InvalidModelDeprecationReasonError,
    Manufacturer,
    ManufacturerName,
    Model,
    ModelCannotDeprecateError,
    ModelDeprecated,
    ModelName,
    ModelNotFoundError,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import deprecate_model
from cora.equipment.features.deprecate_model import DeprecateModel
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


_REASON = printable_ascii_text(min_size=1, max_size=MODEL_DEPRECATION_REASON_MAX_LENGTH)

# Deprecatable source statuses: Defined (first revision) and Versioned
# (subsequent revisions). Deprecated is excluded; it's covered by a
# dedicated rejection property.
_DEPRECATABLE_STATUS = st.sampled_from([ModelStatus.DEFINED, ModelStatus.VERSIONED])

# Negative-case alphabet for the bounded-text reason VO.
_WHITESPACE_CHARS = st.sampled_from([" ", "\t", "\n", "\r", "  ", " \t\n"])


def _invalid_reason() -> st.SearchStrategy[str]:
    """Empty, whitespace-only, or over-length strings for VO rejection PBTs."""
    return st.one_of(
        st.just(""),
        _WHITESPACE_CHARS,
        printable_ascii_text(
            min_size=MODEL_DEPRECATION_REASON_MAX_LENGTH + 1,
            max_size=MODEL_DEPRECATION_REASON_MAX_LENGTH + 50,
        ),
    )


def _model(model_id: UUID, *, status: ModelStatus) -> Model:
    return Model(
        id=model_id,
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_families=frozenset({model_id}),
        status=status,
        version="v0" if status is ModelStatus.VERSIONED else None,
    )


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_DEPRECATABLE_STATUS,
    reason=_REASON,
    now=aware_datetimes(),
)
def test_deprecate_model_emits_exactly_one_event_with_injected_fields(
    model_id: UUID,
    status: ModelStatus,
    reason: str,
    now: datetime,
) -> None:
    """Deprecatable source + valid command -> single ModelDeprecated with
    the trimmed reason and injected `now`."""
    state = _model(model_id, status=status)
    command = DeprecateModel(model_id=model_id, reason=reason)
    events = deprecate_model.decide(state=state, command=command, now=now)
    assert events == [
        ModelDeprecated(
            model_id=model_id,
            reason=reason,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_deprecate_model_on_empty_state_always_raises_not_found(
    model_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """state=None -> ModelNotFoundError carrying command.model_id."""
    command = DeprecateModel(model_id=model_id, reason=reason)
    with pytest.raises(ModelNotFoundError) as exc:
        deprecate_model.decide(state=None, command=command, now=now)
    assert exc.value.model_id == model_id


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_deprecate_model_on_deprecated_state_always_raises_cannot_deprecate(
    model_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """state.status==Deprecated -> ModelCannotDeprecateError."""
    state = _model(model_id, status=ModelStatus.DEPRECATED)
    command = DeprecateModel(model_id=model_id, reason=reason)
    with pytest.raises(ModelCannotDeprecateError) as exc:
        deprecate_model.decide(state=state, command=command, now=now)
    assert exc.value.model_id == model_id
    assert exc.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_DEPRECATABLE_STATUS,
    reason=_invalid_reason(),
    now=aware_datetimes(),
)
def test_deprecate_model_with_invalid_reason_always_raises(
    model_id: UUID,
    status: ModelStatus,
    reason: str,
    now: datetime,
) -> None:
    """Empty, whitespace-only, or over-long reason -> InvalidModelDeprecationReasonError."""
    state = _model(model_id, status=status)
    command = DeprecateModel(model_id=model_id, reason=reason)
    with pytest.raises(InvalidModelDeprecationReasonError):
        deprecate_model.decide(state=state, command=command, now=now)


@pytest.mark.unit
@given(
    model_id=st.uuids(),
    status=_DEPRECATABLE_STATUS,
    reason=_REASON,
    now=aware_datetimes(),
)
def test_deprecate_model_is_pure_same_input_same_output(
    model_id: UUID,
    status: ModelStatus,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return identical events."""
    state = _model(model_id, status=status)
    command = DeprecateModel(model_id=model_id, reason=reason)
    first = deprecate_model.decide(state=state, command=command, now=now)
    second = deprecate_model.decide(state=state, command=command, now=now)
    assert first == second
