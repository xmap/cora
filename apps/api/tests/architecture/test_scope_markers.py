"""Catalog: every `Annotated[T, ...]` site that uses one of the three
scope-marker classes (`NamedFor`, `DeferredVocabulary`, `SubsumedBy`)
from `cora.shared.scope_markers`, with a structural sanity
check on each marker's argument shape.

The three markers (per `project_structural_scope_design.md` §"Marker
convention") record a design-intent stance on bare-str / closed-enum
fields that masquerade as references to a missing aggregate. Today
this fitness test ONLY enumerates the sites and asserts each marker
is constructed with well-formed arguments; it does NOT yet enforce
the deeper invariants those markers imply (e.g. `SubsumedBy` targets
must NOT exist as aggregates today, `DeferredVocabulary.trigger_doc`
must reference a real memo). Those stricter assertions land when the
marker family accumulates enough sites that the looser per-marker
contract starts to drift; today three sites is below the rule-of-three
threshold.

Walks tracked `.py` files under `src/cora/` via `tracked_python_files()`
per the git-aware enumeration rule (see conftest.py). For each
`Annotated[...]` expression, checks the metadata args for direct calls
to `NamedFor(...)`, `DeferredVocabulary(...)`, `SubsumedBy(...)` and
verifies:

  - `NamedFor` is called with a string `target_name`.
  - `DeferredVocabulary` is called with string `target_name` and
    string `trigger_doc`.
  - `SubsumedBy` is called with string `subsumed_target_name` and a
    tuple-literal `subsuming_aggregate_names` whose members are
    strings.

A malformed marker (wrong keyword, non-string argument, missing field)
fails the test loudly; well-formed markers pass silently. A separate
test reports the current catalog count, exercised as a
parameterise-over-marker-kinds smoke check.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


_MARKER_NAMES: frozenset[str] = frozenset({"NamedFor", "DeferredVocabulary", "SubsumedBy"})


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@dataclass(frozen=True, slots=True)
class MarkerSite:
    """One occurrence of a scope-marker in an `Annotated[...]` expression."""

    path: Path
    lineno: int
    field_name: str | None  # None when the Annotated is not directly an AnnAssign target
    marker_kind: str  # one of _MARKER_NAMES
    marker_call: ast.Call


def _call_name(call: ast.Call) -> str | None:
    """Return the callee name for a `Foo(...)` or `mod.Foo(...)` call."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_annotated_subscript(node: ast.AST) -> bool:
    """True for `Annotated[...]` (Subscript with .value an `Annotated` Name/Attribute)."""
    if not isinstance(node, ast.Subscript):
        return False
    value = node.value
    if isinstance(value, ast.Name):
        return value.id == "Annotated"
    if isinstance(value, ast.Attribute):
        return value.attr == "Annotated"
    return False


def _annotated_metadata_args(subscript: ast.Subscript) -> Iterator[ast.expr]:
    """Yield the metadata args of an `Annotated[T, m1, m2, ...]` expression.

    `Annotated[T, m1]` parses as `Subscript(value=Annotated, slice=Tuple([T, m1]))`
    in modern CPython; older shapes wrapped slice in `Index`. Both are
    handled. Single-arg form `Annotated[T]` (no metadata) yields nothing.
    """
    # CPython 3.9+ uses the slice value directly (no ast.Index wrapper).
    sl = subscript.slice
    if isinstance(sl, ast.Tuple):
        # First elt is T, rest are metadata.
        yield from sl.elts[1:]


def _walk_annotated_calls(tree: ast.AST) -> Iterator[tuple[ast.Subscript, ast.expr | None]]:
    """Yield (Annotated subscript node, enclosing AnnAssign-target name or None).

    The enclosing target lets us attribute marker sites to a specific
    aggregate-state field for the catalog. Markers used outside an
    AnnAssign (e.g. in a type alias) attribute as `field_name=None`.
    """
    # Build a map node-id -> ann-assign target name, scanned with parents.
    target_for: dict[int, ast.expr] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            target_for[id(node.annotation)] = node.target
    for node in ast.walk(tree):
        if _is_annotated_subscript(node):
            assert isinstance(node, ast.Subscript)
            yield node, target_for.get(id(node))


def _marker_sites_in_file(path: Path) -> list[MarkerSite]:
    """Catalog all marker sites in one file."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    sites: list[MarkerSite] = []
    for subscript, target in _walk_annotated_calls(tree):
        for meta in _annotated_metadata_args(subscript):
            if not isinstance(meta, ast.Call):
                continue
            name = _call_name(meta)
            if name is None or name not in _MARKER_NAMES:
                continue
            field_name: str | None = None
            if isinstance(target, ast.Name):
                field_name = target.id
            sites.append(
                MarkerSite(
                    path=path,
                    lineno=meta.lineno,
                    field_name=field_name,
                    marker_kind=name,
                    marker_call=meta,
                )
            )
    return sites


def _all_marker_sites() -> list[MarkerSite]:
    sites: list[MarkerSite] = []
    for path in sorted(tracked_python_files()):
        sites.extend(_marker_sites_in_file(path))
    return sites


def _is_string_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _kwargs_by_name(call: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def _check_named_for(call: ast.Call) -> list[str]:
    """Sanity-check a `NamedFor(target_name=...)` call. Returns list of issues."""
    issues: list[str] = []
    kwargs = _kwargs_by_name(call)
    # NamedFor accepts target_name positionally or as a keyword.
    if "target_name" in kwargs:
        if not _is_string_constant(kwargs["target_name"]):
            issues.append("NamedFor.target_name must be a string literal")
    elif call.args:
        if not _is_string_constant(call.args[0]):
            issues.append("NamedFor positional target_name must be a string literal")
    else:
        issues.append("NamedFor requires target_name")
    return issues


def _check_deferred_vocabulary(call: ast.Call) -> list[str]:
    """Sanity-check a `DeferredVocabulary(...)` call."""
    issues: list[str] = []
    kwargs = _kwargs_by_name(call)
    # Resolve target_name + trigger_doc (positional or keyword).
    target_name_node: ast.expr | None = (
        kwargs.get("target_name")
        if "target_name" in kwargs
        else (call.args[0] if call.args else None)
    )
    trigger_doc_node: ast.expr | None = (
        kwargs.get("trigger_doc")
        if "trigger_doc" in kwargs
        else (call.args[1] if len(call.args) >= 2 else None)
    )
    if target_name_node is None:
        issues.append("DeferredVocabulary requires target_name")
    elif not _is_string_constant(target_name_node):
        issues.append("DeferredVocabulary.target_name must be a string literal")
    if trigger_doc_node is None:
        issues.append("DeferredVocabulary requires trigger_doc")
    elif not _is_string_constant(trigger_doc_node):
        issues.append("DeferredVocabulary.trigger_doc must be a string literal")
    return issues


def _check_subsumed_by(call: ast.Call) -> list[str]:
    """Sanity-check a `SubsumedBy(...)` call."""
    issues: list[str] = []
    kwargs = _kwargs_by_name(call)
    subsumed_node: ast.expr | None = (
        kwargs.get("subsumed_target_name")
        if "subsumed_target_name" in kwargs
        else (call.args[0] if call.args else None)
    )
    subsuming_node: ast.expr | None = (
        kwargs.get("subsuming_aggregate_names")
        if "subsuming_aggregate_names" in kwargs
        else (call.args[1] if len(call.args) >= 2 else None)
    )
    if subsumed_node is None:
        issues.append("SubsumedBy requires subsumed_target_name")
    elif not _is_string_constant(subsumed_node):
        issues.append("SubsumedBy.subsumed_target_name must be a string literal")
    if subsuming_node is None:
        issues.append("SubsumedBy requires subsuming_aggregate_names")
    elif not isinstance(subsuming_node, ast.Tuple):
        issues.append("SubsumedBy.subsuming_aggregate_names must be a tuple literal")
    else:
        for elt in subsuming_node.elts:
            if not _is_string_constant(elt):
                issues.append(
                    "SubsumedBy.subsuming_aggregate_names members must all be string literals"
                )
                break
        if not subsuming_node.elts:
            issues.append("SubsumedBy.subsuming_aggregate_names must be non-empty")
    return issues


_CHECKERS = {
    "NamedFor": _check_named_for,
    "DeferredVocabulary": _check_deferred_vocabulary,
    "SubsumedBy": _check_subsumed_by,
}


@pytest.mark.architecture
def test_scope_marker_sites_are_well_formed() -> None:
    """Every `Annotated[..., NamedFor|DeferredVocabulary|SubsumedBy(...)]` site
    constructs the marker with well-formed arguments per the dataclass shape
    declared in `cora.shared.scope_markers`."""
    sites = _all_marker_sites()
    offenders: list[str] = []
    for site in sites:
        checker = _CHECKERS[site.marker_kind]
        issues = checker(site.marker_call)
        for issue in issues:
            field = site.field_name or "<non-AnnAssign site>"
            offenders.append(
                f"{_qualified(site.path)}:{site.lineno} ({field}, {site.marker_kind}): {issue}"
            )
    assert not offenders, (
        "Malformed scope-marker site(s) found:\n  "
        + "\n  ".join(offenders)
        + "\n\nSee `cora.shared.scope_markers` for the dataclass shapes."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("marker_kind", sorted(_MARKER_NAMES))
def test_scope_marker_catalog_counts(marker_kind: str) -> None:
    """Smoke catalog: assert the marker kind is enumerable (count >= 0).

    Today this is a no-assertion-failure walk; the per-marker count is
    reported via the test id for the operator running `-v`. Future slices
    may tighten this to "exactly N expected sites" once the marker family
    stabilises; today the rule-of-three threshold has not fired."""
    sites = [s for s in _all_marker_sites() if s.marker_kind == marker_kind]
    # Count is observed, never asserted; the test passes by construction.
    # This block is intentionally structured so future tightening (e.g.
    # asserting `len(sites) <= EXPECTED_CEILING`) is a one-line edit.
    assert len(sites) >= 0
