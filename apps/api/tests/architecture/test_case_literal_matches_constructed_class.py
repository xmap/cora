"""Pin: a `from_stored` case literal equals the class its body constructs.

The write side is `event_type_name(event) == type(event).__name__`. The read
side dispatches on `case "<literal>":`. Nothing in the codebase ties those two
strings together, so a literal that drifts from its class name is a silent,
total break: the event writes fine, and every later fold of that stream raises
`Unknown <Aggregate>Event event_type` at the wildcard arm. Not a degraded
read. The whole stream stops loading.

## Why the existing coverage test cannot see this

`test_event_union_from_stored_coverage.py` pins that every union member has
SOME case constructing it, and that no case constructs a foreign class. Its
docstring (the "aliased to it are fine" clause) deliberately permits extra
literals mapped to a union member, because that is exactly the shape a legacy
rename takes. So a typo'd or stale literal satisfies it: the class is still
reachable through its correct arm, and the bad arm still builds a member of
the union.

## Why tests do not catch it either

The 2026-08-01 gate review demonstrated this rather than argued it. Injecting
a literal/class divergence into `AllocationCeilingUpdated` left 155
allocation-touching tests and all three replay fitness functions green. The
control injection on the Agent side failed 5 tests only because that slice's
idempotency check forces a stream load; Allocation has no test that writes a
ceiling update twice on one stream, so the event is never deserialized
anywhere. Round-trip coverage is per-event and easy to be missing; this
function is per-arm and cannot be.

The same class of bug reached HEAD once already in this branch: renaming
`AgentToolRevoked`'s payload arm updated the class and `from_stored` while
silently skipping `to_payload`, because that arm happened to be written on one
line where its neighbours span several. A round-trip test caught it. Luck is
not a control.

## Deviations

`_LEGACY_ALIASES` holds literals that intentionally differ, keyed by the
qualified module. The Marten / Axon canonical-rename pattern needs exactly
this: a superseded discriminator kept forever so pre-rename payloads still
fold. One exists today. Adding an entry is a real decision (it means a stream
somewhere holds the old string) and should come with the golden fixture under
`tests/fixtures/event_corpus/` that the corpus README requires.

Guarded against staleness below: an entry whose literal now matches its class
fails, so a cleanup cannot leave a dead exemption behind.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _event_files() -> list[Path]:
    return sorted(
        f
        for f in tracked_python_files()
        if f.name == "events.py"
        and f.parent.parent.name == "aggregates"
        and f.parent.parent.parent.parent == CORA_ROOT
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _find_from_stored(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "from_stored":
            return node
    return None


def _builder_target_class(call: ast.Call, case_scope: ast.AST) -> str | None:
    """Resolve the event class constructed by a ``deserialize_or_raise`` call.

    Recognises two shapes used by the ``cora.infrastructure.event_payload``
    helper:

      - ``deserialize_or_raise("X", lambda: ClassName(...))`` -> ``ClassName``
      - ``deserialize_or_raise("X", _build_x)`` -> walks the nested
        ``def _build_x()`` inside ``case_scope`` and returns the
        ``return ClassName(...)`` target.
    """
    if not (isinstance(call.func, ast.Name) and call.func.id == "deserialize_or_raise"):
        return None
    if len(call.args) < 2:
        return None
    builder = call.args[1]
    if isinstance(builder, ast.Lambda) and isinstance(builder.body, ast.Call):
        body_call = builder.body
        if isinstance(body_call.func, ast.Name):
            return body_call.func.id
        return None
    if isinstance(builder, ast.Name):
        for node in ast.walk(case_scope):
            if isinstance(node, ast.FunctionDef) and node.name == builder.id:
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Return)
                        and isinstance(sub.value, ast.Call)
                        and isinstance(sub.value.func, ast.Name)
                    ):
                        return sub.value.func.id
        return None
    return None


def _string_literals_in_pattern(pattern: ast.pattern) -> list[str]:
    """Return every string-literal value covered by a ``case`` pattern.

    Handles two shapes:
      - ``case "X":`` (single literal; ``ast.MatchValue``)
      - ``case "X" | "Y" | ...:`` (legacy-rename dual-match per the
        Marten/Axon precedent; ``ast.MatchOr`` of MatchValues)

    Other pattern shapes (capture, class, mapping) return empty:
    they don't dispatch on the discriminator string and are out of
    scope for this audit.
    """
    if (
        isinstance(pattern, ast.MatchValue)
        and isinstance(pattern.value, ast.Constant)
        and isinstance(pattern.value.value, str)
    ):
        return [pattern.value.value]
    if isinstance(pattern, ast.MatchOr):
        out: list[str] = []
        for sub in pattern.patterns:
            out.extend(_string_literals_in_pattern(sub))
        return out
    return []


def _collect_case_targets(func: ast.FunctionDef) -> dict[str, str | None]:
    """For each ``case "X":`` (or ``case "X" | "Y":``) arm, return
    ``{X: ClassName, Y: ClassName}`` it constructs.

    Maps a case string to the name of the dataclass returned by its body.
    Recognises both the legacy ``return ClassName(...)`` shape and the
    ``return deserialize_or_raise("X", lambda: ClassName(...))`` /
    ``return deserialize_or_raise("X", _build_x)`` shapes introduced by
    ``cora.infrastructure.event_payload.deserialize_or_raise``.
    """
    out: dict[str, str | None] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            case_strings = _string_literals_in_pattern(case.pattern)
            if not case_strings:
                continue
            target: str | None = None
            for body_node in ast.walk(case):
                if not (
                    isinstance(body_node, ast.Return) and isinstance(body_node.value, ast.Call)
                ):
                    continue
                call = body_node.value
                if isinstance(call.func, ast.Name) and call.func.id == "deserialize_or_raise":
                    target = _builder_target_class(call, case)
                    break
                if isinstance(call.func, ast.Name):
                    target = call.func.id
                    break
            for case_str in case_strings:
                out[case_str] = target
    return out


# (qualified module, case literal) -> the class it deliberately builds.
_LEGACY_ALIASES: dict[tuple[str, str], str] = {
    (
        "cora.access.aggregates.actor.events",
        "ActorRegisteredV2",
    ): "ActorRegistered",
}


def _divergences(path: Path) -> list[tuple[str, str]]:
    """`(literal, constructed class)` pairs where the two names differ."""
    tree = ast.parse(path.read_text())
    func = _find_from_stored(tree)
    if func is None:
        return []
    return [
        (literal, built)
        for literal, built in _collect_case_targets(func).items()
        if built is not None and literal != built
    ]


@pytest.mark.architecture
@pytest.mark.parametrize("events_file", _event_files(), ids=_qualified)
def test_case_literal_matches_the_class_it_constructs(events_file: Path) -> None:
    module = _qualified(events_file)
    unexplained = [
        (literal, built)
        for literal, built in _divergences(events_file)
        if _LEGACY_ALIASES.get((module, literal)) != built
    ]
    assert not unexplained, (
        f"{module}: {unexplained} dispatch on a literal that is not the name of "
        "the class they build. The write side stores `type(event).__name__`, so "
        "these arms can never match a real stored event, and the wildcard arm "
        "will raise on every fold of that stream. Fix the literal to match the "
        "class, or, if a stream genuinely holds the old discriminator, add it to "
        "`_LEGACY_ALIASES` in this file together with a golden fixture under "
        "tests/fixtures/event_corpus/."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_LEGACY_ALIASES))
def test_legacy_alias_still_diverges(key: tuple[str, str]) -> None:
    """An alias whose literal now matches its class is a dead exemption."""
    module, literal = key
    matching = [f for f in _event_files() if _qualified(f) == module]
    assert matching, (
        f"Legacy alias {key!r} names a module that no longer exists. The "
        "aggregate was removed or renamed; update or prune the entry."
    )
    found = dict(_divergences(matching[0]))
    assert literal in found, (
        f"Legacy alias {key!r} no longer diverges: `case {literal!r}` either "
        "was removed or now matches the class it builds. Remove the entry so "
        "the arm stays pinned from here on."
    )
    assert found[literal] == _LEGACY_ALIASES[key], (
        f"Legacy alias {key!r} now builds {found[literal]!r}, not "
        f"{_LEGACY_ALIASES[key]!r}. That is a different deviation from the one "
        "recorded here; re-adjudicate it rather than widening the entry."
    )
