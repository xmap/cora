"""Every `entries_*` table a migration creates is known to record export's
entries-tier registry, and vice versa.

Sibling of `test_record_export_registry_completeness.py`, which
cross-checks `cora.infrastructure.record_export._registry` against
`*LogbookOpened` EVENT CLASSES (AST-discovered under `src/cora`). That
check has nothing to say about a table that ships with no envelope at
all -- `entries_run_feed_heartbeats` and `entries_enclosure_permit_probes`
are declared in the registry by hand for exactly that reason
(`_registry.py`'s module docstring). Nothing today cross-checks the
registry against the OTHER source of truth, migration SQL: a migration
can add an `entries_*` table with no registry entry and nothing fails.
That gap is real -- an envelope-less table has already shipped twice
before `_registry.py`'s explicit declarations closed it -- and this
file is slice 6 of project_record_publishing_campaign.md's fix.

Reuses `tests.architecture.conftest.append_only_table_lineage`'s
rename-following migration scan (moved there from
`test_entries_table_grants.py` for this reuse) rather than writing a
second SQL parser.
"""

import pytest

from cora.infrastructure.record_export import all_specs
from tests.architecture.conftest import append_only_table_lineage


@pytest.mark.architecture
def test_every_migration_created_entries_table_is_in_the_record_export_registry() -> None:
    discovered = {name for name in append_only_table_lineage() if name != "events"}
    registered = {spec.table for spec in all_specs()}

    unregistered = discovered - registered
    assert not unregistered, (
        f"{sorted(unregistered)} are created by a migration but have no "
        "cora.infrastructure.record_export._registry entry. An envelope-"
        "less entries table silently narrows what the exporter can reach "
        "until it is declared (see _registry.py's module docstring for "
        "the heartbeat/probe precedent) -- add an EntriesTableSpec, with "
        "envelope_class=None if the table genuinely has no *LogbookOpened "
        "envelope, or the real envelope class name otherwise."
    )


@pytest.mark.architecture
def test_no_record_export_registry_entry_names_a_table_no_migration_created() -> None:
    discovered = {name for name in append_only_table_lineage() if name != "events"}
    registered = {spec.table for spec in all_specs()}

    stale = registered - discovered
    assert not stale, (
        f"{sorted(stale)} are named by a record_export EntriesTableSpec.table "
        "but no migration creates (or renames a table to) that name. "
        "Renamed in a migration without updating _registry.py?"
    )
