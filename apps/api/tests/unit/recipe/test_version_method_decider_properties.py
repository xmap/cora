"""Property-based tests for `version_method.decide` (Recipe BC).

Complements the example-based `test_version_method_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[MethodVersioned]

Load-bearing properties:

  - state=None always raises `MethodNotFoundError` carrying command.method_id.
  - The source-state partition is total over `MethodStatus`: both
    `Defined` and `Versioned` emit exactly one `MethodVersioned`
    (method_id=state.id, version_tag threaded, occurred_at=now); every
    other status raises `MethodCannotVersionError` carrying the current
    status, so a future status value cannot silently fall through.
  - The emitted event's method_id is `state.id`, never `command.method_id`.
  - Pure: same (state, command, now) returns equal events.

The full gate matrix (trim, empty/whitespace/too-long version tag,
re-attestation, error-message contents) is pinned by the example test;
this file pins the universal shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotVersionError,
    MethodName,
    MethodNotFoundError,
    MethodStatus,
    MethodVersioned,
)
from cora.recipe.features import version_method
from cora.recipe.features.version_method import VersionMethod
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_VERSION_TAG = "v2"

_VERSIONABLE_SOURCES = (MethodStatus.DEFINED, MethodStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in MethodStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _method(
    *,
    method_id: UUID,
    status: MethodStatus,
    name: str = "XRF Mapping",
    version: str | None = None,
    parameters_schema: dict[str, Any] | None = None,
) -> Method:
    return Method(
        id=method_id,
        name=MethodName(name),
        needed_family_ids=frozenset(),
        status=status,
        version=version,
        parameters_schema=parameters_schema,
    )


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    method_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `MethodNotFoundError` carrying command.method_id."""
    with pytest.raises(MethodNotFoundError) as exc:
        version_method.decide(
            state=None,
            command=VersionMethod(method_id=method_id, version_tag=_VERSION_TAG),
            now=now,
        )
    assert exc.value.method_id == method_id


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    name=printable_ascii_text(max_size=50),
    now=aware_datetimes(),
)
def test_version_from_allowed_source_emits_single_event_with_threaded_tag(
    method_id: UUID,
    source: MethodStatus,
    name: str,
    now: datetime,
) -> None:
    """Both Defined and Versioned emit one event with state.id, tag, and now."""
    events = version_method.decide(
        state=_method(method_id=method_id, status=source, name=name),
        command=VersionMethod(method_id=method_id, version_tag=_VERSION_TAG),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, MethodVersioned)
    assert event.method_id == method_id
    assert event.version_tag == _VERSION_TAG
    assert event.occurred_at == now
    assert event.content_hash is not None


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    method_id: UUID,
    source: MethodStatus,
    now: datetime,
) -> None:
    """Any source other than Defined or Versioned raises, carrying the current status."""
    with pytest.raises(MethodCannotVersionError) as exc:
        version_method.decide(
            state=_method(method_id=method_id, status=source, version="v1"),
            command=VersionMethod(method_id=method_id, version_tag=_VERSION_TAG),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_method_id=st.uuids(), command_method_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_state_id_not_command_method_id(
    state_method_id: UUID,
    command_method_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's method_id is state.id, not command.method_id."""
    assume(state_method_id != command_method_id)
    events = version_method.decide(
        state=_method(method_id=state_method_id, status=MethodStatus.DEFINED),
        command=VersionMethod(method_id=command_method_id, version_tag=_VERSION_TAG),
        now=now,
    )
    assert events[0].method_id == state_method_id


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_returns_equal_output(
    method_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _method(method_id=method_id, status=MethodStatus.DEFINED)
    command = VersionMethod(method_id=method_id, version_tag=_VERSION_TAG)
    first = version_method.decide(state=state, command=command, now=now)
    second = version_method.decide(state=state, command=command, now=now)
    assert first == second
