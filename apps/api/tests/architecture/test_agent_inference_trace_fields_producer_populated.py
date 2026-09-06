"""Every `AgentInferenceTrace` PRODUCER passes every declared field.

The historical defect this guards against: a column can exist on the DTO,
carry all the way through the write path, exist in the live table, and
still be written by NOBODY, forever, because every producer construction
site simply never passes it as a keyword. `duration`, `response_id`,
`output_type`, and the three `tool_*` fields were all in this state
simultaneously (0 of 1163 rows populated on the 2-BM record for six of
them), invisible because a NULL column reads as "no data for this call"
rather than "nothing ever writes this."

## The hole in the original guard

The first version of this file checked completeness against the UNION of
every construction site in the tree: a field only had to be passed by SOME
producer, somewhere, to count as covered. `run_debriefer` alone passes all
25 declared fields, so that check stayed green while `_experiment_coordinator`
built an `AgentInferenceTrace` passing only 12 of them, writing NULL into
the other 13 columns for every steering call, forever. The union check
could not see this because a field the ExperimentCoordinator producer never
touched was still "covered" by an entirely different producer's row.

This file checks each construction site independently instead. A field
must be passed by THIS producer, not by some producer, unless the producer
is named on `_PRODUCER_OMISSION_ALLOWLIST` with the field explicitly
listed and a comment explaining why no honest value exists at that
producer's seam.

Like its predecessor, this reads source via `ast` rather than importing
and exercising the producers, so it needs no database and cannot be fooled
by a producer that constructs the trace conditionally at runtime but still
names every field in source.

A keyword is only coverage if it can carry a real value: `field=None`
written as a bare literal counts the same as never passing the keyword at
all, since it writes NULL unconditionally. A DERIVED expression that may
evaluate to `None` (a conditional, a call, an attribute lookup) still
counts, because that is honest population, not a placeholder.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.ports.inference_recorder import AgentInferenceTrace

from .conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.architecture

_TRACE_CLASS_NAME = "AgentInferenceTrace"

# `conversation_id` is deliberately absent from the dataclass itself (see
# `Inference`'s docstring in `cora.decision.aggregates.decision.entries`):
# every producer here makes single-shot calls, so no honest value exists.
# It carries no entry in `AgentInferenceTrace.__dataclass_fields__` at
# all, so it needs no coverage below; naming it here is documentation for
# a reader wondering why the by-value column doesn't appear in this file.

# Per-producer deliberate omissions. Keyed by "<qualified module>::<scope>"
# (the dotted class/function path `_ProducerVisitor` builds), mapped to the
# frozenset of declared fields that producer genuinely cannot fill.
# No entry may exist without a comment explaining WHY the omission is
# honest, right beside it: this dict is the whole point of that comment,
# so "did not get to it" is never a valid entry here.
_PRODUCER_OMISSION_ALLOWLIST: dict[str, frozenset[str]] = {}


def _dataclass_field_names() -> frozenset[str]:
    return frozenset(AgentInferenceTrace.__dataclass_fields__.keys())


def _qualified_module(path: Path) -> str:
    return "cora." + ".".join(path.relative_to(CORA_ROOT).with_suffix("").parts)


class _ProducerVisitor(ast.NodeVisitor):
    """Collects, per enclosing class/function scope, the keyword names
    passed to every `AgentInferenceTrace(...)` call in one module.

    Scope tracking is what lets a failure message name the actual
    construction site: two producers sharing a method name
    (`_record_inference` appears in both `RunDebrieferSubscriber` and
    `CautionDrafterSubscriber`) must not collapse into one entry just
    because the bare function name matches.
    """

    def __init__(self, module_qualname: str) -> None:
        self._module_qualname = module_qualname
        self._scope_stack: list[str] = []
        self.call_sites: dict[str, set[str]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == _TRACE_CLASS_NAME:
            scope = ".".join(self._scope_stack) if self._scope_stack else "<module>"
            producer_id = f"{self._module_qualname}::{scope}"
            keywords = self.call_sites.setdefault(producer_id, set())
            keywords.update(
                kw.arg
                for kw in node.keywords
                if kw.arg is not None and not _is_bare_none_literal(kw.value)
            )
        self.generic_visit(node)


def _is_bare_none_literal(value: ast.expr) -> bool:
    """True only for a literal `None`, never for an expression that merely
    CAN evaluate to `None`.

    A keyword passed as `field=None` writes NULL unconditionally, forever,
    the same hole this file exists to close: the guard must not let a
    producer claim coverage for a field it categorically never fills. A
    derived expression such as
    `tool_type="function" if call.tool_call_id is not None else None` is
    honest population (it depends on the call, not a constant), so only
    the bare-literal shape is excluded here; an `ast.IfExp`, a call, a
    name, or any other expression still counts as covered.
    """
    return isinstance(value, ast.Constant) and value.value is None


def _producer_call_sites() -> dict[str, frozenset[str]]:
    """Every `AgentInferenceTrace(...)` construction site in the tracked
    source tree, keyed by "<module>::<scope>" and mapped to the keyword
    argument names it passes.

    One entry per DISTINCT construction site, not one set unioned across
    the whole tree: that per-site view is exactly what the completeness
    check below needs and the historical guard lacked.
    """
    sites: dict[str, frozenset[str]] = {}
    for path in tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _ProducerVisitor(_qualified_module(path))
        visitor.visit(tree)
        for producer_id, keywords in visitor.call_sites.items():
            sites[producer_id] = frozenset(keywords)
    return sites


def test_every_agent_inference_trace_producer_passes_its_required_fields() -> None:
    declared = _dataclass_field_names()
    failures: list[str] = []
    for producer_id, keywords in sorted(_producer_call_sites().items()):
        allowed_omissions = _PRODUCER_OMISSION_ALLOWLIST.get(producer_id, frozenset())
        missing = (declared - allowed_omissions) - keywords
        if missing:
            failures.append(f"{producer_id}: {sorted(missing)}")
    assert not failures, (
        "These AgentInferenceTrace producers omit fields not named on their "
        "_PRODUCER_OMISSION_ALLOWLIST entry:\n  "
        + "\n  ".join(failures)
        + "\n\nEach omitted field will write NULL into its "
        "entries_decision_inferences column for every row THIS producer "
        'writes, forever. A NULL there reads as "no data for this call", '
        'not as "nothing ever writes this" -- indistinguishable from a '
        "real absence, which is exactly how duration/response_id/"
        "output_type/tool_name/tool_call_id/tool_type went unpopulated for "
        "six fields at once before anyone counted non-nulls. Either "
        "populate the field from this producer, or add it to "
        "_PRODUCER_OMISSION_ALLOWLIST with a comment naming why no honest "
        "value exists at this producer's seam."
    )


def test_producer_omission_allowlist_entries_still_omit_their_field() -> None:
    """Every allowlist entry MUST still name a real producer that still
    omits the listed field.

    Catches a stale entry left behind after a producer is widened to cover
    a field it used to skip, the same drift
    `test_deviation_allowlist_entries_still_deviate` guards against for the
    genesis-verb allowlist.
    """
    sites = _producer_call_sites()
    for producer_id, omitted in _PRODUCER_OMISSION_ALLOWLIST.items():
        assert producer_id in sites, (
            f"{producer_id!r} is allowlisted but no longer matches any "
            "AgentInferenceTrace(...) construction site; prune the entry."
        )
        overlap = omitted & sites[producer_id]
        assert not overlap, (
            f"{producer_id!r} now passes {sorted(overlap)}, which its "
            "allowlist entry still lists as omitted; prune those fields "
            "from the entry."
        )


def test_bare_none_keyword_does_not_count_as_coverage() -> None:
    """A `field=None` literal must not satisfy the completeness check.

    Parsed from a small fixture string, not a real producer file, so this
    stays meaningful even after every current producer is widened or
    rewritten. `duration` and `tool_name` are passed as bare `None`
    literals here and must be absent from the collected keywords;
    `tool_type`, passed as a conditional that can also evaluate to `None`,
    is honest derived population and must still be collected.
    """
    source = """
def _record_inference():
    trace = AgentInferenceTrace(
        decision_id=decision_id,
        duration=None,
        tool_name=None,
        tool_type="function" if call.tool_call_id is not None else None,
    )
"""
    visitor = _ProducerVisitor("cora.fixture")
    visitor.visit(ast.parse(source))
    ((_producer_id, keywords),) = visitor.call_sites.items()
    assert "decision_id" in keywords
    assert "tool_type" in keywords
    assert "duration" not in keywords
    assert "tool_name" not in keywords


def test_the_scan_finds_the_known_always_required_field() -> None:
    """Canary on the scanner itself, mirroring the disposition-table sibling.

    A scanner that silently matched nothing would make the test above pass
    vacuously. `decision_id` has no default and must be passed by every
    construction site, so it must appear at every discovered site. If this
    fails because the field was renamed, update the name here rather than
    deleting the test.
    """
    sites = _producer_call_sites()
    assert sites, "no AgentInferenceTrace(...) construction site found at all"
    for producer_id, keywords in sites.items():
        assert "decision_id" in keywords, f"{producer_id} never passes decision_id"


def test_the_scan_finds_the_field_the_historical_defect_was_named_for() -> None:
    """A second canary, tied to the actual bug rather than a generic field.

    `duration` is the field the originating investigation named
    (`entries_decision_inferences.duration`, 0 of 552 rows). Confirms the
    fix landed, not just that the scanner runs.
    """
    sites = _producer_call_sites()
    assert any("duration" in keywords for keywords in sites.values())
