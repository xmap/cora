"""Pin: every seeded Agent appears in `SEEDED_FLEET`.

`cora.agent._seeded_fleet.SEEDED_FLEET` is a hand-written tuple, and a
hand-written tuple of seventeen ids is the exact shape that goes quietly
stale. It is what the operator promote-the-fleet gesture ranges over, so
an agent missing from it is an agent that silently never gets promoted,
and a stranded agent reports nothing at all.

The rule: for every `seed*.py` module under `cora/agent/` that declares
a `*_AGENT_ID` constant, that id MUST appear in `SEEDED_FLEET`. Scanned
with AST over git-tracked files rather than imported, so a half-added
module in flight stays invisible until it is staged (see the module
docstring in `conftest.py`).

The inverse direction is pinned too: an id in the tuple that no seed
module declares means the fleet carries a member nothing creates.
"""

import ast
from uuid import UUID

import pytest

from cora.agent._seeded_fleet import SEEDED_FLEET
from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_AGENT_ID_SUFFIX = "_AGENT_ID"


def _seeded_agent_ids_declared() -> dict[str, UUID]:
    """Every `*_AGENT_ID = UUID("...")` declared in an agent seed module."""
    declared: dict[str, UUID] = {}
    tracked = tracked_python_files()
    for path in sorted((CORA_ROOT / "agent").glob("seed*.py")):
        if path not in tracked:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if not target.id.endswith(_AGENT_ID_SUFFIX):
                    continue
                call = node.value
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                literal = call.args[0]
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                    declared[target.id] = UUID(literal.value)
    return declared


@pytest.mark.architecture
def test_every_seeded_agent_is_in_the_fleet() -> None:
    declared = _seeded_agent_ids_declared()
    assert declared, "no seeded agent ids found; the scan is broken, not the fleet"

    registered = {member.agent_id for member in SEEDED_FLEET}
    missing = {name: value for name, value in declared.items() if value not in registered}

    assert not missing, (
        "seed modules declare agent ids absent from SEEDED_FLEET:\n"
        + "\n".join(f"  {name} = {value}" for name, value in sorted(missing.items()))
        + "\n\nAdd them to cora/agent/_seeded_fleet.py. An agent missing from "
        "that tuple is skipped by the operator promote gesture and then sits "
        "unable to act without reporting anything."
    )


@pytest.mark.architecture
def test_every_fleet_member_is_declared_by_a_seed_module() -> None:
    declared = set(_seeded_agent_ids_declared().values())
    orphans = [member for member in SEEDED_FLEET if member.agent_id not in declared]

    assert not orphans, "SEEDED_FLEET carries members no seed module declares:\n" + "\n".join(
        f"  {member.name} = {member.agent_id}" for member in orphans
    )


@pytest.mark.architecture
def test_fleet_ids_and_names_are_unique() -> None:
    ids = [member.agent_id for member in SEEDED_FLEET]
    names = [member.name for member in SEEDED_FLEET]
    assert len(set(ids)) == len(ids), "two fleet members share an agent id"
    assert len(set(names)) == len(names), "two fleet members share a name"
