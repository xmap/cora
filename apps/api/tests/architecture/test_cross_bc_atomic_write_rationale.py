"""Every cross-BC atomic co-write handler documents its broken-window rationale.

CORA's default cross-aggregate posture is eventual consistency (bare
UUID references, handler-load fan-out, decider re-validation on current
state). Atomic co-writes are the deliberate exception: a handler that
appends events to TWO different streams in ONE Postgres transaction via
`EventStore.append_streams`, reserved for cases where an observable
intermediate state would be a broken window an operator cannot tolerate
(shared-identity genesis, compensating supersede pairs, audit emission
paired with the domain event).

The pattern is mature and consistently applied; the risk it carries is
silent proliferation. A new author can reach for `append_streams`
without justifying WHY both-or-neither matters here, and a reviewer has
no machine-checked anchor to audit against. This fitness function turns
the `project-cross-bc-atomic-writes` memo's registry into a load-bearing
invariant:

  1. Every registered co-write handler's MODULE docstring must name the
     mechanism (`append_streams`) AND state the atomicity rationale
     (atomic / one transaction / all-or-nothing / rolls back). The
     "broken-window rationale in the handler module docstring" the memo
     asked for.
  2. Drift catcher: any feature `handler.py` that co-writes (calls
     `append_streams` with >=2 `StreamAppend` constructions) but is NOT
     in the registry fails loud. A new atomic seam cannot land without a
     deliberate registry entry + a documented rationale.

See `project_cross_bc_atomic_writes.md` for the canonical registry and
the when-to-reach-for-atomic guidance. The fitness test was deferred at
memo-authoring time until the 6th co-write site landed (rule-of-three);
there are 13 today.

## Detection heuristic

A co-write handler is detected as: a tracked feature `handler.py` that
(a) calls `.append_streams(...)` and (b) constructs >=2 `StreamAppend(...)`
objects. This matches today's idiom (every co-write builds its
`StreamAppend` literals inline). It would undercount a handler that
builds N appends in a loop from a single `StreamAppend(...)` literal; no
such site exists today, and the explicit registry is the source of truth
either way. Single-stream `append_streams` callers (one `StreamAppend`,
e.g. `forget_actor`, `dismiss_event_in_reaction`) are correctly excluded.

Seed / bootstrap modules (`_agent_seed.py`, `_clearance_template_seed.py`)
also call `append_streams` but are out of scope: they are idempotent
startup plumbing, not operator-facing request handlers, so "handler
module docstring" does not apply.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

# tests/architecture/<file>.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

# Feature handlers that co-write >=2 streams in one `append_streams`
# transaction. Paths relative to apps/api/. Mirrors the registry table in
# `project_cross_bc_atomic_writes.md`. Adding a new atomic co-write seam
# requires a deliberate entry here PLUS a documented rationale in the
# handler module docstring; the drift catcher below fails otherwise.
_COWRITE_HANDLERS: frozenset[str] = frozenset(
    {
        "src/cora/agent/features/define_agent/handler.py",
        "src/cora/agent/features/promote_caution_proposal/handler.py",
        "src/cora/calibration/features/publish_revision/handler.py",
        "src/cora/campaign/features/add_run_to_campaign/handler.py",
        "src/cora/campaign/features/remove_run_from_campaign/handler.py",
        "src/cora/caution/features/supersede_caution/handler.py",
        "src/cora/federation/features/define_permit/handler.py",
        "src/cora/federation/features/initialize_seal/handler.py",
        "src/cora/federation/features/register_credential/handler.py",
        "src/cora/federation/features/revoke_credential/handler.py",
        "src/cora/federation/features/rotate_seal_online_key/handler.py",
        "src/cora/run/features/start_run/handler.py",
        "src/cora/safety/features/amend_clearance/handler.py",
    }
)

# Case-insensitive substrings any one of which satisfies the "both-or-neither
# intent is documented" requirement. The docstring must ALSO mention
# `append_streams` so the prose is tied to the actual mechanism.
_RATIONALE_MARKERS: tuple[str, ...] = (
    "atomic",  # atomic / atomically
    "transaction",  # one / single Postgres transaction
    "all-or-nothing",
    "both-or-neither",
    "rolls back",
    "or not at all",
)


def _qualified(p: Path) -> str:
    return str(p.relative_to(_API_ROOT))


def _feature_handlers() -> list[Path]:
    """Tracked `src/cora/**/features/*/handler.py` files.

    Enumerates from git's tracked-file set rather than `rglob` so a
    half-staged slice does not false-fail under pre-commit (see the
    architecture conftest module docstring).
    """
    return sorted(
        p for p in tracked_python_files() if p.name == "handler.py" and "features" in p.parts
    )


def _calls_append_streams(tree: ast.AST) -> bool:
    """True if the module calls `<something>.append_streams(...)`."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append_streams"
        for node in ast.walk(tree)
    )


def _stream_append_count(tree: ast.AST) -> int:
    """Number of `StreamAppend(...)` construction call sites in the module."""
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "StreamAppend"
    )


def _is_cowrite(tree: ast.AST) -> bool:
    return _calls_append_streams(tree) and _stream_append_count(tree) >= 2


@pytest.mark.architecture
@pytest.mark.parametrize("relative", sorted(_COWRITE_HANDLERS))
def test_cowrite_handler_documents_atomic_rationale(relative: str) -> None:
    path = _API_ROOT / relative
    assert path.is_file(), (
        f"{relative} is registered as a cross-BC atomic co-write handler "
        f"but no longer exists. Prune _COWRITE_HANDLERS in "
        f"{Path(__file__).name}."
    )
    tree = ast.parse(path.read_text(), filename=str(path))

    # Drift: a registered handler that stopped co-writing is a stale entry.
    assert _is_cowrite(tree), (
        f"{relative} is registered as an atomic co-write handler but no "
        f"longer calls append_streams with >=2 StreamAppend constructions. "
        f"If the co-write was removed, prune _COWRITE_HANDLERS in "
        f"{Path(__file__).name}."
    )

    doc = (ast.get_docstring(tree) or "").lower()
    assert "append_streams" in doc, (
        f"{relative} co-writes two streams atomically but its MODULE "
        f"docstring does not mention `append_streams`. Document the "
        f"broken-window rationale: name the mechanism and explain why "
        f"both-or-neither matters here (see project_cross_bc_atomic_writes)."
    )
    assert any(marker in doc for marker in _RATIONALE_MARKERS), (
        f"{relative} mentions append_streams but its module docstring does "
        f"not state the atomicity rationale. Add why both writes must commit "
        f"together (e.g. 'atomic', 'one transaction', 'all-or-nothing', "
        f"'rolls back'). Markers checked: {list(_RATIONALE_MARKERS)}."
    )


@pytest.mark.architecture
def test_no_unregistered_cowrite_handlers() -> None:
    """Any feature handler that co-writes >=2 streams must be registered.

    Forces a new atomic seam to land deliberately: a registry entry plus a
    documented rationale (validated by the parametrized test above), rather
    than slipping in unaudited.
    """
    detected = {
        _qualified(p)
        for p in _feature_handlers()
        if _is_cowrite(ast.parse(p.read_text(), filename=str(p)))
    }
    unregistered = detected - _COWRITE_HANDLERS
    assert not unregistered, (
        f"Unregistered cross-BC atomic co-write handler(s): "
        f"{sorted(unregistered)}. A handler that appends to >=2 streams via "
        f"append_streams must be added to _COWRITE_HANDLERS in "
        f"{Path(__file__).name} and document its broken-window rationale in "
        f"its module docstring. If eventual consistency is in fact safe "
        f"here, use single-stream append instead. See "
        f"project_cross_bc_atomic_writes for the when-to-reach-for-atomic "
        f"guidance."
    )
