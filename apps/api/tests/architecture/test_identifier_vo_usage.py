"""Pin: every 2-field `(scheme, value)`-shaped VO either reuses the shared
`cora.shared.identifier.Identifier` VO or carries a deviation
docstring explaining why it stays bespoke.

The open-scheme anti-corruption-ref VO `Identifier(scheme, value)` is the
canonical home for upstream-deferred (scheme, value) pairs CORA does not
model as first-class aggregates. A frozen dataclass with EXACTLY two
annotated fields whose names match the scheme allowlist (`scheme`, `kind`,
`algorithm`, `source_kind`, `identifier_type`, `system`) AND the value
allowlist (`value`, `id`, `number`, `code`, `identifier`) is structurally
indistinguishable from `Identifier` and SHOULD either:

  (a) compose `Identifier` directly (import from
      `cora.shared.identifier`), or
  (b) appear in the deviation allowlist below with a docstring line
      matching `r'^\\s*Deviation from Identifier VO:\\s+'` justifying why
      the bespoke shape is load-bearing (closed-enum scheme, third
      field, stricter value invariant, intra-CORA UUID wrapper, etc.).

The allowlist captures every known legitimate deviation across the
codebase today. New 2-field `(scheme, value)`-shaped VOs that do not
appear here MUST route through `Identifier`; reviewers catch the
reinvention at PR time.

The companion test `test_allowlist_members_carry_deviation_docstring`
walks every allowlisted class and verifies the deviation regex hits
its docstring; this stops the allowlist from silently absorbing classes
whose deviation rationale was deleted.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_SCHEME_FIELD_NAMES: frozenset[str] = frozenset(
    {"scheme", "kind", "algorithm", "source_kind", "identifier_type", "system"}
)
_VALUE_FIELD_NAMES: frozenset[str] = frozenset({"value", "id", "number", "code", "identifier"})

# Classes that legitimately deviate from the shared Identifier VO shape.
# Each member MUST carry a docstring line matching _DEVIATION_DOCSTRING_REGEX
# explaining why the bespoke shape stays. The companion test enforces this.
#
# The federation Credential / Seal aggregate roots carry opaque
# single-string SecretStore-pointer fields (`Credential.secret_ref`,
# `Credential.public_material_ref`, `Credential.rotation_pending_secret_ref`,
# `Seal.online_credential_id`, `Seal.offline_credential_id`) directly on
# the aggregate root, NOT inside a 2-field `(scheme, value)` VO; they do
# not match the structural predicate and are intentionally NOT in the
# allowlist. If a future refactor extracts a 2-field VO carrying any of
# those pointer pairs, add that VO class name here with the required
# deviation docstring.
_DEVIATION_ALLOWLIST: frozenset[str] = frozenset(
    {
        "AlternateIdentifier",
        "PersistentIdentifier",
        "DatasetChecksum",
    }
)

_DEVIATION_DOCSTRING_REGEX = re.compile(r"^\s*Deviation from Identifier VO:\s+", flags=re.MULTILINE)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_frozen_dataclass_decorator(decorator: ast.expr) -> bool:
    """True for `@dataclass(frozen=True)` (call form with the literal True)."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    name = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else None
    )
    if name != "dataclass":
        return False
    frozen_kw = next((kw for kw in decorator.keywords if kw.arg == "frozen"), None)
    if frozen_kw is None:
        return False
    return isinstance(frozen_kw.value, ast.Constant) and frozen_kw.value.value is True


def _has_frozen_dataclass_decorator(class_def: ast.ClassDef) -> bool:
    return any(_is_frozen_dataclass_decorator(d) for d in class_def.decorator_list)


def _annotated_field_names(class_def: ast.ClassDef) -> list[str]:
    """Return the names of all annotated assignments in the class body."""
    names: list[str] = []
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def _matches_identifier_shape(class_def: ast.ClassDef) -> bool:
    """True for a frozen dataclass with exactly two annotated fields whose
    names hit both the scheme allowlist and the value allowlist."""
    if not _has_frozen_dataclass_decorator(class_def):
        return False
    field_names = _annotated_field_names(class_def)
    if len(field_names) != 2:
        return False
    name_set = set(field_names)
    return bool(name_set & _SCHEME_FIELD_NAMES) and bool(name_set & _VALUE_FIELD_NAMES)


def _module_imports_identifier(tree: ast.AST) -> bool:
    """True if the module imports `Identifier` from `cora.shared.identifier`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module != "cora.shared.identifier":
                continue
            if any(alias.name == "Identifier" for alias in node.names):
                return True
    return False


def _scanned_state_files() -> list[Path]:
    """Tracked `state.py` files under `cora/**/aggregates/**/` plus any
    `cora/**/state.py` (no `state.py` files live outside aggregates today,
    but the broader walk keeps the pin honest if one ever lands)."""
    return sorted(path for path in tracked_python_files() if path.name == "state.py")


def _candidate_classes(tree: ast.AST) -> list[ast.ClassDef]:
    """Frozen-dataclass classes whose 2-field shape matches the Identifier
    structural predicate."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _matches_identifier_shape(node)
    ]


@pytest.mark.architecture
@pytest.mark.parametrize("path", _scanned_state_files(), ids=_qualified)
def test_identifier_shaped_vos_compose_or_deviate_explicitly(path: Path) -> None:
    """Every 2-field `(scheme, value)`-shaped frozen dataclass either composes
    `Identifier` (module imports it) or appears in the deviation allowlist
    with the required deviation docstring."""
    tree = ast.parse(path.read_text())
    candidates = _candidate_classes(tree)
    if not candidates:
        return

    module_uses_identifier = _module_imports_identifier(tree)
    offenders: list[str] = []
    for cls in candidates:
        if cls.name in _DEVIATION_ALLOWLIST:
            docstring = ast.get_docstring(cls) or ""
            if not _DEVIATION_DOCSTRING_REGEX.search(docstring):
                offenders.append(
                    f"line {cls.lineno}: {cls.name} is allowlisted but its docstring "
                    "is missing the required line "
                    "'Deviation from Identifier VO: <reason>'"
                )
            continue
        if module_uses_identifier:
            # The class is Identifier-shaped but the module already imports
            # Identifier; the bespoke class is still a reinvention. Surface it.
            offenders.append(
                f"line {cls.lineno}: {cls.name} duplicates the Identifier VO shape; "
                "use the imported Identifier directly instead of declaring a "
                "structurally identical bespoke class"
            )
        else:
            offenders.append(f"line {cls.lineno}: {cls.name} reinvents the Identifier VO shape")

    assert not offenders, (
        f"{_qualified(path)} has Identifier-shaped VO(s) that neither compose "
        "nor explicitly deviate:\n  "
        + "\n  ".join(offenders)
        + "\n\nA frozen dataclass with exactly two fields named from "
        f"scheme={sorted(_SCHEME_FIELD_NAMES)} AND value={sorted(_VALUE_FIELD_NAMES)} "
        "is the canonical `Identifier(scheme, value)` shape. Either import "
        "`Identifier` from `cora.shared.identifier` and compose it, "
        "or add the class to the deviation allowlist in this test plus a "
        "docstring line matching r'^\\s*Deviation from Identifier VO:\\s+' "
        "explaining what load-bearing constraint forces the bespoke shape."
    )


def _resolve_allowlist_classes() -> dict[str, tuple[Path, ast.ClassDef]]:
    """Locate the canonical aggregate-tier ClassDef for every allowlisted name.

    Several allowlisted names recur across the codebase (Manufacturer
    exists both as an aggregate VO in `equipment/aggregates/model/state.py`
    and as a wire-DTO in `equipment/_pidinst/_types.py`; ModelRef exists
    both as an Agent aggregate VO and as an LLM port DTO). The aggregate-
    tier definition is the canonical one for this fitness check: that
    is the class whose shape composes (or deviates from) the Identifier
    VO at the domain layer. Wire DTOs and port DTOs are outside the
    Identifier-VO contract by construction.

    Resolution preference, in order:
      1. Files under `aggregates/<name>/state.py`.
      2. Files under `aggregates/` (covers shared helpers like
         `aggregates/_drawing.py`).
      3. Any remaining tracked .py file (fallback; never expected to
         fire for the locked allowlist members).

    Skips `__init__.py` because re-exports duplicate names without
    moving the canonical definition.
    """
    candidates_by_name: dict[str, list[tuple[int, Path, ast.ClassDef]]] = {}
    for path in sorted(tracked_python_files()):
        if path.name == "__init__.py":
            continue
        path_str = str(path)
        if "/aggregates/" in path_str and path.name == "state.py":
            tier = 0
        elif "/aggregates/" in path_str:
            tier = 1
        else:
            tier = 2
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name not in _DEVIATION_ALLOWLIST:
                continue
            candidates_by_name.setdefault(node.name, []).append((tier, path, node))

    located: dict[str, tuple[Path, ast.ClassDef]] = {}
    for name, hits in candidates_by_name.items():
        hits.sort(key=lambda h: (h[0], str(h[1])))
        _, path, cls = hits[0]
        located[name] = (path, cls)
    return located


@pytest.mark.architecture
@pytest.mark.parametrize("class_name", sorted(_DEVIATION_ALLOWLIST))
def test_allowlist_members_carry_deviation_docstring(class_name: str) -> None:
    """Every allowlisted class MUST carry the required deviation docstring
    line. Stops the allowlist from silently absorbing classes whose
    rationale was deleted during an unrelated refactor."""
    located = _resolve_allowlist_classes()
    assert class_name in located, (
        f"Deviation allowlist member {class_name!r} was not found in any "
        "tracked source file; remove the stale entry from the allowlist "
        "in tests/architecture/test_identifier_vo_usage.py."
    )
    path, cls = located[class_name]
    docstring = ast.get_docstring(cls) or ""
    assert _DEVIATION_DOCSTRING_REGEX.search(docstring), (
        f"{_qualified(path)}::{class_name} is in the Identifier-VO deviation "
        "allowlist but its docstring does not carry the required line "
        "'Deviation from Identifier VO: <reason>'. Either add the line "
        "(explaining what load-bearing constraint forces the bespoke shape) "
        "or remove the class from the allowlist if the deviation is no "
        "longer load-bearing."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("class_name", sorted(_DEVIATION_ALLOWLIST))
def test_allowlist_members_match_identifier_structural_predicate(class_name: str) -> None:
    """Every allowlisted class MUST actually match the Identifier
    structural predicate (frozen dataclass with EXACTLY two annotated
    fields, one from the scheme allowlist, one from the value allowlist).

    Defensive allowlist entries for classes that no longer match the
    predicate (3+ fields, single-field UUID wrappers, etc.) exempt
    nothing: the primary test would not flag them. This drift catcher
    forces the allowlist to shrink as classes evolve away from the
    Identifier shape.
    """
    located = _resolve_allowlist_classes()
    assert class_name in located, (
        f"Deviation allowlist member {class_name!r} was not found in any "
        "tracked source file; remove the stale entry."
    )
    path, cls = located[class_name]
    assert _matches_identifier_shape(cls), (
        f"{_qualified(path)}::{class_name} is in the Identifier-VO deviation "
        "allowlist but no longer matches the structural predicate "
        "(frozen dataclass with EXACTLY two annotated fields, one named "
        f"from scheme={sorted(_SCHEME_FIELD_NAMES)}, one from "
        f"value={sorted(_VALUE_FIELD_NAMES)}). The primary test would not "
        "flag this class today; remove the entry from the allowlist."
    )
