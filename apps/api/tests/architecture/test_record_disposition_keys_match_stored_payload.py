"""Pin: the disposition table's keys are the keys `to_payload` writes.

The generated redaction table (`_dispositions.py`) is built from each
event's DATACLASS FIELD names (`tools/gen_record_dispositions.py`'s
`_resolve_fields`, absent a `_OVERRIDE_WIRE_KEYS` entry). Redaction
(`redact_tier1_payload`) looks a field up by iterating the STORED
PAYLOAD's own keys -- the literal strings `to_payload` writes into the
dict jsonb actually holds. When a field's dataclass name and its wire
key disagree, the table carries a rule under a key redaction will never
see, and the actual stored key has no rule at all: the field drops by
the ordinary "unlisted key" default, silently, forever, for every event
of that type any export will ever carry.

This is F6's root cause measured directly: `DatasetRegistered` declared
`checksum_algorithm` / `checksum_value` while `to_payload` nested them
under `"checksum"`, so the checksum -- the one field that makes a
published record checkable against the data it describes -- dropped by
a rule that could never fire, not by a redaction DECISION. Nine event
classes had this shape before it was fixed; this test is what keeps a
tenth from arriving unnoticed.

## Scope

Only event classes whose `to_payload` `case ClassName(...):` arm returns
a PLAIN dict literal with string-constant keys are checked: that covers
the AST shape most event classes in this codebase use, but not all of
them. A class using some other shape does not silently pass, it does
not appear in the comparison at all (see `_KEYS_BY_CLASS`'s docstring).

As of this writing, 18 committed event classes build their payload as
`payload: dict[str, Any] = {...}` followed by conditional
`payload["x"] = ...` mutation rather than a single `return {...}`
literal, and are therefore NOT checked by this test: `AssetRegistered`
and all six Supply lifecycle events (`SupplyRegistered`,
`SupplyDegraded`, `SupplyDeregistered`, `SupplyMarkedAvailable`,
`SupplyMarkedRecovering`, `SupplyMarkedUnavailable`, `SupplyRestored`),
plus `ActorRegisteredV2`, `CalibrationRevisionAppended`,
`CautionAcknowledgement`, `EnclosurePermitObserved`,
`MethodRequiredRoleAdded`, `MethodVersioned`, `ModelDefined`,
`PlanVersioned`, `VisitCheckedOut`, `VisitPresenceClosed`. Notably this
includes Equipment and Supply, the two BCs already carrying VOs
directly on events, so a future field-name/wire-key mismatch in exactly
that shape would stay undetected. Widening `_dict_literal_keys` to read
the assign-then-mutate shape closes this gap; it is not attempted here
because it is a second AST case, not a fix to this one. If a future
event ever builds its payload some third way, this test needs a
matching AST case too, not a bigger blind spot.

## Why this stays a static AST check, not an import

Resolving `DISPOSITIONS` is a normal import (it lives in
`cora.infrastructure.record_export`, not the generator). Resolving
`to_payload`'s actual keys is done by parsing SOURCE, deliberately not
by calling `to_payload` on a constructed instance: constructing a real
instance of all 235 event classes would need valid values for every
field (including cross-BC value objects with their own validation),
which is exactly the generator-internal cost the campaign chose not to
pay for a stronger, structural-parity-only guarantee (see
`RedactionResult.unfired_tier1_fields`'s docstring for the tradeoff
argument). A static AST read has no such cost and needs no live data.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.record_export._dispositions import DISPOSITIONS
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


def _find_to_payload(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "to_payload":
            return node
    return None


def _match_class_name(pattern: ast.pattern) -> str | None:
    """The class name a `case ClassName(...):` arm dispatches on.

    `ast.MatchClass.cls` is an `ast.Name` for a bare `ClassName(...)`
    pattern (every event class in this codebase) or an `ast.Attribute`
    for a qualified `module.ClassName(...)` pattern (unused today, kept
    so a future qualified pattern does not silently fall through).
    """
    if not isinstance(pattern, ast.MatchClass):
        return None
    if isinstance(pattern.cls, ast.Name):
        return pattern.cls.id
    if isinstance(pattern.cls, ast.Attribute):
        return pattern.cls.attr
    return None


def _dict_literal_keys(case: ast.match_case) -> frozenset[str] | None:
    """String-literal keys of this arm's `return {...}`, or `None` if
    the arm's return value is not a plain dict literal with every key a
    string constant (out of scope; see module docstring)."""
    for node in ast.walk(case):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            string_keys: list[str] = []
            for k in node.value.keys:
                if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                    return None
                string_keys.append(k.value)
            return frozenset(string_keys)
    return None


def _keys_by_class(func: ast.FunctionDef) -> dict[str, frozenset[str]]:
    """`{ClassName: {stored keys}}` for every arm whose payload is a
    plain dict literal. An arm this cannot read (see `_dict_literal_keys`)
    is simply absent from the result, not recorded as empty."""
    out: dict[str, frozenset[str]] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            class_name = _match_class_name(case.pattern)
            if class_name is None:
                continue
            keys = _dict_literal_keys(case)
            if keys is not None:
                out[class_name] = keys
    return out


def _stored_keys_by_class() -> dict[str, tuple[Path, frozenset[str]]]:
    """`{ClassName: (defining file, stored keys)}` across every tracked
    `events.py`, for classes whose `to_payload` arm is AST-readable."""
    out: dict[str, tuple[Path, frozenset[str]]] = {}
    for path in _event_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        func = _find_to_payload(tree)
        if func is None:
            continue
        for class_name, keys in _keys_by_class(func).items():
            out[class_name] = (path, keys)
    return out


def _cases() -> list[tuple[str, Path, frozenset[str]]]:
    """One case per event type this test can actually check: present in
    BOTH the committed table and an AST-readable `to_payload` arm."""
    stored = _stored_keys_by_class()
    return sorted(
        (event_type, path, keys)
        for event_type, (path, keys) in stored.items()
        if event_type in DISPOSITIONS
    )


_CASES = _cases()


@pytest.mark.architecture
@pytest.mark.parametrize("case", _CASES, ids=lambda c: c[0])
def test_disposition_keys_match_stored_payload_keys(case: tuple[str, Path, frozenset[str]]) -> None:
    event_type, path, stored_keys = case
    table_keys = frozenset(DISPOSITIONS[event_type])

    dead_rules = table_keys - stored_keys
    unruled_keys = stored_keys - table_keys

    assert not dead_rules and not unruled_keys, (
        f"{event_type} ({path}): the generated disposition table and "
        f"to_payload's actual stored keys disagree. Rules that can never "
        f"fire (declared in DISPOSITIONS, absent from the stored payload): "
        f"{sorted(dead_rules)}. Stored keys with no rule (redacted by the "
        f"unlisted-key default, silently, forever): {sorted(unruled_keys)}. "
        "If the field's dataclass name deliberately differs from its wire "
        "key, add an entry to `_OVERRIDE_WIRE_KEYS` in "
        "tools/gen_record_dispositions.py and regenerate with "
        "`make record-dispositions`; otherwise retype the field so its "
        "declared shape matches what it is actually stored as."
    )


@pytest.mark.architecture
def test_at_least_the_known_checksum_carrying_events_are_checked() -> None:
    """Canary: if the AST walk above ever matches nothing (a refactor of
    `to_payload`'s shape broke `_dict_literal_keys`'s assumptions), this
    test says so specifically rather than the parametrized suite quietly
    collecting zero cases and reporting all green."""
    checked = {event_type for event_type, _, _ in _CASES}
    expected = {"DatasetRegistered", "DistributionRegistered"}
    missing = expected - checked
    assert not missing, (
        f"{sorted(missing)} should be AST-readable by this test's "
        "to_payload walk and are not; the walk's assumptions about the "
        "match-arm shape have drifted from the real event modules."
    )
