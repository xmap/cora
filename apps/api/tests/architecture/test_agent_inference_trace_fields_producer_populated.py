"""Every `AgentInferenceTrace` field is set by at least one producer.

The historical defect this guards against: a column can exist on the DTO,
carry all the way through the write path, exist in the live table, and
still be written by NOBODY, forever, because every producer construction
site simply never passes it as a keyword. `duration`, `response_id`,
`output_type`, and the three `tool_*` fields were all in this state
simultaneously (0 of 1163 rows populated on the 2-BM record for six of
them), invisible because a NULL column reads as "no data for this call"
rather than "nothing ever writes this."

A column that exists and is always NULL is a silent hole in the audit
trail this DTO exists to prevent. Filling one instance of it should have
prompted a sweep of the whole row; it did not, until something
specifically counted non-nulls. This test is the sweep, made permanent:
it reads every producer's source rather than running one, so it fails
the moment a NEW field is added to `AgentInferenceTrace` with no producer
ever passing it, before a single row is written.

Like its sibling drift tests, this reads source via `ast` rather than
importing and exercising the producers, so it needs no database and
cannot be fooled by a producer that constructs the trace conditionally
at runtime but still names every field in source.
"""

import ast

import pytest

from cora.infrastructure.ports.inference_recorder import AgentInferenceTrace

from .conftest import tracked_python_files

pytestmark = pytest.mark.architecture

_TRACE_CLASS_NAME = "AgentInferenceTrace"

# `conversation_id` is deliberately absent from the dataclass itself (see
# `Inference`'s docstring in `cora.decision.aggregates.decision.entries`):
# every producer here makes single-shot calls, so no honest value exists.
# It carries no entry in `AgentInferenceTrace.__dataclass_fields__` at
# all, so it needs no coverage below; naming it here is documentation for
# a reader wondering why the by-value column doesn't appear in this file.


def _dataclass_field_names() -> frozenset[str]:
    return frozenset(AgentInferenceTrace.__dataclass_fields__.keys())


def _keywords_passed_at_construction_sites() -> frozenset[str]:
    """Every keyword argument name passed to `AgentInferenceTrace(...)`,
    across every tracked source file. A field only needs to be set by ONE
    call site somewhere in the tree to satisfy the completeness check
    below; that is the actual invariant the historical bug violated
    (zero call sites, not merely a low count)."""
    covered: set[str] = set()
    for path in tracked_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == _TRACE_CLASS_NAME):
                continue
            covered.update(kw.arg for kw in node.keywords if kw.arg is not None)
    return frozenset(covered)


def test_every_agent_inference_trace_field_is_set_by_some_producer() -> None:
    declared = _dataclass_field_names()
    covered = _keywords_passed_at_construction_sites()

    unwritten = declared - covered
    assert not unwritten, (
        "These AgentInferenceTrace fields are never passed as a keyword by any "
        "construction site in the tracked source tree, so the corresponding "
        "table column would be written by nobody, forever, exactly like "
        "duration/response_id/output_type/tool_name/tool_call_id/tool_type were "
        f"before this test existed:\n  {sorted(unwritten)}\n"
        "Either populate the field from at least one producer, or if no value "
        "is ever honest (the conversation_id case), remove it from the "
        "dataclass and document the omission on Inference's docstring instead."
    )


def test_the_scan_finds_the_known_always_required_field() -> None:
    """Canary on the scanner itself, mirroring the disposition-table sibling.

    A scanner that silently matched nothing would make the test above pass
    forever. `decision_id` has no default and is passed by literally every
    construction site, so it must appear covered. If this fails because the
    field was renamed, update the name here rather than deleting the test.
    """
    covered = _keywords_passed_at_construction_sites()
    assert covered, "no AgentInferenceTrace(...) construction site found at all"
    assert "decision_id" in covered


def test_the_scan_finds_the_field_the_historical_defect_was_named_for() -> None:
    """A second canary, tied to the actual bug rather than a generic field.

    `duration` is the field the originating investigation named
    (`entries_decision_inferences.duration`, 0 of 552 rows). Confirms the
    fix landed, not just that the scanner runs.
    """
    assert "duration" in _keywords_passed_at_construction_sites()
