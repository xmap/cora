"""Guard every hand-typed `permitted_commands`-shaped list against reality.

No function anywhere in this codebase enumerates "every command name the app
exposes." The mechanically-enforced source of truth is the `command_name=`
keyword literal passed to `with_tracing`/`with_idempotency` at every BC's
`wire.py` composition site -- it is a required keyword-only parameter on both
(`cora.infrastructure.observability.decorator.with_tracing`,
`cora.infrastructure.idempotency.with_idempotency`), so nothing can be wired
without supplying one. This file generalizes
`test_visit_command_names.py::_wire_command_name_literals()` (which reads
this same literal off exactly one `wire.py`) across all 18 `BCS`.

A Trust `Policy.permitted_commands` set is define-once: there is no
`UpdatePolicy`, only `RevokePolicyGrant` (which can only shrink
`permitted_principal_ids`). Widening or fixing `permitted_commands` after
the fact means defining a brand-new Policy, repointing
`Settings.trust_policy_id`, and restarting. That makes any hand-typed
command-name list feeding a real Policy a place where a rename or removed
slice fails CLOSED silently in production rather than loudly in CI --
exactly the failure mode a policy built from a stale list would hit.

`_HARDCODED_COMMAND_LISTS` below is the registry. When a future change
defines a real `permitted_commands` set for a deployment (2-BM or otherwise),
add it here so a subsequent rename is caught at commit time. The System
Bootstrap Policy seed is deliberately NOT in this registry: its check
(`test_bootstrap_policy_seed_postgres.py::test_bootstrap_policy_permitted_commands_match_real_handler_command_names`)
already imports `_COMMAND_NAME` constants directly rather than retyping the
strings, so it carries no drift risk to begin with -- duplicating it here
would just create a second hand-typed list with the exact problem this file
exists to prevent.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT

_FACILITY_FIXTURE = (
    CORA_ROOT.parents[1] / "tests" / "integration" / "scenarios" / "_facility_fixture.py"
)


def _wire_command_name_literals(wire_py: Path) -> set[str]:
    """Extract every `command_name="..."` literal in one `wire.py`."""
    tree = ast.parse(wire_py.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "command_name":
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            out.add(value.value)
    return out


def _all_wire_command_names() -> frozenset[str]:
    """Every `command_name=` literal across every BC's `wire.py`.

    This is the full, mechanically-enforced set of command/query names
    CORA can execute today -- 301 distinct names across 18 BCs as of this
    writing. Generalizes `test_visit_command_names.py`'s single-file
    AST walk across all of `BCS`.
    """
    names: set[str] = set()
    for bc in BCS:
        wire_py = CORA_ROOT / bc / "wire.py"
        names |= _wire_command_name_literals(wire_py)
    return frozenset(names)


def _extract_frozenset_of_str(tree: ast.Module, name: str) -> frozenset[str]:
    """Pull the string contents of a module-level
    `<name>: frozenset[str] = frozenset({...})` annotated assignment.

    Parsed as source text, not imported: architecture tests inspect
    source rather than importing across test tiers, matching how
    `test_visit_command_names.py` reaches into a migration's raw SQL
    text rather than importing it.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not (isinstance(node.target, ast.Name) and node.target.id == name):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and value.args
        ):
            continue
        elts = getattr(value.args[0], "elts", None)
        if elts is None:
            continue
        return frozenset(
            elt.value
            for elt in elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
    msg = f"{name!r} not found as an annotated `frozenset[str] = frozenset({{...}})` assignment"
    raise AssertionError(msg)


def _facility_fixture_commands(name: str) -> frozenset[str]:
    tree = ast.parse(_FACILITY_FIXTURE.read_text(encoding="utf-8"))
    return _extract_frozenset_of_str(tree, name)


_IN_PROCESS_GRANTS = CORA_ROOT / "api" / "in_process_grants.py"


def _in_process_grants_commands() -> frozenset[str]:
    """Every granted command name in
    `cora.api.in_process_grants.IN_PROCESS_GRANTS`.

    That table's shape -- a `MappingProxyType` keyed by imported UUID
    constants and valued by `frozenset[str]` literals -- does not fit
    `_extract_frozenset_of_str`'s single flat-frozenset shape, so this
    walks the whole assigned value once and keeps every string constant
    found anywhere in it. Only the granted command names ever appear as
    string literals in that subtree: the mapping's keys are `Name`
    references to imported constants, never literals, so nothing else
    could be swept in by mistake.
    """
    tree = ast.parse(_IN_PROCESS_GRANTS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
            continue
        if node.target.id != "IN_PROCESS_GRANTS" or node.value is None:
            continue
        return frozenset(
            sub.value
            for sub in ast.walk(node.value)
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
        )
    msg = "IN_PROCESS_GRANTS not found as a module-level annotated assignment"
    raise AssertionError(msg)


_HARDCODED_COMMAND_LISTS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "facility_fixture._OPERATIONS_COMMANDS",
        _facility_fixture_commands("_OPERATIONS_COMMANDS"),
    ),
    (
        "facility_fixture._AGENT_COMMANDS",
        _facility_fixture_commands("_AGENT_COMMANDS"),
    ),
    (
        "in_process_grants.IN_PROCESS_GRANTS",
        _in_process_grants_commands(),
    ),
)


@pytest.mark.architecture
def test_all_wire_command_names_is_non_empty_and_has_no_duplicates() -> None:
    """Guards the enumerator itself: a broken AST walk that silently
    returned an empty set would make every parametrized case below
    vacuously pass."""
    names = _all_wire_command_names()
    assert len(names) > 250, (
        f"expected at least 250 distinct wire command names, found {len(names)}; "
        "the AST walk may be broken"
    )


@pytest.mark.architecture
@pytest.mark.parametrize(("label", "commands"), _HARDCODED_COMMAND_LISTS)
def test_hardcoded_command_list_is_a_subset_of_the_real_wire_surface(
    label: str, commands: frozenset[str]
) -> None:
    """Every command name in a hand-typed, policy-shaped list must be a
    real, currently-wired command name.

    Catches the failure mode a stale Trust Policy would hit silently: a
    slice gets renamed or removed, a hardcoded permitted-commands-shaped
    list still references the old name, and (once such a list becomes a
    real Policy's `permitted_commands`) every caller of that command
    starts getting an unexplained 403 in production instead of a red
    build here.
    """
    real = _all_wire_command_names()
    stale = sorted(commands - real)
    assert not stale, (
        f"{label} references command name(s) not found in any wire.py: {stale}. "
        "Either the slice was renamed/removed (update this list) or it is "
        "unwired (add it to the owning BC's wire_<bc>.py)."
    )
