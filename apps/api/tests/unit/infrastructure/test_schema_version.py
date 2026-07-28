"""The boot-time schema check: every branch, without a database."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from cora.infrastructure.schema_version import (
    SchemaAbsentError,
    SchemaAheadError,
    SchemaBehindError,
    compare_versions,
    is_well_formed,
    parse_versions,
    read_applied_version,
    verify_schema_version,
)

_OLDER = "20260624000000"
_EXPECTED = "20260713000000"
_NEWER = "20260801000000"


class _FakePool:
    """Answers `fetchval` with a value or an exception. The check only
    ever issues one query, so this is the whole surface it touches."""

    def __init__(self, result: object) -> None:
        self._result = result

    async def fetchval(self, *_args: Any, **_kwargs: Any) -> Any:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _pool(result: object) -> Any:
    return _FakePool(result)


def test_compare_versions_matching_returns_without_raising() -> None:
    compare_versions(_EXPECTED, _EXPECTED)


def test_compare_versions_older_database_raises_behind() -> None:
    with pytest.raises(SchemaBehindError) as caught:
        compare_versions(_OLDER, _EXPECTED)
    assert caught.value.applied == _OLDER
    assert caught.value.expected == _EXPECTED


def test_compare_versions_newer_database_raises_ahead() -> None:
    with pytest.raises(SchemaAheadError) as caught:
        compare_versions(_NEWER, _EXPECTED)
    assert caught.value.applied == _NEWER


def test_compare_versions_no_applied_version_raises_absent() -> None:
    with pytest.raises(SchemaAbsentError):
        compare_versions(None, _EXPECTED)


def test_behind_message_directs_to_migrate_and_ahead_message_does_not() -> None:
    """The two directions must not give the same advice.

    Ahead cannot be fixed by migrating (forward-only leaves nothing to
    apply), so an ahead message that mentions `migrate-apply` would send
    an operator in a circle. This pins the asymmetry rather than the
    prose: the remedy is the part that must differ.
    """
    behind = str(SchemaBehindError(_OLDER, _EXPECTED))
    ahead = str(SchemaAheadError(_NEWER, _EXPECTED))
    assert "make migrate-apply" in behind
    assert "make migrate-apply" not in ahead
    assert "forward-only" in ahead


@pytest.mark.asyncio
async def test_read_applied_version_missing_table_reads_as_never_migrated() -> None:
    result = await read_applied_version(_pool(asyncpg.UndefinedTableError("no such table")))
    assert result is None


@pytest.mark.asyncio
async def test_read_applied_version_missing_schema_reads_as_never_migrated() -> None:
    result = await read_applied_version(_pool(asyncpg.InvalidSchemaNameError("no such schema")))
    assert result is None


@pytest.mark.asyncio
async def test_read_applied_version_empty_table_reads_as_never_migrated() -> None:
    """The query coalesces to '' rather than NULL, so the empty-table case
    arrives as a falsy string and must not be mistaken for a version."""
    assert await read_applied_version(_pool("")) is None


@pytest.mark.asyncio
async def test_read_applied_version_connection_failure_propagates() -> None:
    """A pool that cannot answer is not a fresh install.

    Swallowing this into None would report a connectivity outage as a
    never-migrated database, and send an operator to run migrations
    against something they cannot reach.
    """
    with pytest.raises(OSError):
        await read_applied_version(_pool(OSError("connection refused")))


@pytest.mark.asyncio
async def test_verify_matching_schema_reports_matched() -> None:
    check = await verify_schema_version(_pool(_EXPECTED), expected=_EXPECTED)
    assert check.posture == "matched"


@pytest.mark.asyncio
async def test_verify_mismatch_without_override_refuses() -> None:
    with pytest.raises(SchemaBehindError):
        await verify_schema_version(_pool(_OLDER), expected=_EXPECTED)


@pytest.mark.asyncio
async def test_verify_mismatch_with_override_reports_degraded_and_both_versions() -> None:
    check = await verify_schema_version(_pool(_OLDER), allow_mismatch=True, expected=_EXPECTED)
    assert check.posture == "degraded"
    assert check.applied == _OLDER
    assert check.expected == _EXPECTED


@pytest.mark.asyncio
async def test_verify_ahead_with_override_reports_degraded() -> None:
    check = await verify_schema_version(_pool(_NEWER), allow_mismatch=True, expected=_EXPECTED)
    assert check.posture == "degraded"


@pytest.mark.asyncio
async def test_verify_absent_schema_with_override_still_refuses() -> None:
    """The override buys reading a restored database, and an empty one has
    nothing to read. Letting it through would boot a process that reports
    an empty database as serviceable."""
    with pytest.raises(SchemaAbsentError):
        await verify_schema_version(_pool(None), allow_mismatch=True, expected=_EXPECTED)


def test_parse_versions_strips_description_and_sorts(tmp_path: Any) -> None:
    files = [
        tmp_path / "20260713000000_init_proj_budget.sql",
        tmp_path / "20260509120000_init_events.sql",
    ]
    assert parse_versions(files) == ("20260509120000", "20260713000000")


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("20260713000000", True),
        ("2026071300000", False),
        ("202607130000000", False),
        ("20260713_00000", False),
        ("", False),
    ],
)
def test_is_well_formed_accepts_only_fixed_width_timestamps(version: str, expected: bool) -> None:
    assert is_well_formed(version) is expected
