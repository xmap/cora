"""Every name an event is STORED under has a disposition.

The redaction table is keyed on `events.event_type`, and the generator
builds it by asking each module's own `event_type_name` what that string
is. This test asks the same question by a deliberately DIFFERENT route:
it reads the string literals those functions return, straight from the
source, without importing anything and without running the generator.

The independence is the whole value. The pre-existing drift test
compares the generator against its own committed output, so a generator
that derives the wrong key produces a table that is wrong and a drift
test that is green, which is exactly what happened: the table was keyed
on class names, `ActorRegistered` writes `"ActorRegisteredV2"`, and the
mismatch was invisible until a real export refused a real record. Every
database holds an Actor registration from bootstrap, so the redacted
export path was unreachable for every real record while CI stayed green.

A static reader cannot be fooled by the same mistake as a runtime one.
If these two ever disagree, one of them is wrong and this fails.

Scope: only literal returns. `return type(event).__name__` names the
class and the generator covers it by construction; a literal is the
case where a stored name and a class name part company, and it is the
case nothing else checks.

Like the drift test beside it, this reads source files rather than
importing them, so pytest-tach's impact analysis cannot see that every
`events.py` is a dependency and `pytest --tach` would skip it after an
event-only change. CI runs without that flag.
"""

import ast
from pathlib import Path

import pytest

from cora.infrastructure.record_export._dispositions import DISPOSITIONS

from .conftest import tracked_python_files

pytestmark = pytest.mark.architecture


def _event_type_name_literals(path: Path) -> frozenset[str]:
    """String literals returned by `event_type_name` in one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    literals: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "event_type_name":
            continue
        for statement in ast.walk(node):
            if not isinstance(statement, ast.Return):
                continue
            value = statement.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                literals.add(value.value)
    return frozenset(literals)


def _stored_names_by_module() -> dict[Path, frozenset[str]]:
    found: dict[Path, frozenset[str]] = {}
    for path in sorted(tracked_python_files()):
        if path.name != "events.py":
            continue
        literals = _event_type_name_literals(path)
        if literals:
            found[path] = literals
    return found


def test_every_literal_stored_event_name_has_a_disposition() -> None:
    missing: list[str] = []
    for path, literals in _stored_names_by_module().items():
        for name in sorted(literals):
            if name not in DISPOSITIONS:
                missing.append(f"{name} (returned by {path.name} in {path.parent.name})")

    assert not missing, (
        "These strings are written into events.event_type but have no entry in "
        "DISPOSITIONS, so redaction refuses any record containing one and no "
        "published export of such a record is possible:\n  "
        + "\n  ".join(missing)
        + "\nRegenerate with `make record-dispositions` and review the diff."
    )


def test_the_literal_scan_finds_the_known_renamed_event() -> None:
    """A canary on the scanner itself.

    A test that silently found nothing would pass forever. `ActorRegistered`
    is the one event in the tree whose stored name differs from its class
    name, so the scan must see it. If this fails because the rename was
    retired, delete this test rather than weakening the one above.
    """
    all_literals: set[str] = set()
    for literals in _stored_names_by_module().values():
        all_literals |= literals

    assert "ActorRegisteredV2" in all_literals
