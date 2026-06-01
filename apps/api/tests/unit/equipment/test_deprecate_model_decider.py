"""Unit tests for the `deprecate_model` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Deprecated`. Same
source-set as version_model but the target is terminal.
Re-deprecating raises (strict-not-idempotent, mirrors deprecate_family).
The `reason` is validated defensively via `ModelDeprecationReason` so
direct decider callers get the same bounded-text protection as
API-boundary callers.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_REASON = "Vendor end-of-life 2026-Q3; replaced by ANT130-LZS"


def _model(
    *,
    status: ModelStatus = ModelStatus.DEFINED,
    version: str | None = None,
) -> Model:
    return Model(
        id=uuid4(),
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_families=frozenset({uuid4()}),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [ModelStatus.DEFINED, ModelStatus.VERSIONED],
)
def test_decide_emits_model_deprecated_for_each_allowed_source_status(
    source: ModelStatus,
) -> None:
    state = _model(status=source, version="v1" if source is ModelStatus.VERSIONED else None)
    events = deprecate_model.decide(
        state=state,
        command=DeprecateModel(model_id=state.id, reason=_REASON),
        now=_NOW,
    )
    assert events == [
        ModelDeprecated(model_id=state.id, reason=_REASON, occurred_at=_NOW),
    ]


@pytest.mark.unit
def test_decide_raises_model_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(ModelNotFoundError) as exc_info:
        deprecate_model.decide(
            state=None,
            command=DeprecateModel(model_id=target_id, reason=_REASON),
            now=_NOW,
        )
    assert exc_info.value.model_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    state = _model(status=ModelStatus.DEPRECATED, version="v1")
    with pytest.raises(ModelCannotDeprecateError) as exc_info:
        deprecate_model.decide(
            state=state,
            command=DeprecateModel(model_id=state.id, reason=_REASON),
            now=_NOW,
        )
    assert exc_info.value.model_id == state.id
    assert exc_info.value.current_status is ModelStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _model(status=ModelStatus.DEPRECATED, version="v1")
    with pytest.raises(ModelCannotDeprecateError) as exc_info:
        deprecate_model.decide(
            state=state,
            command=DeprecateModel(model_id=state.id, reason=_REASON),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_rejects_empty_reason() -> None:
    state = _model()
    with pytest.raises(InvalidModelDeprecationReasonError):
        deprecate_model.decide(
            state=state,
            command=DeprecateModel(model_id=state.id, reason=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    state = _model()
    with pytest.raises(InvalidModelDeprecationReasonError):
        deprecate_model.decide(
            state=state,
            command=DeprecateModel(model_id=state.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_over_long_reason() -> None:
    state = _model()
    too_long = "x" * (MODEL_DEPRECATION_REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidModelDeprecationReasonError):
        deprecate_model.decide(
            state=state,
            command=DeprecateModel(model_id=state.id, reason=too_long),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_trims_reason_before_embedding_in_event() -> None:
    """The VO trims surrounding whitespace; the emitted event carries
    the trimmed value, not the raw input."""
    state = _model()
    events = deprecate_model.decide(
        state=state,
        command=DeprecateModel(model_id=state.id, reason=f"  {_REASON}  "),
        now=_NOW,
    )
    assert events[0].reason == _REASON


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _model()
    command = DeprecateModel(model_id=state.id, reason=_REASON)
    first = deprecate_model.decide(state=state, command=command, now=_NOW)
    second = deprecate_model.decide(state=state, command=command, now=_NOW)
    assert first == second
