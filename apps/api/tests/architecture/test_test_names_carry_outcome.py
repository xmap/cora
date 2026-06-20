"""Test function names must include an outcome clause, not just inputs.

CLAUDE.md hard rule: ``test_<subject>_<scenario>_<expectation>``. The
expectation segment is load-bearing: a name that stops at the input
("test_register_actor_with_empty_name") describes a scenario without
saying what's supposed to happen, which is the named anti-pattern in
Osherove's ``UnitOfWork_StateUnderTest_ExpectedBehavior`` rule and
in Khorikov's "a test states a fact" formulation.

The detection rule is two-element:

  1. Name contains a segment-bounded INPUT CONNECTOR
     (``_with_``, ``_when_``, ``_for_``, ``_on_``, ``_given_``,
     ``_using_``, ``_from_``, ``_after_``, ``_during_``, ``_if_``).
  2. Name contains ZERO outcome tokens across these six buckets:
     present-tense outcome verbs (``raises``, ``rejects``, ``rebuilds``,
     ``serializes``, ``fires``, ``dedups``, ``agrees``, ...), regular
     past participles (any ``_[a-z]{3,}ed`` suffix like ``_rejected``,
     ``_captured``, ``_mounted``), irregular past tenses (``built``,
     ``held``, ``kept``, ...), state predicates (``is_``, ``has_``,
     ``stays_``, ``remains_``), HTTP status codes (``_404``, ``_409``,
     ``_422``, ...), diagnostic prefixes (``iserror_``, ``noop``,
     ``noaction``), and comparative outcomes (``equals``, ``differs``,
     ``distinct``, ``independent``, ``unchanged``).

Names with no input connector at all are unconditionally allowed: the
convention permits subject + outcome with no scenario clause
(``test_forget_actor_scrubs_pii``).

``GRANDFATHERED_NAMES`` is the explicit work-tracker for legacy
violators surfaced when this fitness landed. Each entry is
``<relative-test-path>::<test_name>``. Drain to zero by renaming.
Entries should only be added when a new violator is grandfathered
ahead of its rename.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import tracked_test_files

if TYPE_CHECKING:
    from pathlib import Path


_INPUT_CONNECTOR = re.compile(r"_(with|when|for|on|given|using|from|after|during|if)_")

_OUTCOME_VERBS = (
    r"raises?|rejects?|fails?|errors?|blocks?|returns?|emits?|appends?|"
    r"yields?|records?|persists?|succeeds?|allows?|grants?|denies?|"
    r"creates?|updates?|deletes?|removes?|adds?|drops?|wraps?|skips?|"
    r"warns?|logs?|propagates?|surfaces?|preserves?|keeps?|stops?|"
    r"starts?|stays?|becomes?|enters?|leaves?|completes?|aborts?|"
    r"requires?|expects?|accepts?|conflicts?|treats?|uses?|sets?|"
    r"gets?|reads?|writes?|projects?|forbids?|prevents?|honors?|trims?|"
    r"truncates?|filters?|scopes?|defaults?|dedups?|chains?|clears?|"
    r"sees?|spans?|maps?|merges?|caches?|signs?|verifies?|publishes?|"
    r"consumes?|finalizes?|registers?|repeats?|builds?|wires?|loads?|"
    r"stores?|fetches?|lists?|enumerates?|paginates?|sorts?|orders?|"
    r"groups?|joins?|splits?|composes?|notifies?|opens?|closes?|locks?|"
    r"unlocks?|resolves?|exits?|handles?|works?|behaves?|holds?|"
    r"degrades?|advances?|transitions?|differs?|coexists?|carries?|"
    r"encodes?|decodes?|escapes?|rounds?|coerces?|casts?|reuses?|"
    r"inserts?|drains?|expires?|throttles?|retries?|debounces?|"
    r"batches?|streams?|prunes?|throws?|crashes?|panics?|hits?|"
    r"misses?|races?|deadlocks?|leaks?|frees?|allocates?|spawns?|"
    r"kills?|forks?|fires?|flags?|agrees?|forgets?|scrubs?|round_trips?|"
    r"short_circuits?|no_ops?|noops?|fans?_out|fans?_in|rolls?_back|"
    r"folds?|evolves?|seeds?|mounts?|dismounts?|debriefs?|drafts?|"
    r"promotes?|demotes?|deprecates?|supersedes?|abandons?|resumes?|"
    r"suspends?|revives?|revokes?|"
    r"rebuilds?|serializes?|deserializes?|upcasts?|prefers?|tolerates?|"
    r"omits?|embeds?|includes?|excludes?|captures?|derives?|passes?|"
    r"parses?|links?|versions?|lands?|compares?|constructs?|reflects?|"
    r"distinguishes?|mirrors?|wins?|contains?|asserts?|delegates?|"
    r"ignores?|declines?|pushes?|redacts?|validates?|picks?|chooses?|"
    r"awaits?|applies?|acknowledges?|ranks?|mints?|salts?|hashes?|"
    r"queries?|scans?|normalizes?|walks?|traces?|shapes?|invokes?|"
    r"gates?|dispatches?|relays?|forwards?|routes?|renders?|inflates?|"
    r"deflates?|materializes?|hydrates?|dehydrates?|checks?|controls?|"
    r"cancels?|extends?|narrows?|widens?|commits?|tags?|labels?|"
    r"annotates?|enriches?|adapts?|shrinks?|grows?|finds?|searches?|"
    r"locates?|computes?|deduces?|infers?|prompts?|signals?|reports?|"
    r"tracks?|measures?|samples?|polls?|drives?|orchestrates?|stamps?|"
    r"boots?|exists?|upserts?|falls?_back|falls?|reconstructs?|inherits?|"
    r"replaces?|advances?|hands?_back"
)

_OUTCOME_TOKEN = re.compile(rf"(?<![a-z])(?:{_OUTCOME_VERBS})(?![a-z])")

_STATE_PREDICATE = re.compile(
    r"(?<![a-z])(is|has|are|stays|remains|does_not|cannot|can|never|always|"
    r"only|still)_[a-z]"
)

_STATUS_CODE = re.compile(r"(?<![0-9])[1-5][0-9][0-9](?![0-9])")

_DIAG_TOKENS: frozenset[str] = frozenset(
    {"iserror", "noop", "no_op", "noaction", "no_action", "noerror", "no_caching"}
)

_COMPARATIVE = re.compile(
    r"(?<![a-z])(equals?|differs?|matches?|mismatches?|unchanged|"
    r"same_as|bigger_than|smaller_than|before|after_then|"
    r"distinct|independent|unique|redundant|disjoint|orthogonal)(?![a-z])"
)

_PAST_PARTICIPLE = re.compile(r"_[a-z]{3,}ed(?![a-z])")

_IRREGULAR_PAST = re.compile(
    r"(?<![a-z])(built|held|kept|forgot|lost|sent|caught|taught|brought|"
    r"thought|ran|swept|fed|led|met|set|shown|known|read|done|gone|"
    r"broken|hidden|chosen|written|drawn|frozen|stuck|spent|spun|"
    r"dropped|left|grown|torn|worn|paid|made|laid)(?![a-z])"
)


def _has_outcome(name: str) -> bool:
    if _OUTCOME_TOKEN.search(name):
        return True
    if _STATE_PREDICATE.search(name):
        return True
    if _STATUS_CODE.search(name):
        return True
    if _COMPARATIVE.search(name):
        return True
    if _PAST_PARTICIPLE.search(name):
        return True
    if _IRREGULAR_PAST.search(name):
        return True
    return any(tok in name for tok in _DIAG_TOKENS)


_CONNECTOR_PREFIXES = (
    "with_",
    "when_",
    "for_",
    "on_",
    "given_",
    "using_",
    "from_",
    "after_",
    "during_",
    "if_",
)


def _flagged(name: str) -> bool:
    if not name.startswith("test_"):
        return False
    if not _INPUT_CONNECTOR.search(name):
        return False
    # Diagnostic tokens (noop, iserror, no_caching, ...) are accepted anywhere,
    # including subject position (`test_no_op_when_X`).
    if any(tok in name for tok in _DIAG_TOKENS):
        return False
    parts = name.split("_", 2)
    if len(parts) < 3:
        return False
    # Default check: outcome anywhere AFTER the first subject token. The first
    # token (`register` in `test_register_actor_with_X`) is conventionally the
    # subject root, so a verb there names the function under test rather than
    # asserting a result.
    if _has_outcome("_" + parts[2]):
        return False
    # Carve-out: when the first token is itself an outcome verb and the input
    # connector IMMEDIATELY follows (`test_raises_on_X`), the first token IS
    # the outcome. The connector-after-noun case (`test_register_actor_with_X`)
    # is intentionally NOT covered: that shape is the canonical anti-pattern.
    return not (re.fullmatch(_OUTCOME_VERBS, parts[1]) and parts[2].startswith(_CONNECTOR_PREFIXES))


def _test_function_names(path: Path) -> list[tuple[int, str]]:
    # `tracked_test_files()` reads `git ls-files`, which still lists files
    # whose deletion is in the working tree but not yet staged. Skip those
    # gracefully so a pending delete doesn't crash the fitness.
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out.append((node.lineno, node.name))
    return out


# Entries are "<relative-path-from-apps/api>::<test_name>". Surfaced when this
# fitness landed; drain by renaming each test to include an outcome clause.
GRANDFATHERED_NAMES: frozenset[str] = frozenset(
    {
        "tests/contract/test_rate_decision_mcp_tool.py::test_mcp_rate_decision_with_comment",
        "tests/integration/scenarios/test_2bm_streaming_tomography.py::test_streaming_tomography_with_adjust_run",
        "tests/integration/test_acquisitions_against_softioc_postgres.py::test_conductor_runs_continuous_action_with_axis_sweep_against_softioc",
        "tests/unit/agent/test_revise_agent_budget_decider.py::test_clears_budget_when_both_caps_none",
        "tests/unit/caution/test_caution_events.py::test_deserialize_target_for_asset",
        "tests/unit/caution/test_caution_events.py::test_deserialize_target_for_procedure",
        "tests/unit/caution/test_caution_events.py::test_serialize_target_for_asset",
        "tests/unit/caution/test_caution_events.py::test_serialize_target_for_procedure",
        "tests/unit/caution/test_caution_evolver.py::test_fold_genesis_with_parent_id",
        "tests/unit/caution/test_caution_evolver.py::test_fold_genesis_with_procedure_target",
        "tests/unit/decision/test_decision_inferences.py::test_decision_reasoning_with_agent_fields",
        "tests/unit/decision/test_decision_inferences.py::test_decision_reasoning_with_tool_call_fields",
        "tests/unit/equipment/test_asset_events.py::test_event_type_name_for_port_events",
        "tests/unit/infrastructure/test_content_hash.py::test_canonical_body_bytes_for_empty_dict",
        "tests/unit/infrastructure/test_content_hash.py::test_canonical_body_bytes_for_none_value",
        "tests/unit/infrastructure/test_content_hash.py::test_canonical_body_bytes_stable_for_frozenset_of_dataclasses",
        "tests/unit/recipe/test_capability.py::test_capability_aggregate_with_full_declarative_contract",
        "tests/unit/safety/test_clearance_evolver.py::test_fold_genesis_with_optional_fields",
    }
)


def _flagged_test_files() -> list[Path]:
    return sorted(p for p in tracked_test_files() if p.suffix == ".py")


@pytest.mark.architecture
@pytest.mark.parametrize(
    "path",
    _flagged_test_files(),
    ids=lambda p: str(p),
)
def test_test_function_names_include_outcome_clause(path: Path) -> None:
    violations: list[str] = []
    rel = path.as_posix().rsplit("apps/api/", 1)[-1]
    for lineno, name in _test_function_names(path):
        if not _flagged(name):
            continue
        key = f"{rel}::{name}"
        if key in GRANDFATHERED_NAMES:
            continue
        violations.append(f"line {lineno}: {name}")
    assert not violations, (
        f"{rel} has test name(s) with an input clause but no outcome:\n  "
        + "\n  ".join(violations)
        + "\nPer CLAUDE.md, test names follow test_<subject>_<scenario>_<expectation>. "
        "Add an outcome verb, state predicate, status code, or comparative "
        "(see test_test_names_carry_outcome.py module docstring)."
    )


@pytest.mark.architecture
def test_grandfathered_names_still_flagged() -> None:
    """Allowlist entries must still match the input-only pattern.

    Once a test is renamed to include an outcome clause, its allowlist
    entry becomes dead weight. Re-running the heuristic here forces the
    entry to be removed alongside the rename.
    """
    for entry in GRANDFATHERED_NAMES:
        _, _, name = entry.partition("::")
        assert _flagged(name), (
            f"{entry}: name no longer matches the input-only pattern; "
            f"remove from GRANDFATHERED_NAMES (rename shipped)."
        )
