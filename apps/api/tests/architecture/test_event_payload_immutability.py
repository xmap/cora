"""Event payload collection fields use immutable types.

Per the 2026-05-22 audit (D15) and the project convention exemplified
by ``Plan.wires`` (``frozenset[Wire]``) and Run's
``tuple[CautionAcknowledgement, ...]``: event payloads must declare
collection-typed fields with immutable types so that a payload dict
shared by reference into folded state can't be mutated post-fold.

This fitness function rejects:

  - ``list[X]``  →  use ``tuple[X, ...]``
  - ``set[X]``   →  use ``frozenset[X]``

``dict[X, Y]`` is deliberately NOT pinned: JSON-schema-shaped payloads
are intrinsically freeform dicts; pinning ``Mapping[X, Y]`` would
document intent without enforcing runtime immutability. The companion
defence for dict aliasing (B1 from the 2026-05-22 audit) is
shallow-copy on fold in the evolver.

The scan recurses through the whole annotation, so a ``list`` / ``set``
nested inside a ``dict`` value (``dict[UUID, list[str]]``) is rejected
on the same terms as a bare ``list[str]``. Folded state shares
references at every depth, so a nested mutable collection invites the
same alias bug as a top-level one. The lone historical case,
``asset_families_snapshot``, was migrated by hand in the 2026-05-22
audit and is now ``dict[UUID, tuple[UUID, ...]]``.

``MUTABLE_COLLECTION_EVENT_FIELDS`` is the explicit work-tracker for
known list/set fields awaiting migration. A migration replaces the
types with their immutable counterparts and removes the matching
allowlist entries.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Entries are <qualified-event-class>.<field-name>. Each removed
# when a migration replaces the type with tuple[...] / frozenset[...].
MUTABLE_COLLECTION_EVENT_FIELDS: frozenset[str] = frozenset()


def _event_files() -> list[Path]:
    """Tracked ``events.py`` files under ``<bc>/aggregates/<agg>/events.py``."""
    return sorted(
        f
        for f in tracked_python_files()
        if f.name == "events.py"
        and f.parent.parent.name == "aggregates"
        and f.parent.parent.parent.parent == CORA_ROOT
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _unwrap_optional(ann: ast.expr) -> ast.expr:
    """Return the inner type of ``X | None`` (matches CORA's annotation style)."""
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        # X | None  →  take the X side.
        if isinstance(ann.right, ast.Constant) and ann.right.value is None:
            return ann.left
        if isinstance(ann.left, ast.Constant) and ann.left.value is None:
            return ann.right
    return ann


def _mutable_collection_name(ann: ast.expr) -> str | None:
    """Return ``'list'`` / ``'set'`` if ``ann`` names one at any depth, else ``None``.

    The walk descends into subscript parameters, so ``dict[UUID, list[str]]``
    and ``tuple[set[int], ...]`` are caught as well as a bare ``list[str]``.
    ``frozenset`` and ``tuple`` are distinct names and never match.
    """
    for node in ast.walk(_unwrap_optional(ann)):
        if isinstance(node, ast.Name) and node.id in {"list", "set"}:
            return node.id
    return None


@pytest.mark.architecture
@pytest.mark.parametrize("events_file", _event_files(), ids=_qualified)
def test_event_payload_collection_fields_are_immutable(events_file: Path) -> None:
    qualified_module = _qualified(events_file)
    tree = ast.parse(events_file.read_text())
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            collection = _mutable_collection_name(stmt.annotation)
            if collection is None:
                continue
            key = f"{qualified_module}.{node.name}.{stmt.target.id}"
            if key in MUTABLE_COLLECTION_EVENT_FIELDS:
                continue
            replacement = "tuple[X, ...]" if collection == "list" else "frozenset[X]"
            violations.append(
                f"line {stmt.lineno}: {node.name}.{stmt.target.id} "
                f"is {ast.unparse(stmt.annotation)}; "
                f"{collection} is mutable, use {replacement}"
            )
    assert not violations, (
        f"{qualified_module} has mutable collection fields in event "
        f"payload(s):\n  " + "\n  ".join(violations) + "\n"
        "Event payloads share references into folded state; mutable "
        "collections invite alias bugs. Use tuple / frozenset."
    )


@pytest.mark.architecture
def test_allowlisted_event_fields_still_mutable() -> None:
    """``MUTABLE_COLLECTION_EVENT_FIELDS`` entries must still be mutable types.

    Drift catcher: once a field migrates to ``tuple[X, ...]`` /
    ``frozenset[X]``, its allowlist entry becomes dead weight. Re-running
    the mutable-type check here forces the entry to be removed alongside
    the fix. Entries containing a known nested-mutability shape
    (``asset_families_snapshot`` today) are exempt: the outer type is
    ``dict``, so the per-key mutability check doesn't apply.
    """
    nested_mutability_entries: frozenset[str] = frozenset()
    for entry in MUTABLE_COLLECTION_EVENT_FIELDS:
        # entry format: cora.<bc>.aggregates.<agg>.events.<Class>.<field>
        module_parts = entry.split(".")
        # Last two parts are <Class>.<field>; everything before is module path.
        *module_path, class_name, field_name = module_parts
        assert module_path[0] == "cora", f"{entry}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*module_path[1:]).with_suffix(".py")
        assert path.is_file(), f"{entry}: file no longer exists; remove allowlist entry"
        tree = ast.parse(path.read_text())
        cls = next(
            (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name),
            None,
        )
        assert cls is not None, (
            f"{entry}: class {class_name} no longer defined; remove allowlist entry"
        )
        field_stmt = next(
            (
                s
                for s in cls.body
                if isinstance(s, ast.AnnAssign)
                and isinstance(s.target, ast.Name)
                and s.target.id == field_name
            ),
            None,
        )
        assert field_stmt is not None, (
            f"{entry}: field {field_name} no longer declared; remove allowlist entry"
        )
        if entry in nested_mutability_entries:
            continue
        assert _mutable_collection_name(field_stmt.annotation) is not None, (
            f"{entry}: field is no longer list/set typed; remove allowlist entry"
        )
