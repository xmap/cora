"""Property-based tests for `approve_language_model.decide` (Agent BC).

Complements the example-based `test_approve_language_model_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[LanguageModelApproved]

Load-bearing properties:

  - state=None always raises `LanguageModelNotFoundError` carrying
    command.language_model_id.
  - The source-state partition is total over `LanguageModelStatus`:
    only `Defined` emits exactly one `LanguageModelApproved`
    (language_model_id=state.id, occurred_at=now); every other status
    raises `LanguageModelCannotApproveError` carrying the current
    status, so a future status value cannot silently fall through.
  - The emitted event's language_model_id is `state.id`, never
    `command.language_model_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    LanguageModel,
    LanguageModelApproved,
    LanguageModelCannotApproveError,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.approve_language_model.command import ApproveLanguageModel
from cora.agent.features.approve_language_model.decider import decide
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_APPROVABLE_SOURCES = (LanguageModelStatus.DEFINED,)
_DISALLOWED_SOURCES = tuple(
    s for s in LanguageModelStatus if s not in frozenset(_APPROVABLE_SOURCES)
)


def _language_model(*, language_model_id: UUID, status: LanguageModelStatus) -> LanguageModel:
    return LanguageModel(
        id=language_model_id,
        name=LanguageModelName("Claude Sonnet 4.6"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        served_via=ServingRoute.ARGO,
        cost_basis=TokenPricing(
            input_per_mtok=3.0,
            output_per_mtok=15.0,
            cache_write_per_mtok=3.75,
            cache_read_per_mtok=0.3,
        ),
        data_tier=DataSensitivityTier.INTERNAL,
        archivability=ArchivabilityTier.ALIAS,
        status=status,
    )


@pytest.mark.unit
@given(language_model_id=st.uuids(), now=aware_datetimes())
def test_approve_with_none_state_always_raises_not_found(
    language_model_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.language_model_id."""
    with pytest.raises(LanguageModelNotFoundError) as exc:
        decide(
            state=None,
            command=ApproveLanguageModel(language_model_id=language_model_id),
            now=now,
        )
    assert exc.value.language_model_id == language_model_id


@pytest.mark.unit
@given(language_model_id=st.uuids(), now=aware_datetimes())
def test_approve_from_defined_emits_single_event(
    language_model_id: UUID,
    now: datetime,
) -> None:
    """Defined is the only approvable source; emits one LanguageModelApproved."""
    events = decide(
        state=_language_model(
            language_model_id=language_model_id, status=LanguageModelStatus.DEFINED
        ),
        command=ApproveLanguageModel(language_model_id=language_model_id),
        now=now,
    )
    assert events == [LanguageModelApproved(language_model_id=language_model_id, occurred_at=now)]


@pytest.mark.unit
@given(
    language_model_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_approve_from_disallowed_source_always_raises_cannot_approve(
    language_model_id: UUID,
    source: LanguageModelStatus,
    now: datetime,
) -> None:
    """Any source other than Defined raises, carrying the current status."""
    with pytest.raises(LanguageModelCannotApproveError) as exc:
        decide(
            state=_language_model(language_model_id=language_model_id, status=source),
            command=ApproveLanguageModel(language_model_id=language_model_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_approve_uses_state_id_not_command_language_model_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's language_model_id is state.id, not command's."""
    assume(state_id != command_id)
    events = decide(
        state=_language_model(language_model_id=state_id, status=LanguageModelStatus.DEFINED),
        command=ApproveLanguageModel(language_model_id=command_id),
        now=now,
    )
    assert events[0].language_model_id == state_id


@pytest.mark.unit
@given(language_model_id=st.uuids(), now=aware_datetimes())
def test_approve_is_pure_same_input_same_output(language_model_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _language_model(language_model_id=language_model_id, status=LanguageModelStatus.DEFINED)
    command = ApproveLanguageModel(language_model_id=language_model_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
