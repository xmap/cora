"""Every Equipment `<X>Cannot<Verb>Error` class has at least one producer.

Background: the alternate-identifier slice pair landed with a
state-tier `AssetCannotAddAlternateIdentifierError` class declared
for a lifecycle guard the deciders never raise. The route module
registered the class in its 409 mapping, the docstring described
the guard, and the design memo Lock E pinned it, but the actual
decider bodies were guard-free. A reader walking from the state
module to the routes module would conclude the guard ships; in
fact, a Decommissioned asset accepts add / remove unchecked. The
gate review caught the drift on close inspection of the decider
bodies; no fitness function would have surfaced it.

This module pins the rule that drift implies: every state-declared
class matching ``<X>Cannot<Verb>Error`` under any Equipment
aggregate's ``state.py`` MUST have AT LEAST ONE textual ``raise
<Class>(`` site somewhere in ``cora.equipment.features.*`` (slice
deciders, handlers, route handlers; tests excluded).

Scope: Equipment BC only. The same rule generalizes to every BC
that follows the per-transition error class taxonomy, but the
audit that motivated this fitness covered Equipment exclusively;
generalize when a second BC accrues a producer-less class.

Enumeration is git-aware via ``tracked_python_files()`` per the
worktree pre-commit-stash rationale in ``conftest.py``: half-
staged files must stay invisible to this scan, otherwise in-flight
slices would false-fail before the author wires up the raise site.

``GRANDFATHERED_PRODUCERLESS`` carries any class that ships
declared-but-not-raised on purpose. Each entry MUST cite the
finding it grandfathers and the design lock that justifies the
class staying alive. The set is currently empty: every Equipment
``<X>Cannot<Verb>Error`` class is raised by at least one slice
under ``cora.equipment.features.*``. Add a new entry only when a
design lock pins a class that ships ahead of its producer.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_EQUIPMENT_ROOT = CORA_ROOT / "equipment"
_AGGREGATES_ROOT = _EQUIPMENT_ROOT / "aggregates"
_FEATURES_ROOT = _EQUIPMENT_ROOT / "features"

# Aggregate directories whose ``state.py`` declares per-transition error
# classes that the slice deciders are expected to raise. Listed
# explicitly rather than auto-discovered so adding a new aggregate
# requires a deliberate edit to this fitness (forcing the question
# "does this aggregate also follow the producer convention?").
_AGGREGATES_WITH_TRANSITION_ERRORS: tuple[str, ...] = (
    "asset",
    "family",
    "frame",
    "model",
    "mount",
)

# Pattern matches the canonical state-transition error taxonomy
# (``<X>Cannot<Verb>Error``) declared at the docs/reference/patterns.md
# Rejections table. Kept loose on the leading noun (`[A-Z][A-Za-z]+`)
# so it matches Asset / Model / Family / Frame / Mount uniformly; the
# verb segment likewise stays loose so future verbs land without a
# regex update.
_CANNOT_ERROR_PATTERN = re.compile(r"^[A-Z][A-Za-z]+Cannot[A-Z][A-Za-z]+Error$")


# Entries are bare class names (each class is unique across the
# Equipment BC by construction; per-aggregate prefix disambiguates).
# Each entry MUST cite the gate-review finding it grandfathers and
# the design lock that justifies the class staying declared-but-
# unraised until the follow-up lands. Currently empty.
GRANDFATHERED_PRODUCERLESS: frozenset[str] = frozenset()


def _cannot_error_class_names(state_path: Path) -> frozenset[str]:
    """Top-level ``<X>Cannot<Verb>Error`` class defs in one ``state.py``."""
    tree = ast.parse(state_path.read_text())
    return frozenset(
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and _CANNOT_ERROR_PATTERN.match(node.name)
    )


def _declared_cannot_classes() -> frozenset[str]:
    """All ``<X>Cannot<Verb>Error`` classes declared across in-scope state.py files.

    Filtered through ``tracked_python_files()`` so half-staged
    additions stay invisible until ``git add``ed.
    """
    tracked = tracked_python_files()
    declared: set[str] = set()
    for aggregate in _AGGREGATES_WITH_TRANSITION_ERRORS:
        state_path = _AGGREGATES_ROOT / aggregate / "state.py"
        if state_path not in tracked:
            continue
        declared |= _cannot_error_class_names(state_path)
    return frozenset(declared)


def _feature_source_text() -> str:
    """Concatenated source of every tracked ``features/*`` Python file.

    A single concatenated blob keeps the per-class scan linear instead
    of N classes times M files. Tests under ``tests/`` are excluded by
    ``tracked_python_files()`` (which scopes to ``src/cora``).
    """
    tracked = tracked_python_files()
    sources: list[str] = []
    for path in sorted(tracked):
        try:
            path.relative_to(_FEATURES_ROOT)
        except ValueError:
            continue
        sources.append(path.read_text())
    return "\n".join(sources)


def _producer_sites(class_name: str, blob: str) -> bool:
    """Whether a textual ``raise <class_name>(`` site exists in the blob."""
    return f"raise {class_name}(" in blob


@pytest.mark.architecture
@pytest.mark.parametrize("class_name", sorted(_declared_cannot_classes()))
def test_cannot_error_has_at_least_one_producer(class_name: str) -> None:
    if class_name in GRANDFATHERED_PRODUCERLESS:
        pytest.skip(
            f"{class_name} is grandfathered as producer-less; "
            "see GRANDFATHERED_PRODUCERLESS for the finding cited"
        )
    blob = _feature_source_text()
    assert _producer_sites(class_name, blob), (
        f"{class_name} is declared in an Equipment aggregate's state.py "
        "but no slice under cora.equipment.features.* contains a "
        f"`raise {class_name}(` site.\n"
        "Either add the missing raise to the relevant decider, OR remove "
        "the class from state.py and the BC's error-to-status mapping.\n"
        "Consumer-without-producer drift surfaces in API contract docs "
        "(the routes module advertises a 409 the decider can never emit) "
        "and in the design memo (which describes a guard that never runs)."
    )


@pytest.mark.architecture
def test_grandfathered_producerless_entries_still_declared() -> None:
    """``GRANDFATHERED_PRODUCERLESS`` entries must still exist in state.py.

    Drift catcher: once Path A (or the equivalent follow-up) restores
    the producer, the per-class test above passes naturally and the
    grandfather entry becomes dead weight. Re-checking declaration
    forces the entry to be removed alongside the producer-restoration
    commit.
    """
    declared = _declared_cannot_classes()
    for entry in GRANDFATHERED_PRODUCERLESS:
        assert entry in declared, (
            f"GRANDFATHERED_PRODUCERLESS entry {entry!r}: class is no "
            "longer declared in any Equipment state.py; remove the "
            "entry (the follow-up that restored the producer shipped)."
        )


@pytest.mark.architecture
def test_grandfathered_producerless_entries_are_actually_producerless() -> None:
    """``GRANDFATHERED_PRODUCERLESS`` entries must STILL lack a producer.

    Drift catcher mirror of the prior test: once a producer lands, the
    grandfather entry no longer protects anything. Re-running the
    feature-source scan forces the entry to be removed in the same
    commit as the producer restoration.
    """
    blob = _feature_source_text()
    for entry in GRANDFATHERED_PRODUCERLESS:
        assert not _producer_sites(entry, blob), (
            f"GRANDFATHERED_PRODUCERLESS entry {entry!r}: producer now "
            "exists under cora.equipment.features.*; remove the entry "
            "from GRANDFATHERED_PRODUCERLESS in the same commit that "
            "added the raise site."
        )
