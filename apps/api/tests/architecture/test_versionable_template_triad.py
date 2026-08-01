"""Pin: the `version` field and the `Versioned` event imply each other.

Ten aggregates are versionable templates. Every one of them carries a
`version` field on its aggregate root AND emits the full triad:

    <X>Defined  ->  <X>Versioned  ->  <X>Deprecated

agent, assembly, family, model, capability, method, plan, practice,
recipe, clearance_template. Ten out of ten, with no exceptions in
either direction. That is not a coincidence worth leaving unpinned:
the `version` field IS the machine-readable marker of the template
archetype, and it lets a fitness function tell templates from
everything else without a hand-maintained classification map.

## What this is NOT

`test_event_class_defined_vs_registered.py` pins that a genesis event
ends in `Defined` or `Registered`, and deliberately declines to check
WHICH, because that would need a per-aggregate semantic map. Its
docstring defers the direction-enforcing companion "until a rule-of-
three misclassification fires".

The 2026-08-01 audit checked. It has not fired. Eight aggregates emit
`Defined` without being versionable, and seven of the eight have a
solid reason:

  - `language_model` is a catalog entry for a vendor product. We
    cannot version it; the vendor does. It keeps `Deprecated` (the
    facility withdrew approval) and adds `Retired` (the vendor ended
    it), which is the one sanctioned deviation below.
  - `calibration` models versioning under a different name entirely:
    `CalibrationRevisionAppended` / `CalibrationRevisionPublished`.
  - `role` derives its id from `uuid5(name)`, so a rename mints a new
    identity and a version bump is structurally impossible.
  - `conduit`, `policy`, `surface`, `zone` are declared authorization
    artifacts with no version axis.

Only `permit` is arguable, and its own status enum opens at `Defined`,
so the aggregate is at least internally coherent. One arguable case is
not three. `Defined` therefore legitimately means "declared artifact",
of which "versionable template" is one kind, and this function pins
the kind rather than trying to narrow the word.

## The four pins

  1. `version` field on the aggregate root  <=>  `<X>Versioned` event.
     Both directions. A `version` field with no `Versioned` event is a
     field nothing can ever change; a `Versioned` event with no field
     is a bump the fold cannot record.
  2. Every `Versioned` aggregate's genesis ends in `Defined`. A
     versionable template is declared, never registered.
  3. Every `Versioned` aggregate also emits `Deprecated`. A template
     that can be revised needs a way to stop being recommended.
  4. `Deprecated` without `Versioned` is allowed only by allowlist,
     since it otherwise signals a template that lost its version axis.

Together these catch the drift a genesis-suffix check cannot see: a
new template whose genesis says `Registered`, a versionable aggregate
with no retirement path, or a `version` field added without the event
that moves it.
"""

import ast
from functools import cache
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_DEPRECATED_WITHOUT_VERSIONED: dict[str, str] = {
    "agent/language_model": (
        "a catalog entry for an external vendor product: the facility can withdraw "
        "approval (`LanguageModelDeprecated`) and the vendor can end service "
        "(`LanguageModelRetired`), but neither party versions the model through "
        "CORA, so there is no version axis to carry"
    ),
}


def _flatten_union(node: ast.expr) -> list[str]:
    """Names in a PEP 604 pipe chain, in source (left-associative) order."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union(node.left) + _flatten_union(node.right)
    if isinstance(node, ast.Name):
        return [node.id]
    return [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]


def _event_union(tree: ast.Module) -> list[str] | None:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
        if isinstance(target, ast.Name) and target.id.endswith("Event") and node.value:
            return _flatten_union(node.value)
    return None


def _root_class_has_version(state_path: Path, root_name: str) -> bool:
    """True when the aggregate root dataclass declares a `version` field."""
    if not state_path.exists():
        return False
    for node in ast.walk(ast.parse(state_path.read_text())):
        if isinstance(node, ast.ClassDef) and node.name == root_name:
            return any(
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == "version"
                for stmt in node.body
            )
    return False


@cache
def _aggregates() -> dict[str, dict[str, bool]]:
    """Map `<bc>/<aggregate>` to its template-archetype signals."""
    out: dict[str, dict[str, bool]] = {}
    for path in sorted(tracked_python_files()):
        if path.name != "events.py" or "aggregates" not in path.parts:
            continue
        parts = path.relative_to(CORA_ROOT).parts
        bc, aggregate = parts[0], parts[2]
        tree = ast.parse(path.read_text())
        union = _event_union(tree)
        if union is None:
            union = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        if not union:
            continue
        root_name = "".join(word.capitalize() for word in aggregate.split("_"))
        out[f"{bc}/{aggregate}"] = {
            "version_field": _root_class_has_version(path.parent / "state.py", root_name),
            "versioned": any(name.endswith("Versioned") for name in union),
            "deprecated": any(name.endswith("Deprecated") for name in union),
            "defined_genesis": union[0].endswith("Defined"),
        }
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_aggregates()))
def test_version_field_and_versioned_event_imply_each_other(key: str) -> None:
    signals = _aggregates()[key]
    assert signals["version_field"] == signals["versioned"], (
        f"{key}: `version` field on the aggregate root is "
        f"{signals['version_field']} but a `<X>Versioned` event is "
        f"{signals['versioned']}. These must agree. A `version` field with no "
        "event is a value nothing can ever change; a `Versioned` event with no "
        "field is a bump the fold cannot record. Add the missing half, or drop "
        "the other one."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(k for k, v in _aggregates().items() if v["versioned"]))
def test_versionable_template_is_defined_and_deprecatable(key: str) -> None:
    signals = _aggregates()[key]
    assert signals["defined_genesis"], (
        f"{key}: emits a `<X>Versioned` event, so it is a versionable template "
        "and its genesis event must end in `Defined`, not `Registered`. See "
        "test_event_class_defined_vs_registered.py for the genesis-suffix rule "
        "this narrows."
    )
    assert signals["deprecated"], (
        f"{key}: emits a `<X>Versioned` event but no `<X>Deprecated`. A template "
        "that can be revised needs a way to stop being recommended, or every "
        "past version stays live forever."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(
    "key", sorted(k for k, v in _aggregates().items() if v["deprecated"] and not v["versioned"])
)
def test_deprecatable_without_version_axis_is_allowlisted(key: str) -> None:
    assert key in _DEPRECATED_WITHOUT_VERSIONED, (
        f"{key}: emits `<X>Deprecated` without `<X>Versioned`. That usually means "
        "a versionable template lost its version axis. If the aggregate genuinely "
        "cannot be versioned through CORA, add it to "
        "`_DEPRECATED_WITHOUT_VERSIONED` in this file with the reason."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_DEPRECATED_WITHOUT_VERSIONED))
def test_allowlisted_aggregate_still_lacks_a_version_axis(key: str) -> None:
    """Allowlist entries must still deviate, so a later version axis prunes them."""
    aggregates = _aggregates()
    assert key in aggregates, (
        f"Allowlist entry {key!r} resolves to no tracked aggregate. It was removed "
        "or renamed; update or prune the entry in this file."
    )
    signals = aggregates[key]
    assert signals["deprecated"] and not signals["versioned"], (
        f"Allowlist entry {key!r} no longer deprecates-without-versioning "
        f"(deprecated={signals['deprecated']}, versioned={signals['versioned']}). "
        "Remove it from `_DEPRECATED_WITHOUT_VERSIONED` in this file."
    )
