"""Property-based tests for `version_practice.decide` (Recipe BC).

Complements the example-based `test_version_practice_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source versioning transition

    (state, command, now) -> list[PracticeVersioned]

with source set `Defined | Versioned -> Versioned`; only Deprecated is
rejected.

Load-bearing properties:

  - state=None always raises `PracticeNotFoundError` carrying
    command.practice_id.
  - Any allowed source status (Defined, Versioned) with a valid version
    tag emits exactly one `PracticeVersioned` whose practice_id is
    `state.id`, whose version_tag is the threaded (trimmed) tag, and
    whose occurred_at is `now`.
  - Any disallowed source status raises `PracticeCannotVersionError`
    carrying the current status, so a future status value cannot
    silently fall through.
  - The emitted event's practice_id is `state.id`, never
    `command.practice_id`.
  - Pure: same (state, command, now) returns equal events.

The full gate matrix (empty / whitespace / too-long tags) is pinned by
the example test; this file does not duplicate it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeCannotVersionError,
    PracticeName,
    PracticeNotFoundError,
    PracticeStatus,
    PracticeVersioned,
)
from cora.recipe.features import version_practice
from cora.recipe.features.version_practice import VersionPractice
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_METHOD_ID = UUID(int=1)
_SITE_ID = UUID(int=2)
_VALID_VERSION_TAG = "v2"

_VERSIONABLE_SOURCES = (PracticeStatus.DEFINED, PracticeStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in PracticeStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _practice(*, practice_id: UUID, status: PracticeStatus) -> Practice:
    return Practice(
        id=practice_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=_METHOD_ID,
        site_id=_SITE_ID,
        status=status,
    )


@pytest.mark.unit
@given(practice_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    practice_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PracticeNotFoundError` carrying command.practice_id."""
    with pytest.raises(PracticeNotFoundError) as exc:
        version_practice.decide(
            state=None,
            command=VersionPractice(practice_id=practice_id, version_tag=_VALID_VERSION_TAG),
            now=now,
        )
    assert exc.value.practice_id == practice_id


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_allowed_source_emits_single_event(
    practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """Any allowed source emits one PracticeVersioned with threaded tag and now."""
    events = version_practice.decide(
        state=_practice(practice_id=practice_id, status=source),
        command=VersionPractice(practice_id=practice_id, version_tag=_VALID_VERSION_TAG),
        now=now,
    )
    assert events == [
        PracticeVersioned(
            practice_id=practice_id,
            version_tag=_VALID_VERSION_TAG,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """Any disallowed source raises, carrying the current status."""
    with pytest.raises(PracticeCannotVersionError) as exc:
        version_practice.decide(
            state=_practice(practice_id=practice_id, status=source),
            command=VersionPractice(practice_id=practice_id, version_tag=_VALID_VERSION_TAG),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's practice_id is state.id, not command.practice_id."""
    assume(state_id != command_id)
    events = version_practice.decide(
        state=_practice(practice_id=state_id, status=PracticeStatus.DEFINED),
        command=VersionPractice(practice_id=command_id, version_tag=_VALID_VERSION_TAG),
        now=now,
    )
    assert events[0].practice_id == state_id


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    tag=printable_ascii_text(max_size=50),
    now=aware_datetimes(),
)
def test_version_emits_event_with_trimmed_tag(
    practice_id: UUID,
    tag: str,
    now: datetime,
) -> None:
    """The emitted event threads the trimmed version tag from the command."""
    padded = f"  {tag}  "
    events = version_practice.decide(
        state=_practice(practice_id=practice_id, status=PracticeStatus.DEFINED),
        command=VersionPractice(practice_id=practice_id, version_tag=padded),
        now=now,
    )
    assert events[0].version_tag == tag


@pytest.mark.unit
@given(practice_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_same_output(practice_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _practice(practice_id=practice_id, status=PracticeStatus.DEFINED)
    command = VersionPractice(practice_id=practice_id, version_tag=_VALID_VERSION_TAG)
    first = version_practice.decide(state=state, command=command, now=now)
    second = version_practice.decide(state=state, command=command, now=now)
    assert first == second
