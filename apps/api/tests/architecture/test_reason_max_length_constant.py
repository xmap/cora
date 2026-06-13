"""Pin: the operator-reason length bound lives once, as REASON_MAX_LENGTH.

Operator free-text `reason` strings (abort a Run, deprecate a Model,
reject a Clearance, decommission an Enclosure, ...) are all capped at the
same length. That bound was duplicated as ~38 per-aggregate
`<X>_REASON_MAX_LENGTH = 500` constants plus a scatter of feature-local
`_REASON_MAX_LENGTH = 500` and inline `max_length=500` literals across 12
BCs. It is now hoisted to a single `REASON_MAX_LENGTH` in
`cora.shared.text_bounds`.

This ratchet keeps it hoisted:

  - REASON_MAX_LENGTH is defined in exactly one module, and
  - no other module re-introduces a `*REASON_MAX_LENGTH` numeric
    constant (named aggregate-level OR feature-local `_`-prefixed), and
  - no new inline `max_length=500` reason literal appears (the only
    permitted `max_length=500` literals are a frozen allowlist of
    genuinely non-reason 500-char/500-item bounds).

Unlike the per-VO `MAX_LENGTH` constants (`cora.shared.bounded_text`),
which deliberately stay aggregate-local, a reason is a bare validated
string with one bound everywhere, so it is shared.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# The one module that DEFINES the shared reason bound.
_DEFINITION_HOME = "cora.shared.text_bounds"
_CONSTANT = "REASON_MAX_LENGTH"

# A module-level numeric constant assignment whose name ends in
# REASON_MAX_LENGTH: matches the shared `REASON_MAX_LENGTH = 500`, any
# named `<X>_REASON_MAX_LENGTH = 500`, and any feature-local
# `_REASON_MAX_LENGTH = 500`. References (imports, __all__ entries,
# `max_length=REASON_MAX_LENGTH`) do not match: they are not a
# column-0 `NAME = <number>` assignment.
_DEFINITION_RE = re.compile(
    r"^(?P<name>[A-Z_][A-Z0-9_]*)\s*(?::[^=\n]+)?=\s*\d",
    re.MULTILINE,
)

# Inline char/item bound literal. After the hoist every reason Field
# uses REASON_MAX_LENGTH; the only `max_length=500` literals left are
# genuinely non-reason bounds, frozen here. Shrink-only: removing a
# literal must remove its allowlist entry (see the drift-catcher).
_INLINE_500_RE = re.compile(r"max_length\s*=\s*500\b")
_INLINE_500_ALLOWLIST: frozenset[str] = frozenset(
    {
        # trigger_source: free-form text capturing what initiated a Run,
        # not a transition reason.
        "cora.run.features.start_run.route",
        "cora.run.features.start_run.tool",
        # entries: a 1-500 batch-size cap on the list of step entries,
        # not a char bound on a reason.
        "cora.operation.features.append_activities.tool",
    }
)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
def test_reason_max_length_defined_in_exactly_one_module() -> None:
    definers: list[str] = []
    for p in tracked_python_files():
        for m in _DEFINITION_RE.finditer(p.read_text()):
            if m.group("name").endswith("REASON_MAX_LENGTH"):
                definers.append(f"{_qualified(p)}:{m.group('name')}")
    assert definers == [f"{_DEFINITION_HOME}:{_CONSTANT}"], (
        f"The reason-length bound must be defined once, as {_CONSTANT} in "
        f"{_DEFINITION_HOME}; found {sorted(definers)}. A per-aggregate "
        f"`<X>_REASON_MAX_LENGTH` or feature-local `_REASON_MAX_LENGTH` "
        f"constant re-introduces the duplication this hoist removed. Import "
        f"`from cora.shared.text_bounds import REASON_MAX_LENGTH` instead."
    )


@pytest.mark.architecture
def test_no_unallowlisted_inline_max_length_500() -> None:
    offenders = sorted(
        _qualified(p)
        for p in tracked_python_files()
        if _INLINE_500_RE.search(p.read_text()) and _qualified(p) not in _INLINE_500_ALLOWLIST
    )
    assert not offenders, (
        f"Inline `max_length=500` found in {offenders}. A reason field must "
        f"use `max_length=REASON_MAX_LENGTH` (cora.shared.text_bounds). If "
        f"the 500 is a genuinely non-reason bound, add the module to "
        f"_INLINE_500_ALLOWLIST in this file with a one-line justification."
    )


@pytest.mark.architecture
def test_inline_500_allowlist_has_no_stale_entries() -> None:
    by_module = {_qualified(p): p for p in tracked_python_files()}
    stale = sorted(
        module
        for module in _INLINE_500_ALLOWLIST
        if module not in by_module or not _INLINE_500_RE.search(by_module[module].read_text())
    )
    assert not stale, (
        f"_INLINE_500_ALLOWLIST entries no longer contain a `max_length=500` "
        f"literal: {stale}. Remove them; the allowlist is shrink-only."
    )
