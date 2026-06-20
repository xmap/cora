"""Every feature command/query handler MUST authorize before it runs.

The authz gate (`deps.authz.authorize(...)` -> Allow | Deny) is the
Layer-1 check in front of every operator command and query that enters
through a feature slice. Coverage is complete today but only by
convention: a new slice could load + append events without ever calling
authorize, and no other test would notice. This fitness test pins that
coverage so the gate cannot silently rot.

Scope: `<bc>/features/<slice>/handler.py` (Level 2) plus the make_*
handler factories they delegate to (Level 1). Reactive writers that are
deliberately NOT operator-command handlers (subscribers, agent runtimes,
the run supervisor, projection workers, `*_seed` / `_bootstrap`) write
under a system or agent principal and are out of scope here.

A handler is considered to authorize if EITHER:

  1. its module calls `.authorize(...)` directly (the bespoke handlers,
     including every `get_*` query and the multi-stream / longhand
     command handlers that re-implement the gate by hand); OR
  2. it delegates to a sanctioned authorizing factory (the single-stream
     commands via `make_*_update_handler` and the `list_*` queries via
     `make_list_query_handler`).

The sanctioned factories are discovered, not hardcoded: Level 1 below
verifies that every `make_*` factory in the factory files reaches an
`authorize` call (directly, or by delegating to a sibling factory),
computed as a fixpoint over the call graph. Level 2 then checks every
feature handler against that verified set.

This is the "separate test (planned)" referenced in
`test_handler_accepts_surface_id.py`: that test pins the `surface_id`
kwarg shape; this one pins that the kwarg is actually used to authorize.

Limitations (this is a coverage ratchet, not a proof; it catches the
common failure of a whole slice losing its authz, which the paired
mutation test exercises):

  - Per-module, not per-bind-path. Detection is an AST walk of the whole
    module, so a dead or legacy `.authorize` call could mask an ungated
    live path. It does NOT isolate the closure returned by `bind()`.
  - Call, not enforcement. It pins that authorize is CALLED, not that a
    `Deny` result is raised; a handler that authorizes then ignores the
    verdict would still pass.
  - Canonical names only. An aliased factory import (`... as mk`) or an
    authorize call bound to a local would not be recognized, so handlers
    must call authorize and the factories by their canonical names.

If a handler legitimately needs no authz (none do today), add it to
`_AUTHZ_EXEMPT_HANDLERS` with a one-line reason.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_BC_ROOT_HELPER_MARKER = "_handler.py"
_CROSS_BC_FACTORIES = (
    CORA_ROOT / "infrastructure" / "update_handler.py",
    CORA_ROOT / "infrastructure" / "list_query.py",
)

# Feature handler.py modules (qualified name) that intentionally do NOT
# authorize. Each entry MUST carry a one-line WHY. Empty today: every
# feature handler authorizes (verified by the enforcement audit
# 2026-06-20). An entry here is a deliberate, reviewed exception, not a
# place to silence a real gap.
_AUTHZ_EXEMPT_HANDLERS: dict[str, str] = {}


def _qualified(handler_file: Path) -> str:
    rel = handler_file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _slice_handler_files() -> list[Path]:
    """Every git-tracked `<bc>/features/<slice>/handler.py`."""
    out: list[Path] = []
    for path in sorted(tracked_python_files()):
        if not path.is_relative_to(CORA_ROOT):
            continue
        parts = path.relative_to(CORA_ROOT).parts
        if (
            len(parts) == 4
            and parts[0] in BCS
            and parts[1] == "features"
            and parts[3] == "handler.py"
        ):
            out.append(path)
    return out


def _factory_files() -> list[Path]:
    """The authorizing-factory definitions: BC-root `<bc>/_*_handler.py`
    wrappers plus the cross-BC `update_handler.py` / `list_query.py`.

    `idempotency.py` is deliberately excluded: it is an idempotency
    wrapper, not an authz factory; handlers that use it still call
    `authorize` themselves.
    """
    tracked = tracked_python_files()
    out: list[Path] = []
    for path in sorted(tracked):
        if not path.is_relative_to(CORA_ROOT):
            continue
        parts = path.relative_to(CORA_ROOT).parts
        if (
            len(parts) == 2
            and parts[0] in BCS
            and parts[1].startswith("_")
            and parts[1].endswith(_BC_ROOT_HELPER_MARKER)
        ):
            out.append(path)
    out.extend(f for f in _CROSS_BC_FACTORIES if f in tracked)
    return out


def _scan_calls(node: ast.AST) -> tuple[bool, set[str]]:
    """Walk `node`; return (calls_authorize, set_of_called_function_names).

    `calls_authorize` is True if any `....authorize(...)` call appears.
    Called-name set captures both `name(...)` (ast.Name) and
    `obj.name(...)` (ast.Attribute) forms so factory delegation is seen
    regardless of import style.
    """
    calls_authorize = False
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute):
            if func.attr == "authorize":
                calls_authorize = True
            names.add(func.attr)
        elif isinstance(func, ast.Name):
            names.add(func.id)
    return calls_authorize, names


def _scan_factories() -> tuple[set[str], set[str]]:
    """Parse the factory files; return (all_factory_fns, authorizers).

    A factory function is an `authorizer` if it calls `authorize`
    directly or (transitively) delegates to one that does. Computed as a
    fixpoint over the make_* call graph.
    """
    fn_calls: dict[str, set[str]] = {}
    fn_authorizes: dict[str, bool] = {}
    for path in _factory_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "make_"
            ):
                direct, names = _scan_calls(node)
                fn_authorizes[node.name] = direct
                fn_calls[node.name] = names
    all_fns = set(fn_calls)
    authorizers = {fn for fn, ok in fn_authorizes.items() if ok}
    changed = True
    while changed:
        changed = False
        for fn in all_fns - authorizers:
            if fn_calls[fn] & authorizers:
                authorizers.add(fn)
                changed = True
    return all_fns, authorizers


_ALL_FACTORY_FNS, _AUTHORIZING_FACTORIES = _scan_factories()


@pytest.mark.architecture
def test_authorizing_factories_all_reach_authorize() -> None:
    """Level 1: every make_* factory reaches an authorize call.

    A factory that neither calls authorize nor delegates to one that
    does would let every handler routed through it skip the gate.
    """
    assert "make_update_handler" in _AUTHORIZING_FACTORIES, (
        "Scan is broken: the root make_update_handler was not found to "
        "authorize. Check _factory_files() / _scan_factories()."
    )
    assert len(_ALL_FACTORY_FNS) >= 12, (
        f"Expected >=12 make_* factory functions (functions, not files: a "
        f"file may define several) across the factory files, found "
        f"{len(_ALL_FACTORY_FNS)}. Discovery may be wrong."
    )
    non_authorizing = sorted(_ALL_FACTORY_FNS - _AUTHORIZING_FACTORIES)
    assert not non_authorizing, (
        f"Factory functions that neither call deps.authz.authorize() nor "
        f"delegate to a factory that does: {non_authorizing}. Every "
        f"make_* handler factory must gate through the Authorize port."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("handler_file", _slice_handler_files(), ids=_qualified)
def test_feature_handler_authorizes(handler_file: Path) -> None:
    """Level 2: every feature handler authorizes directly or via a
    verified authorizing factory."""
    qualified = _qualified(handler_file)
    if qualified in _AUTHZ_EXEMPT_HANDLERS:
        pytest.skip(f"{qualified}: exempt ({_AUTHZ_EXEMPT_HANDLERS[qualified]})")

    tree = ast.parse(handler_file.read_text(), filename=str(handler_file))
    calls_authorize, called_names = _scan_calls(tree)
    if calls_authorize or (called_names & _AUTHORIZING_FACTORIES):
        return

    pytest.fail(
        f"{qualified} appears to run without authorizing: no "
        f"deps.authz.authorize(...) call and no delegation to a "
        f"sanctioned authorizing factory. Either call authorize before "
        f"loading/appending, delegate to one of the update/list-query "
        f"factories, or (if it genuinely needs no authz) add it to "
        f"_AUTHZ_EXEMPT_HANDLERS with a reason."
    )


@pytest.mark.architecture
def test_feature_handler_files_were_actually_discovered() -> None:
    """Drift catcher: a broken glob must fail loudly, not pass zero
    parametrized cases."""
    files = _slice_handler_files()
    assert len(files) >= 200, (
        f"Expected at least 200 feature handler files across the BCs, "
        f"found {len(files)}. The discovery glob may be wrong."
    )
