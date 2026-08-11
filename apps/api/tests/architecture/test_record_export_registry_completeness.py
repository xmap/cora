"""Every `*LogbookOpened` class is named by the entries-tier registry.

`cora.infrastructure.record_export._registry` resolves a logbook
envelope's `kind` to the `entries_*` table it opened. Per
`project_record_is_two_tier.md`, the envelope never names its own table,
so the registry is the one place that link is written down, and a new
`*LogbookOpened` class that forgets to register itself would silently
narrow envelope-driven traversal the same way the eighth entries table
(`entries_enclosure_permit_probes`) silently narrowed it before this
registry existed.

This fitness function AST-discovers every `*LogbookOpened` class under
`src/cora` (git-tracked, so pre-commit's tracked-file staging sees the
same set) and pins it against `registered_envelope_classes()`, both
directions: a new envelope class with no registry entry, and a registry
entry naming a class that no longer exists (e.g. after a rename), both
fail loudly instead of rotting quietly.
"""

import ast
from pathlib import Path

import pytest

from cora.infrastructure.record_export import registered_envelope_classes
from tests.architecture.conftest import tracked_python_files


def _find_logbook_opened_classes(tree: ast.Module) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name.endswith("LogbookOpened")
    ]


def _discover_logbook_opened_classes() -> dict[str, Path]:
    """Map every discovered `*LogbookOpened` class name to its defining file."""
    found: dict[str, Path] = {}
    for path in tracked_python_files():
        if path.name != "events.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for class_name in _find_logbook_opened_classes(tree):
            found[class_name] = path
    return found


@pytest.mark.architecture
def test_every_logbook_opened_class_is_in_the_registry() -> None:
    discovered = _discover_logbook_opened_classes()
    registered = registered_envelope_classes()

    unregistered = set(discovered) - registered
    assert not unregistered, (
        f"{sorted(unregistered)} define a *LogbookOpened envelope with no "
        "entry in cora.infrastructure.record_export._registry. Envelope-"
        "driven traversal silently stops covering the new table until "
        "one is added. Files: "
        f"{ {name: str(discovered[name]) for name in sorted(unregistered)} }"
    )


@pytest.mark.architecture
def test_no_registry_entry_names_a_class_that_no_longer_exists() -> None:
    discovered = _discover_logbook_opened_classes()
    registered = registered_envelope_classes()

    stale = registered - set(discovered)
    assert not stale, (
        f"{sorted(stale)} are named by the registry's envelope_class field "
        "but no *LogbookOpened class by that name exists under src/cora "
        "anymore (renamed?). Update _registry.py's envelope_class."
    )


@pytest.mark.architecture
def test_exactly_six_logbook_opened_classes_exist() -> None:
    """Pins the count so a seventh envelope class is a deliberate, reviewed
    registry addition rather than a silent drift. Bump alongside a new
    _registry.py entry, never on its own."""
    assert len(_discover_logbook_opened_classes()) == 6
