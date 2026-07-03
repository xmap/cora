"""No facility-state effect precedes its authorization check.

Companion to `test_handler_authorizes` (which proves every feature
handler CALLS + ENFORCES `authorize`). This test pins the stronger
ORDERING property that the call-existence check does not: in a handler
that authorizes directly, the `authorize(...)` call must come BEFORE the
first state-writing `event_store.append(...)` / `append_streams(...)`.
An authorize that runs after the append would have already let the effect
land.

This is the codified form of the paper's non-bypass invariant (E2): "no
facility-state effect occurs without a prior authorization." It is a
lightweight positional check over each `bind()` body, not a proof of
branch reachability; combined with `test_handler_authorizes` (existence +
enforcement) and the authorizing-factory fixpoint, it closes the ordering
gap those leave open.

Scope + method:

  - Only handlers that BOTH call `authorize` directly AND append directly
    in `bind()` are checked here: the ordering question only exists when
    both are in the same body. Handlers that delegate to a `make_*`
    authorizing factory are covered by that factory (it authorizes before
    it appends); handlers that only authorize (queries) have no append to
    order against.
  - Ordering uses the AST line number of the first `authorize` call vs the
    first `append` / `append_streams` call. Handlers in this codebase are
    straight-line load-authorize-decide-append bodies, so lineno ordering
    is faithful; a handler that guarded an append behind a branch before
    authorizing would still be caught (its append lineno precedes the
    authorize).

Reactive writers (subscribers, agent runtimes, the run supervisor, seeds,
bootstrap) are out of scope: they write under a system/agent principal
and are not operator-command handlers, exactly as in
`test_handler_authorizes`.
"""

# Reuses the sibling test's discovery helpers (same pattern as
# test_slice_test_coverage reusing test_slice_contract's).
# pyright: reportPrivateUsage=false

import ast

import pytest

from tests.architecture.conftest import CORA_ROOT
from tests.architecture.test_handler_authorizes import (
    _AUTHZ_EXEMPT_HANDLERS,
    _bind_node,
    _qualified,
    _slice_handler_files,
)

_APPEND_METHODS = frozenset({"append", "append_streams"})


def _first_lineno(node: ast.AST, *, predicate: object) -> int | None:
    """Lowest line number of a Call node satisfying `predicate`, or None.

    `predicate` is a callable `(ast.Call) -> bool`.
    """
    best: int | None = None
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and predicate(child):  # type: ignore[operator]
            line = child.lineno
            if best is None or line < best:
                best = line
    return best


def _is_authorize_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == "authorize"


def _is_append_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr in _APPEND_METHODS


@pytest.mark.architecture
@pytest.mark.parametrize("handler_file", _slice_handler_files(), ids=_qualified)
def test_authorize_precedes_state_effect(handler_file: object) -> None:
    """A handler that authorizes AND appends directly must authorize first."""
    from pathlib import Path

    path = handler_file if isinstance(handler_file, Path) else Path(str(handler_file))
    qualified = _qualified(path)
    if qualified in _AUTHZ_EXEMPT_HANDLERS:
        pytest.skip(f"{qualified}: exempt ({_AUTHZ_EXEMPT_HANDLERS[qualified]})")

    assert path.is_relative_to(CORA_ROOT)  # discovery invariant
    tree = ast.parse(path.read_text(), filename=str(path))
    bind = _bind_node(tree)
    if bind is None:
        pytest.skip(f"{qualified}: no bind() (covered by test_handler_authorizes)")

    authorize_line = _first_lineno(bind, predicate=_is_authorize_call)
    append_line = _first_lineno(bind, predicate=_is_append_call)

    if authorize_line is None or append_line is None:
        # No direct authorize+append pair in this body: the ordering
        # question does not arise here (delegating / query handlers are
        # covered by test_handler_authorizes + the factory fixpoint).
        return

    assert authorize_line < append_line, (
        f"{qualified}: a state-writing append (line {append_line}) precedes "
        f"the authorize() call (line {authorize_line}) in bind(). Facility "
        f"state must never be written before the authorization check "
        f"(non-bypass invariant). Move authorize above the append."
    )


@pytest.mark.architecture
def test_at_least_one_handler_exercises_the_ordering_check() -> None:
    """Drift catcher: the check is meaningful only if some handler actually
    has a direct authorize+append pair. If none do (discovery broke, or
    every handler moved to factories), this test would silently pass on an
    empty set."""
    checked = 0
    for path in _slice_handler_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        bind = _bind_node(tree)
        if bind is None:
            continue
        if _first_lineno(bind, predicate=_is_authorize_call) is not None and (
            _first_lineno(bind, predicate=_is_append_call) is not None
        ):
            checked += 1
    assert checked >= 10, (
        f"Expected >=10 feature handlers with a direct authorize+append pair "
        f"to exercise the ordering invariant, found {checked}. Discovery may "
        f"be broken."
    )
