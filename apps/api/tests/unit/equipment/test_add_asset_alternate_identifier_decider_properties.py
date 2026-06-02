"""Property-based tests for `add_asset_alternate_identifier.decide`.

Complements the example-based decider tests with universal claims
across generated inputs. The decider's pure shape

    (state, command, now) -> list[AssetAlternateIdentifierAdded]

makes a handful of strict-not-idempotent properties mechanical to
express. Mirror of `test_remove_asset_alternate_identifier_decider_properties.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
    AlternateIdentifier,
    AlternateIdentifierKind,
    Asset,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierAlreadyPresentError,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
)
from cora.equipment.features import add_asset_alternate_identifier
from cora.equipment.features.add_asset_alternate_identifier import (
    AddAssetAlternateIdentifier,
)

if TYPE_CHECKING:
    from uuid import UUID

_ANY_LIFECYCLE = st.sampled_from(list(AssetLifecycle))
_KIND = st.sampled_from(list(AlternateIdentifierKind))
_VALID_VALUE = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ALTERNATE_IDENTIFIER_VALUE_MAX_LENGTH,
)
_DT_BASE = datetime(2026, 6, 2, 0, 0, 0, tzinfo=UTC)


@st.composite
def _identifier(draw: st.DrawFn) -> AlternateIdentifier:
    return AlternateIdentifier(kind=draw(_KIND), value=draw(_VALID_VALUE))


def _asset(
    asset_id: UUID,
    *,
    lifecycle: AssetLifecycle,
    alternate_identifiers: frozenset[AlternateIdentifier],
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Detector-X"),
        level=AssetLevel.DEVICE,
        parent_id=asset_id,  # any UUID; non-Enterprise requires non-null
        lifecycle=lifecycle,
        alternate_identifiers=alternate_identifiers,
    )


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    identifier=_identifier(),
    lifecycle=_ANY_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_adding_absent_identifier_emits_one_event_with_injected_fields(
    asset_id: UUID,
    identifier: AlternateIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Identifier absent from any non-Decommissioned (and Decommissioned
    too: no lifecycle guard) state -> single Added event carrying the
    injected timestamp and identifier."""
    state = _asset(asset_id, lifecycle=lifecycle, alternate_identifiers=frozenset())
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    events = add_asset_alternate_identifier.decide(
        state=state,
        command=AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
        now=now,
    )
    assert events == [
        AssetAlternateIdentifierAdded(
            asset_id=asset_id,
            alternate_identifier=identifier,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    identifier=_identifier(),
    lifecycle=_ANY_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_adding_present_identifier_always_raises_already_present(
    asset_id: UUID,
    identifier: AlternateIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Strict-not-idempotent: pair already in state -> AlreadyPresent
    regardless of lifecycle or timestamp."""
    state = _asset(
        asset_id,
        lifecycle=lifecycle,
        alternate_identifiers=frozenset({identifier}),
    )
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    with pytest.raises(AssetAlternateIdentifierAlreadyPresentError) as exc:
        add_asset_alternate_identifier.decide(
            state=state,
            command=AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
            now=now,
        )
    assert exc.value.asset_id == asset_id
    assert exc.value.identifier == identifier


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    identifier=_identifier(),
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_state_none_always_raises_asset_not_found(
    asset_id: UUID,
    identifier: AlternateIdentifier,
    seconds_offset: int,
) -> None:
    """state=None -> AssetNotFoundError regardless of identifier or now."""
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    with pytest.raises(AssetNotFoundError) as exc:
        add_asset_alternate_identifier.decide(
            state=None,
            command=AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
            now=now,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.unit
@given(
    asset_id=st.uuids(),
    identifier=_identifier(),
    other=_identifier(),
    lifecycle=_ANY_LIFECYCLE,
    seconds_offset=st.integers(min_value=0, max_value=10_000_000),
)
def test_decide_is_pure_same_input_same_output(
    asset_id: UUID,
    identifier: AlternateIdentifier,
    other: AlternateIdentifier,
    lifecycle: AssetLifecycle,
    seconds_offset: int,
) -> None:
    """Two calls with identical (state, command, now) return identical
    events; no hidden clock or id leakage."""
    assume(identifier != other)
    state = _asset(
        asset_id,
        lifecycle=lifecycle,
        alternate_identifiers=frozenset({other}),
    )
    now = _DT_BASE + timedelta(seconds=seconds_offset)
    command = AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier)
    first = add_asset_alternate_identifier.decide(state=state, command=command, now=now)
    second = add_asset_alternate_identifier.decide(state=state, command=command, now=now)
    assert first == second
