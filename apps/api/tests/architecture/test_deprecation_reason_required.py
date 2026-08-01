"""Pin: every `<X>Deprecated` event carries a required `reason: str`.

Deprecation is the one terminal whose reason changes how a reader must
treat data that ALREADY EXISTS. A Method retired because a better one
landed leaves every prior Run standing; a Method retired because it was
subtly wrong makes every prior Run suspect. The 2026-08-01 audit found
the corpus answering that question three different ways: seven templates
recorded nothing, three recorded operator prose, and one made the prose
optional.

All eleven now carry `reason: str`, validated at the command layer by
the closed `cora.shared.deprecation.DeprecationReason` enum. This
function keeps that closed, because the drift it prevents is not a
rename an author would notice. It is the next template shipping with a
`Deprecated` event and no reason at all, which is exactly how the first
seven got there.

## Why the event holds a primitive and the command holds the enum

The event field is `str`, not `DeprecationReason`. That mirrors
`CautionRetired`, the corpus's existing closed-reason precedent: the
enum lives on the command, Pydantic rejects an unknown value at the
edge with a 422 before any handler runs, and the decider passes
`command.reason.value` through so the stored payload stays JSON-plain.
Typing the event field would put an enum in the persistence envelope
for no gain and would break the `to_payload` primitive rule.

## Optional is not a middle ground here

`reason: str | None` is specifically disallowed, not merely
discouraged. `AgentDeprecated` shipped that way and it is the shape
this function exists to prevent returning: a reader asking "can I still
trust what this produced" cannot act on "the operator declined to say".
Where a cause genuinely may not exist, the right event is a different
one. `LanguageModelRetired` keeps an optional free-text reason for
exactly that case, because a vendor can withdraw a model without ever
issuing a statement, and it is not a `Deprecated` event.

## Scope

Every class in an `<Aggregate>Event` union whose name ends in
`Deprecated`. There are eleven today: the ten versionable templates
(agent, assembly, family, model, capability, method, plan, practice,
recipe, clearance_template) plus language_model, which the facility
deprecates without being able to version it.

No allowlist. A future `Deprecated` event that genuinely cannot name a
reason would be the first evidence that the closed vocabulary is wrong,
and that deserves a design conversation rather than a quiet exemption.
"""

import ast
from functools import cache
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_ENUM_MODULE = CORA_ROOT / "shared" / "deprecation.py"


def _flatten_union(node: ast.expr) -> list[str]:
    """Names in a PEP 604 pipe chain, in source order."""
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


@cache
def _deprecated_events() -> dict[str, tuple[str, str | None]]:
    """Map `<bc>/<aggregate>/<Class>` to (annotation, default-or-None)."""
    out: dict[str, tuple[str, str | None]] = {}
    for path in sorted(tracked_python_files()):
        if path.name != "events.py" or "aggregates" not in path.parts:
            continue
        parts = path.relative_to(CORA_ROOT).parts
        tree = ast.parse(path.read_text())
        union = _event_union(tree)
        if union is None:
            union = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        members = set(union)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name not in members:
                continue
            if not node.name.endswith("Deprecated"):
                continue
            annotation = "<missing>"
            default: str | None = None
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "reason"
                ):
                    annotation = ast.unparse(stmt.annotation)
                    default = ast.unparse(stmt.value) if stmt.value is not None else None
            out[f"{parts[0]}/{parts[2]}/{node.name}"] = (annotation, default)
    return out


@cache
def _deprecate_command_files() -> frozenset[str]:
    """Every `<bc>/features/deprecate_*/command.py` git is tracking."""
    return frozenset(
        str(path)
        for path in tracked_python_files()
        if path.name == "command.py" and path.parent.name.startswith("deprecate_")
    )


def _command_reason_annotation(path: Path) -> str:
    """The annotation on the command class's `reason` field, or a marker."""
    tree = ast.parse(path.read_text())
    expected = "".join(word.capitalize() for word in path.parent.name.split("_"))
    candidates = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    chosen = next((n for n in candidates if n.name == expected), None) or next(
        (n for n in candidates if n.name.startswith("Deprecate")), None
    )
    if chosen is None:
        return "<no command class>"
    for stmt in chosen.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "reason"
        ):
            return ast.unparse(stmt.annotation)
    return "<missing>"


@pytest.mark.architecture
def test_the_shared_deprecation_reason_enum_exists() -> None:
    assert _ENUM_MODULE in tracked_python_files(), (
        "cora/shared/deprecation.py is missing. It holds `DeprecationReason`, the "
        "closed vocabulary every `<X>Deprecated` command validates against. The "
        "per-event `reason: str` pins below are meaningless without it."
    )
    names = {
        node.name
        for node in ast.walk(ast.parse(Path(_ENUM_MODULE).read_text()))
        if isinstance(node, ast.ClassDef)
    }
    assert "DeprecationReason" in names, (
        f"cora/shared/deprecation.py declares {sorted(names)}, not `DeprecationReason`."
    )


@pytest.mark.architecture
def test_the_corpus_still_has_deprecated_events_to_pin() -> None:
    """Vacuity guard: an empty collection would make every pin below trivially pass.

    The parametrized tests collect zero cases if `_deprecated_events()` returns
    `{}` (a moved directory, a changed union shape, a broken walker), and pytest
    reports that as success. This is the one thing the pins cannot check about
    themselves.
    """
    found = _deprecated_events()
    assert len(found) >= 11, (
        f"Expected at least the 11 known `<X>Deprecated` events, found {len(found)}: "
        f"{sorted(found)}. Either the AST walker stopped matching, or events were "
        "removed. If a deprecation event was legitimately deleted, lower the floor "
        "here deliberately rather than letting the pins go quiet."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", sorted(_deprecate_command_files()))
def test_deprecate_command_annotates_the_closed_enum(path: str) -> None:
    """The event holds a primitive; the COMMAND is where the vocabulary is closed.

    Pinning only the event field leaves the real guarantee unguarded: a new
    `deprecate_*` slice could take a free-text `reason: str` on its command,
    emit it into a `reason: str` event, and pass every other check here.
    """
    annotation = _command_reason_annotation(Path(path))
    assert annotation == "DeprecationReason", (
        f"{path}: the command's `reason` is {annotation!r}, expected "
        "`DeprecationReason`. The event field is deliberately a primitive, so the "
        "command annotation is the only thing that closes the vocabulary and gives "
        "Pydantic something to reject an unknown value against at the edge."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_deprecated_events()))
def test_deprecated_event_carries_a_required_reason(key: str) -> None:
    annotation, default = _deprecated_events()[key]
    assert annotation == "str", (
        f"{key}: `reason` is {annotation!r}, expected `str`. Deprecation is the one "
        "terminal whose reason decides whether data produced under this template is "
        "still trustworthy, so every `<X>Deprecated` event must carry it. The event "
        "field holds the primitive; the command holds the closed "
        "`cora.shared.deprecation.DeprecationReason` enum, which is what rejects an "
        "unknown value at the edge. See `CautionRetired` for the same split."
    )
    assert default is None, (
        f"{key}: `reason` has default {default!r}, which makes it optional. That is "
        "the shape `AgentDeprecated` shipped with and this pin exists to prevent: a "
        "reader asking whether prior use of this template still stands cannot act on "
        "a missing answer. If a cause genuinely may not exist, the event is not a "
        "deprecation. See `LanguageModelRetired`, which keeps an optional free-text "
        "reason because a vendor can withdraw a model without issuing a statement."
    )
