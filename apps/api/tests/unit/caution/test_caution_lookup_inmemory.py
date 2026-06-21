"""Unit tests for `AlwaysQuietCautionLookup` (the test-default stub).

Mirrors `AlwaysCoveredClearanceLookup`'s unit-test shape: pins that
the stub returns `[]` regardless of inputs, so existing Run tests
that rely on `build_deps` / `build_postgres_deps` defaults don't
incidentally surface cautions.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.ports import AlwaysQuietCautionLookup


@pytest.mark.unit
async def test_always_quiet_returns_empty_list_for_empty_scope() -> None:
    lookup = AlwaysQuietCautionLookup()
    result = await lookup.find_active_in_scope(
        asset_ids=frozenset(),
        procedure_ids=frozenset(),
    )
    assert result == []


@pytest.mark.unit
async def test_always_quiet_returns_empty_list_with_asset_ids() -> None:
    lookup = AlwaysQuietCautionLookup()
    result = await lookup.find_active_in_scope(
        asset_ids=frozenset({uuid4(), uuid4()}),
        procedure_ids=frozenset(),
    )
    assert result == []


@pytest.mark.unit
async def test_always_quiet_returns_empty_list_with_procedure_ids() -> None:
    lookup = AlwaysQuietCautionLookup()
    result = await lookup.find_active_in_scope(
        asset_ids=frozenset(),
        procedure_ids=frozenset({uuid4()}),
    )
    assert result == []


@pytest.mark.unit
async def test_always_quiet_returns_empty_list_with_explicit_min_severity() -> None:
    """min_severity argument is accepted (port contract) but unused."""
    lookup = AlwaysQuietCautionLookup()
    result = await lookup.find_active_in_scope(
        asset_ids=frozenset({uuid4()}),
        procedure_ids=frozenset(),
        min_severity="Notice",
    )
    assert result == []


@pytest.mark.unit
async def test_always_quiet_find_retired_for_target_returns_empty_list() -> None:
    """The retirement-memory lookup stub is also silent (port contract)."""
    lookup = AlwaysQuietCautionLookup()
    result = await lookup.find_retired_for_target(
        target_kind="Asset",
        target_id=uuid4(),
        category="OperationalWindow",
        authored_by=uuid4(),
    )
    assert result == []
