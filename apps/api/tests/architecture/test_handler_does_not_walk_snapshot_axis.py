"""Pin: a handler that consumes the Asset lookup must not hand-walk the chain (Anti-hook 5c).

The chain walk is the AssetLookup port's job (ancestors_of). A handler
that consumes the Asset lookup (references `asset_lookup` / `ancestors_of`)
must call that method, NOT reconstruct the Asset hierarchy itself by
reading a chain axis (`parent_id` / `fixture_id`) off a loaded Asset and
looping. That handler-side walk is the H1 anti-pattern the H3 design
rejected: it scatters cycle-defense and BC-seam discipline across every
consumer instead of keeping it in one reviewed adapter.

The companion snapshot-row pin (test_asset_lookup_result_walk_axis_fields,
5a) already keeps `parent_id` off `AssetLookupResult`, so a handler cannot
walk via the lookup result. This guard closes the other door: a consumer
re-deriving the chain from some OTHER source (a loaded Asset aggregate,
say) while holding the lookup.

Scope: handler files that reference the Asset lookup. Trip: such a handler
makes an attribute access `.parent_id` or `.fixture_id` (the Asset-chain
traversal axes). `subject_id` is deliberately NOT in the trip set: it is a
Subject-binding identifier ubiquitous in handlers (`command.subject_id`),
not an Asset-chain axis; 5a already keeps it off the snapshot row. Uses
AST so a `parent_id=` keyword argument (an `ast.keyword`, not an
`ast.Attribute`) never trips this -- only a genuine attribute read does.

The allowlist starts EMPTY and every Asset-lookup consumer obeys (each
accesses only `.id` and `.lifecycle` on the walk result). Adding an entry
means a handler walks an Asset-chain axis itself instead of calling
ancestors_of, which needs a design conversation, not an incidental edit.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Attribute accesses that signal a handler-side Asset-chain walk.
_WALK_AXIS_ATTRS: frozenset[str] = frozenset({"parent_id", "fixture_id"})

# A handler "consumes the Asset lookup" if it touches either of these.
_LOOKUP_ATTRS: frozenset[str] = frozenset({"asset_lookup", "ancestors_of"})

# Handlers permitted to access an Asset-chain axis despite consuming the
# lookup. Empty by design; extend only at a design review.
_ALLOWLIST: frozenset[str] = frozenset()


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _handler_files() -> list[Path]:
    return sorted(
        p for p in tracked_python_files() if p.name == "handler.py" and "/features/" in str(p)
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", _handler_files(), ids=_qualified)
def test_asset_lookup_consuming_handler_does_not_walk_chain_axis(path: Path) -> None:
    tree = ast.parse(path.read_text())

    attrs = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
    consumes_lookup = any(a.attr in _LOOKUP_ATTRS for a in attrs)
    if not consumes_lookup:
        return
    if _qualified(path) in _ALLOWLIST:
        return

    walk_hits = sorted({f"line {a.lineno}: .{a.attr}" for a in attrs if a.attr in _WALK_AXIS_ATTRS})
    assert not walk_hits, (
        f"{_qualified(path)} consumes the Asset lookup AND accesses an Asset-chain "
        "axis:\n  " + "\n  ".join(walk_hits) + "\n\nA handler that needs the ancestor "
        "closure must call AssetLookup.ancestors_of, not re-derive the chain by reading "
        "parent_id / fixture_id itself (the H1 handler-walks-the-tree anti-pattern). See "
        "chain-walk Anti-hook 5c. If this access is genuinely unrelated to chain walking "
        "(requires a design review), add the handler's qualified name to _ALLOWLIST."
    )


@pytest.mark.architecture
def test_guard_actually_has_lookup_consuming_handlers_in_scope() -> None:
    """Anti-vacuity anchor: at least one handler consumes the Asset lookup,
    so the parametrized guard above is genuinely evaluated and not a silent
    no-op (which it would become if `_LOOKUP_ATTRS` drifted from the real
    attribute names)."""
    consumers = [
        _qualified(p)
        for p in _handler_files()
        if any(
            isinstance(n, ast.Attribute) and n.attr in _LOOKUP_ATTRS
            for n in ast.walk(ast.parse(p.read_text()))
        )
    ]
    assert consumers, (
        "no handler references asset_lookup / ancestors_of, so the 5c guard scans nothing. "
        "Either the markers in _LOOKUP_ATTRS drifted, or every consumer was removed."
    )
