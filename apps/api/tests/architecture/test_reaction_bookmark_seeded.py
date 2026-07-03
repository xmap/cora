"""Every Reaction class has a `projection_bookmarks` seed row in a migration.

Sibling to `test_projection_table_match` (which covers Projections via
their `proj_*` table migrations). Reactions have NO `proj_*` table, so a
Reaction's bookmark row is easy to forget: when the subscriber is
registered on the live worker, the advance loop calls
`read_bookmark(conn, subscriber.name)` and a missing row raises
`MissingBookmarkError` every tick, so the Reaction silently never fires.
This test catches that omission at PR time.

Discovery is static (no Kernel needed): scan every `cora/*/subscribers/`
module for classes carrying the Reaction shape (`name`,
`subscribed_event_types`, `batch_size`), read the class `name` attribute,
and assert it appears in an `INSERT INTO projection_bookmarks (name)
VALUES ('<name>')` in some migration.

## Known-unseeded pre-existing reactions

The three Agent-BC LLM reactions (`run_debriefer`, `caution_drafter`,
`caution_promoter`) predate this test and have NO bookmark-seed migration.
They have not bitten because they are LLM-gated (skipped without an API
key) and their tests drive `apply()` directly rather than the live
worker, but they WOULD wedge their advance loop if enabled on a live
worker. They are allowlisted here as documented latent debt so this test
does not redden the suite for a pre-existing gap; the allowlist is
append-only-shrinking and a NEW reaction cannot join it. Fixing those
three is an Agent-BC change, tracked separately.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_migration_files, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

_BOOKMARK_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+projection_bookmarks\s*\(name\)\s*VALUES\s*\(\s*'([a-zA-Z_][a-zA-Z0-9_]*)'",
    re.IGNORECASE,
)

# Pre-existing Agent-BC reactions with no bookmark-seed migration (see the
# module docstring). Append-only-shrinking: a NEW reaction must ship its
# seed migration, not join this list.
_ALLOWED_UNSEEDED_REACTIONS: frozenset[str] = frozenset(
    {"run_debriefer", "caution_drafter", "caution_promoter"}
)


def _seeded_bookmark_names() -> set[str]:
    out: set[str] = set()
    for path in tracked_migration_files():
        for match in _BOOKMARK_INSERT_RE.finditer(path.read_text()):
            out.add(match.group(1))
    return out


def _string_value(node: ast.expr | None) -> str | None:
    """Return the value of an `ast` node when it is a string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _reaction_names_in_module(path: Path) -> set[str]:
    """Names declared by Reaction-shaped classes in a subscriber module.

    A Reaction-shaped class assigns all three class attributes `name`,
    `subscribed_event_types`, and `batch_size`. `name` must be a string
    literal (it is, for every production subscriber). Purely static: no
    import, no Kernel.
    """
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        assigned: dict[str, ast.expr] = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        assigned[target.id] = stmt.value
        shape = {"name", "subscribed_event_types", "batch_size"}
        if shape <= assigned.keys():
            name_value = _string_value(assigned["name"])
            if name_value is not None:
                names.add(name_value)
    return names


def _all_reaction_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(tracked_python_files()):
        if path.parent.name != "subscribers":
            continue
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        # Only subscriber packages under a BC (cora/<bc>/subscribers/).
        if CORA_ROOT not in path.parents:
            continue
        names.update(_reaction_names_in_module(path))
    return names


@pytest.mark.architecture
def test_every_reaction_has_a_bookmark_seed() -> None:
    reactions = _all_reaction_names()
    if not reactions:
        pytest.skip("no Reaction-shaped subscriber classes found")
    seeded = _seeded_bookmark_names()
    missing = sorted(
        name for name in reactions if name not in seeded and name not in _ALLOWED_UNSEEDED_REACTIONS
    )
    assert not missing, (
        "Reactions missing a projection_bookmarks seed migration:\n"
        + "\n".join(f"  - {n}" for n in missing)
        + "\n\nEvery Reaction needs `INSERT INTO projection_bookmarks (name) "
        "VALUES ('<subscriber.name>') ON CONFLICT DO NOTHING` in a migration, "
        "or the worker's advance loop raises MissingBookmarkError every tick "
        "and the Reaction silently never fires."
    )


@pytest.mark.architecture
def test_unseeded_reaction_allowlist_stays_shrinking() -> None:
    """The allowlist must not name a reaction that no longer exists (drift)."""
    reactions = _all_reaction_names()
    stale = sorted(name for name in _ALLOWED_UNSEEDED_REACTIONS if name not in reactions)
    assert not stale, (
        "Allowlisted reactions no longer present (remove from "
        f"_ALLOWED_UNSEEDED_REACTIONS): {stale}"
    )
