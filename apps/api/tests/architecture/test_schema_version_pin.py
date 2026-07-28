"""`EXPECTED_SCHEMA_VERSION` must name the newest migration.

The constant is hand-maintained because the runtime image ships no
migrations directory to derive it from. Hand-maintained means it drifts,
and drift here is silent in the worst direction: the pin lags, so a
database migrated past it reads as AHEAD and a correctly-deployed process
refuses to boot. The gate would then be a liability rather than a
protection, and the first person to find out would be whoever restarted
CORA after a routine migration.

This test moves that discovery to CI. Adding a migration and forgetting
the constant fails here, in the same commit, with the value to paste.
"""

from __future__ import annotations

from cora.infrastructure.schema_version import (
    EXPECTED_SCHEMA_VERSION,
    is_well_formed,
    parse_versions,
)
from tests.architecture.conftest import tracked_migration_files


def test_expected_schema_version_matches_newest_tracked_migration() -> None:
    versions = parse_versions(tracked_migration_files())
    assert versions, (
        "No .sql files tracked under infra/atlas/migrations; either the "
        "migrations directory moved or git ls-files lost them."
    )
    newest = versions[-1]
    assert newest == EXPECTED_SCHEMA_VERSION, (
        f"EXPECTED_SCHEMA_VERSION is {EXPECTED_SCHEMA_VERSION!r} but the "
        f"newest tracked migration is {newest!r}. A migration landed without "
        f"the pin moving with it. Set EXPECTED_SCHEMA_VERSION to {newest!r} "
        f"in cora/infrastructure/schema_version.py."
    )


def test_every_migration_version_is_fixed_width() -> None:
    """Ordering is a string compare, which fixed width is what makes correct.

    `compare_versions` decides behind-versus-ahead with `applied >
    expected`. That is only sound while every version has the same number
    of digits: a 13-digit version would sort above a 14-digit one and
    invert the verdict, telling an operator to run a different image when
    they needed to run migrations. Atlas's own format is
    `YYYYMMDDHHMMSS`, so this holds today and this test keeps it holding.
    """
    malformed = [v for v in parse_versions(tracked_migration_files()) if not is_well_formed(v)]
    assert not malformed, (
        f"Migration versions must be Atlas's 14-digit YYYYMMDDHHMMSS, but "
        f"these are not: {malformed}. Version ordering in "
        f"compare_versions is a string compare and silently inverts on "
        f"mixed widths."
    )
