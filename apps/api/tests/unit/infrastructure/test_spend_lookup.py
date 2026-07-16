"""Unit tests for the SpendLookup port shapes and the test-default stub."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.spend_lookup import (
    AlwaysZeroSpendLookup,
    SpendLookupResult,
)

_WINDOW_START = datetime(2026, 7, 1, tzinfo=UTC)
_WINDOW_END = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.mark.unit
async def test_always_zero_stub_returns_zero_spend_echoing_the_window() -> None:
    """The kernel-default stub answers 'nothing spent' for any agent,
    echoing the requested window so gate log lines stay self-describing."""
    agent_id = uuid4()

    result = await AlwaysZeroSpendLookup().find_agent_spend(
        agent_id=agent_id,
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
    )

    assert result == SpendLookupResult(
        agent_id=agent_id,
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
        usd_spent=0.0,
        tokens_spent=0,
        call_count=0,
    )


@pytest.mark.unit
def test_spend_lookup_result_is_frozen() -> None:
    """A gate must never mutate the snapshot it decides on."""
    result = SpendLookupResult(
        agent_id=uuid4(),
        window_start=_WINDOW_START,
        window_end=_WINDOW_END,
        usd_spent=1.25,
        tokens_spent=42,
        call_count=3,
    )
    with pytest.raises(FrozenInstanceError):
        result.usd_spent = 99.0  # type: ignore[misc]
