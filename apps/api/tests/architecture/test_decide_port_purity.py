"""G2: the DecidePort seam stays optimizer- AND action-neutral.

The brain behind `DecidePort` may be a static grid walker, a Bayesian
optimizer, or an LLM; CORA must not be able to tell which. Two lexicons
therefore may never appear as a token in any `decide_port.py` surface
identifier: a class name, a DTO field name, a Protocol method name, a helper
function name, or a module-level alias.

  - OPTIMIZER internals (kernel, acquisition, surrogate, GP posterior,
    lengthscale, ...): leaking one would bind the seam to a single
    optimizer's shape and break grid / GP / LLM substitutability.
  - CONTROL / CONDUCTOR specifics (scan, acquire, motor, pv, the captures
    bus, a setpoint, a step): leaking one would close the compute-steering
    door and couple the seam to a single actuation path.

Matching is by stem PREFIX over each lowercase token, so morphological
variants are caught too: `captures` / `setpoints` / `steps` / `scanned` /
`acquired` / `motors` / `pvs` / `kernels` all trip their singular stem.

The point-to-captures translation is the CALLER's job; `point_to_captures`
must never be a `DecidePort` member (the `capture` stem enforces it).
Coordinate vocabulary (`point`, `next_point`) is neutral and allowed: it
names WHERE, not HOW to actuate.
"""

import ast
import re

import pytest

from tests.architecture.conftest import CORA_ROOT

_DECIDE_PORT = CORA_ROOT / "operation" / "ports" / "decide_port.py"

# Singular stems; matched by token-prefix so plurals / participles are caught.
_OPTIMIZER_STEMS = frozenset(
    {
        "kernel",
        "acquisition",
        "prior",
        "exploration",
        "hyperparam",
        "lengthscale",
        "gp",
        "surrogate",
        "posterior",
    }
)
_ACTION_STEMS = frozenset(
    {
        "scan",
        "acquire",
        "move",
        "write",
        "submit",
        "actuate",
        "trigger",
        "motor",
        "pv",
        "capture",
        "setpoint",
        "step",
    }
)
_BANNED_STEMS = _OPTIMIZER_STEMS | _ACTION_STEMS


def _tokens(name: str) -> set[str]:
    """Split a snake_case / camelCase identifier into lowercase tokens."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return {token for token in s2.lower().split("_") if token}


def _banned_hits(name: str) -> set[str]:
    """Stems a name's tokens trip, by prefix (so `captures` trips `capture`)."""
    return {stem for token in _tokens(name) for stem in _BANNED_STEMS if token.startswith(stem)}


def _surface_names(tree: ast.AST) -> list[str]:
    """Every surface identifier: class names, class-level annotated fields,
    function / method names, and module-level assignment targets."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    names.append(item.target.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.append(node.name)
    for item in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            names.append(item.target.id)
        elif isinstance(item, ast.Assign):
            names.extend(t.id for t in item.targets if isinstance(t, ast.Name))
    return names


@pytest.mark.architecture
def test_decide_port_surface_is_optimizer_and_action_neutral() -> None:
    """No DecidePort surface identifier carries a banned optimizer/action stem."""
    tree = ast.parse(_DECIDE_PORT.read_text())
    offenders = {
        name: sorted(_banned_hits(name)) for name in _surface_names(tree) if _banned_hits(name)
    }
    assert not offenders, (
        "decide_port.py exposes optimizer- or action-specific tokens on its seam:\n  "
        + "\n  ".join(f"{name}: {bad}" for name, bad in sorted(offenders.items()))
        + "\n\nThe DecidePort seam must stay optimizer- AND action-neutral so a grid, a "
        "GP, or an LLM are all substitutable behind it and the compute-steering door "
        "stays open. Move optimizer internals into the adapter and control specifics "
        "into the caller's point translation; keep the port to coordinate vocabulary."
    )


@pytest.mark.architecture
def test_decide_port_has_no_captures_translation_member() -> None:
    """`point_to_captures` is the caller's job, never a DecidePort member."""
    tree = ast.parse(_DECIDE_PORT.read_text())
    assert "point_to_captures" not in _surface_names(tree), (
        "decide_port.py declares a `point_to_captures` member. Translating a "
        "next_point into the conductor's captures bus is the CALLER's job; the seam "
        "carries only coordinates keyed by axis name, never the actuation path."
    )
