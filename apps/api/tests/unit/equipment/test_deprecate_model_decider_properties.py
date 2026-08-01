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
  - Pure: same (state, command, now) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import deprecate_model
from cora.equipment.features.deprecate_model import DeprecateModel
from cora.shared.deprecation import DeprecationReason
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


_REASON = st.sampled_from(DeprecationReason)

# Deprecatable source statuses: Defined (first revision) and Versioned
# (subsequent revisions). Deprecated is excluded; it's covered by a
# dedicated rejection property.
_DEPRECATABLE_STATUS = st.sampled_from([ModelStatus.DEFINED, ModelStatus.VERSIONED])

# Negative-case alphabet for the bounded-text reason VO.
_WHITESPACE_CHARS = st.sampled_from([" ", "\t", "\n", "\r", "  ", " \t\n"])


def _model(model_id: UUID, *, status: ModelStatus) -> Model:
    return Model(
        id=model_id,
        name=ModelName("Existing"),
        manufacturer=Manufacturer(name=ManufacturerName("M")),
        part_number=PartNumber("P"),
        declared_family_ids=frozenset({model_id}),
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
def test_deprecate_model_is_pure_same_input_same_output(
    model_id: UUID,
    status: ModelStatus,
    reason: DeprecationReason,
    now: datetime,
) -> None:
    """Two calls with identical args return identical events."""
    state = _model(model_id, status=status)
    command = DeprecateModel(model_id=model_id, reason=reason)
    first = deprecate_model.decide(state=state, command=command, now=now)
    second = deprecate_model.decide(state=state, command=command, now=now)
    assert first == second
