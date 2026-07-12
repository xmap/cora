"""Property-based tests for `announce_language_model_retirement.decide` (Agent BC).

Complements the example-based
`test_announce_language_model_retirement_decider.py` with universal
claims across generated inputs. The decider is a pure single-source
FSM transition

    (state, command, now) -> list[LanguageModelRetirementAnnounced]

Load-bearing properties:

  - state=None always raises `LanguageModelNotFoundError` carrying
    command.language_model_id.
  - The source-state partition is total over `LanguageModelStatus`:
    only `Approved` emits exactly one `LanguageModelRetirementAnnounced`
    (language_model_id=state.id, occurred_at=now); every other status
    raises `LanguageModelCannotAnnounceRetirementError` carrying the
    current status, so a future status value cannot silently fall
    through.
  - A valid reason threads through trimmed; `effective_at` (None or
    set) passes through unchanged.
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
    LanguageModelCannotAnnounceRetirementError,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelRetirementAnnounced,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON_MAX = 500

_ANNOUNCEABLE_SOURCES = (LanguageModelStatus.APPROVED,)
_DISALLOWED_SOURCES = tuple(
    s for s in LanguageModelStatus if s not in frozenset(_ANNOUNCEABLE_SOURCES)
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
def test_announce_with_none_state_always_raises_not_found(
    language_model_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises not-found carrying command.language_model_id."""
    with pytest.raises(LanguageModelNotFoundError) as exc:
        decide(
            state=None,
            command=AnnounceLanguageModelRetirement(
                language_model_id=language_model_id, reason="x"
            ),
            now=now,
        )
    assert exc.value.language_model_id == language_model_id


@pytest.mark.unit
@given(language_model_id=st.uuids(), now=aware_datetimes())
def test_announce_from_approved_emits_single_event(
    language_model_id: UUID,
    now: datetime,
) -> None:
    """Approved is the only announceable source; emits one event."""
    events = decide(
        state=_language_model(
            language_model_id=language_model_id, status=LanguageModelStatus.APPROVED
        ),
        command=AnnounceLanguageModelRetirement(
            language_model_id=language_model_id, reason="vendor sunset"
        ),
        now=now,
    )
    assert events == [
        LanguageModelRetirementAnnounced(
            language_model_id=language_model_id,
            reason="vendor sunset",
            effective_at=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    language_model_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_announce_from_disallowed_source_always_raises_cannot_announce(
    language_model_id: UUID,
    source: LanguageModelStatus,
    now: datetime,
) -> None:
    """Any source other than Approved raises, carrying the current status."""
    with pytest.raises(LanguageModelCannotAnnounceRetirementError) as exc:
        decide(
            state=_language_model(language_model_id=language_model_id, status=source),
            command=AnnounceLanguageModelRetirement(
                language_model_id=language_model_id, reason="x"
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    language_model_id=st.uuids(),
    reason=printable_ascii_text(max_size=_REASON_MAX),
    now=aware_datetimes(),
)
def test_announce_threads_reason_through_trimmed(
    language_model_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """A valid reason threads through to the event after VO trimming."""
    events = decide(
        state=_language_model(
            language_model_id=language_model_id, status=LanguageModelStatus.APPROVED
        ),
        command=AnnounceLanguageModelRetirement(language_model_id=language_model_id, reason=reason),
        now=now,
    )
    assert events[0].reason == reason.strip()


@pytest.mark.unit
@given(
    language_model_id=st.uuids(),
    effective_at=st.one_of(st.none(), aware_datetimes()),
    now=aware_datetimes(),
)
def test_announce_threads_effective_at_through_unchanged(
    language_model_id: UUID,
    effective_at: datetime | None,
    now: datetime,
) -> None:
    """The vendor cutoff (None or set) passes through to the event as-is."""
    events = decide(
        state=_language_model(
            language_model_id=language_model_id, status=LanguageModelStatus.APPROVED
        ),
        command=AnnounceLanguageModelRetirement(
            language_model_id=language_model_id,
            reason="vendor sunset",
            effective_at=effective_at,
        ),
        now=now,
    )
    assert events[0].effective_at == effective_at


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_announce_uses_state_id_not_command_language_model_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's language_model_id is state.id, not command's."""
    assume(state_id != command_id)
    events = decide(
        state=_language_model(language_model_id=state_id, status=LanguageModelStatus.APPROVED),
        command=AnnounceLanguageModelRetirement(language_model_id=command_id, reason="x"),
        now=now,
    )
    assert events[0].language_model_id == state_id


@pytest.mark.unit
@given(language_model_id=st.uuids(), now=aware_datetimes())
def test_announce_is_pure_same_input_same_output(language_model_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _language_model(
        language_model_id=language_model_id, status=LanguageModelStatus.APPROVED
    )
    command = AnnounceLanguageModelRetirement(
        language_model_id=language_model_id, reason="vendor sunset"
    )
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
