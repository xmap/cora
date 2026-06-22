"""Pin the 13 Visit slice command-name strings against the design memo.

The design memo `project_visit_aggregate_design.md` AuthZ matrix lists
the command-name strings that production Policy grants must reference.
Renaming any of these on the wire side without updating the matrix is a
silent contract break: deployed policies stop matching and every
operator command starts returning 403.

Sibling to `test_wire_command_name_matches_handler.py` which catches
drift between the wire literal and the handler's `_COMMAND_NAME`. This
test catches drift between BOTH ends and the externally-documented
matrix.

Also asserts the Visit commands are NOT in the System Bootstrap Policy
seed. Per design memo lock: "Visit commands are NOT added to the
System Bootstrap Policy seed. The bootstrap seed stays at
`{DefinePolicy, RegisterActor}`."
"""

import ast

import pytest

from tests.architecture.conftest import CORA_ROOT

# 13 Visit command names locked by the AuthZ matrix (9
# lifecycle + 2 presence + 2 Surface-control).
_VISIT_COMMAND_NAMES: frozenset[str] = frozenset(
    {
        "RegisterVisit",
        "RecordVisitArrival",
        "StartVisit",
        "HoldVisit",
        "ResumeVisit",
        "CompleteVisit",
        "CancelVisit",
        "AbortVisit",
        "VoidVisit",
        # Presence
        "CheckInVisit",
        "CheckOutVisit",
        # Surface control
        "TakeControlOfSurface",
        "ReleaseControlOfSurface",
    }
)

_TRUST_WIRE = CORA_ROOT / "trust" / "wire.py"
# CORA_ROOT is apps/api/src/cora, so repo root is four levels up.
_BOOTSTRAP_SEED = (
    CORA_ROOT.parents[3]
    / "infra"
    / "atlas"
    / "migrations"
    / "20260519000000_seed_bootstrap_policy.sql"
)


def _wire_command_name_literals() -> set[str]:
    """Extract every `command_name="..."` literal in trust/wire.py."""
    tree = ast.parse(_TRUST_WIRE.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "command_name":
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            out.add(value.value)
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("expected", sorted(_VISIT_COMMAND_NAMES))
def test_visit_command_name_is_wired_under_locked_string(expected: str) -> None:
    """Each AuthZ-matrix string appears in trust/wire.py.

    Catches the case where a slice gets renamed (e.g. `RegisterVisit`
    becomes `CreateVisit`) without the design memo + deployed Policies
    being updated in lockstep.
    """
    literals = _wire_command_name_literals()
    assert expected in literals, (
        f"Visit command name {expected!r} not found in trust/wire.py. "
        "Either the slice was renamed (update the AuthZ matrix in "
        "project_visit_aggregate_design.md and deployed Policies) or the "
        "slice is unwired (add to wire_trust)."
    )


@pytest.mark.architecture
def test_bootstrap_seed_excludes_visit_commands() -> None:
    """Visit commands MUST NOT be in the System Bootstrap Policy seed.

    Per design memo Locks: bootstrap seed stays at
    `{DefinePolicy, RegisterActor}`. First real admin Policy grants
    Visit commands post-bootstrap.

    The seed migration file is checked as source text rather than
    parsed: the seed is a SQL INSERT with a literal jsonb payload.
    Plain substring search catches any future drift where someone
    appends a Visit command to the seed's permitted_commands list.
    """
    if not _BOOTSTRAP_SEED.exists():
        pytest.skip(f"Bootstrap seed migration missing: {_BOOTSTRAP_SEED}")
    seed_text = _BOOTSTRAP_SEED.read_text(encoding="utf-8")
    leaked = sorted(name for name in _VISIT_COMMAND_NAMES if name in seed_text)
    assert not leaked, (
        f"Visit commands leaked into bootstrap seed: {leaked}. "
        "Per project_visit_aggregate_design.md Locks, bootstrap stays at "
        "{DefinePolicy, RegisterActor}; first real admin Policy grants "
        "Visit commands post-bootstrap."
    )
