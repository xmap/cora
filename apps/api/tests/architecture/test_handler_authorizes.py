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

  1. its `bind()` calls `.authorize(...)` directly AND enforces the
     verdict (the bespoke handlers: an `isinstance(decision, Deny)`
     check followed by a `raise`, covering every `get_*` query and the
     multi-stream / longhand command handlers); OR
  2. its `bind()` delegates to a sanctioned authorizing factory (the
     single-stream commands via `make_*_update_handler` and the `list_*`
     queries via `make_list_query_handler`).

The sanctioned factories are discovered, not hardcoded: Level 1 below
verifies that every `make_*` factory in the factory files reaches an
`authorize` call (directly, or by delegating to a sibling factory),
computed as a fixpoint over the call graph, and that every direct
authorizer enforces the verdict. Level 2 then checks every feature
handler against that verified set.

This is the "separate test (planned)" referenced in
`test_handler_accepts_surface_id.py`: that test pins the `surface_id`
kwarg shape; this one pins that the kwarg is actually used to authorize.

Limitations (this is a coverage ratchet, not a proof; it catches the
common failure of a whole slice losing its authz, which the paired
mutation test exercises):

  - Scans the `bind()` subtree, not full reachability. It excludes
    module-level sibling functions (so a dead or legacy `.authorize` in
    a separate helper no longer masks an ungated path), but it does not
    prove the authorize sits on the live branch within `bind()`.
  - Enforcement is heuristic. A direct-authorize handler must also
    `raise` and reference `Deny` inside `bind()` (the
    `isinstance(decision, Deny)` -> `raise` shape), so a forgotten
    verdict check is caught; it does not prove the `raise` is wired to
    that specific `authorize` result.
  - Canonical names only. An aliased factory import (`... as mk`) or an
    authorize call bound to a local would not be recognized, so handlers
    must call authorize and the factories by their canonical names.

If a handler legitimately needs no authz (none do today), add it to
`_AUTHZ_EXEMPT_HANDLERS` with a one-line reason.
"""

import ast
from pathlib import Path
from typing import NamedTuple

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


class _Scan(NamedTuple):
    """What an AST subtree reveals about authorization."""

    calls_authorize: bool
    called_names: frozenset[str]
    has_raise: bool
    refs_deny: bool

    @property
    def enforces(self) -> bool:
        """A direct authorizer enforces the verdict if it both references
        `Deny` (the `isinstance(decision, Deny)` check) and `raise`s."""
        return self.calls_authorize and self.has_raise and self.refs_deny


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

    `idempotency.py` is not collected: it defines no `make_*` factory and
    is not under a BC, so it can never match; idempotent handlers still
    call `authorize` themselves.
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


def _feature_bearing_packages() -> set[str]:
    """Every `src/cora/<pkg>` (regardless of BCS membership) that has a
    `features/` tree, derived from tracked files. Used to catch a new BC
    that grew handlers but was never added to conftest.BCS."""
    pkgs: set[str] = set()
    for path in tracked_python_files():
        if not path.is_relative_to(CORA_ROOT):
            continue
        parts = path.relative_to(CORA_ROOT).parts
        if len(parts) >= 3 and parts[1] == "features":
            pkgs.add(parts[0])
    return pkgs


def _scan(node: ast.AST) -> _Scan:
    """Walk `node` and summarize its authorization-relevant shape.

    `calls_authorize` is True if any `....authorize(...)` call appears.
    Called-name set captures both `name(...)` (ast.Name) and
    `obj.name(...)` (ast.Attribute) forms so factory delegation is seen
    regardless of import style. `has_raise` / `refs_deny` back the
    verdict-enforcement check.
    """
    calls_authorize = False
    names: set[str] = set()
    has_raise = False
    refs_deny = False
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                if func.attr == "authorize":
                    calls_authorize = True
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
        elif isinstance(child, ast.Raise):
            has_raise = True
        elif isinstance(child, ast.Name) and child.id == "Deny":
            refs_deny = True
    return _Scan(calls_authorize, frozenset(names), has_raise, refs_deny)


def _bind_node(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The top-level `def bind(...)` of a slice handler, or None."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "bind":
            return node
    return None


def _scan_factories() -> tuple[set[str], set[str], set[str]]:
    """Parse the factory files; return (all_fns, authorizers, non_enforcing).

    A factory is an `authorizer` if it calls `authorize` directly or
    (transitively) delegates to one that does (fixpoint over the make_*
    call graph). `non_enforcing` are the direct authorizers that call
    authorize but do not raise on `Deny`.
    """
    fn_scan: dict[str, _Scan] = {}
    for path in _factory_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
                "make_"
            ):
                fn_scan[node.name] = _scan(node)
    all_fns = set(fn_scan)
    authorizers = {fn for fn, s in fn_scan.items() if s.calls_authorize}
    non_enforcing = {fn for fn in authorizers if not fn_scan[fn].enforces}
    changed = True
    while changed:
        changed = False
        for fn in all_fns - authorizers:
            if fn_scan[fn].called_names & authorizers:
                authorizers.add(fn)
                changed = True
    return all_fns, authorizers, non_enforcing


_ALL_FACTORY_FNS, _AUTHORIZING_FACTORIES, _NON_ENFORCING_FACTORIES = _scan_factories()


@pytest.mark.architecture
def test_authorizing_factories_all_reach_authorize() -> None:
    """Level 1: every make_* factory reaches an authorize call, and every
    direct authorizer enforces the verdict.

    A factory that neither calls authorize nor delegates to one that does
    would let every handler routed through it skip the gate; a direct
    authorizer that never raises on Deny would call the gate and ignore
    it."""
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
    assert not _NON_ENFORCING_FACTORIES, (
        f"Factory functions that call authorize but do not raise on Deny "
        f"(no isinstance(..., Deny) -> raise): {sorted(_NON_ENFORCING_FACTORIES)}. "
        f"Calling the gate without enforcing the verdict is not a gate."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("handler_file", _slice_handler_files(), ids=_qualified)
def test_feature_handler_authorizes(handler_file: Path) -> None:
    """Level 2: every feature handler authorizes (and enforces) inside
    `bind()`, directly or via a verified authorizing factory."""
    qualified = _qualified(handler_file)
    if qualified in _AUTHZ_EXEMPT_HANDLERS:
        pytest.skip(f"{qualified}: exempt ({_AUTHZ_EXEMPT_HANDLERS[qualified]})")

    tree = ast.parse(handler_file.read_text(), filename=str(handler_file))
    bind = _bind_node(tree)
    assert bind is not None, (
        f"{qualified}: no top-level `def bind(...)` found. The authz scan "
        f"keys on bind(); a handler with a different shape needs the scan "
        f"(or this assumption) revisited."
    )

    scan = _scan(bind)
    if scan.called_names & _AUTHORIZING_FACTORIES:
        return  # delegates to a verified authorizing factory
    if scan.calls_authorize:
        assert scan.enforces, (
            f"{qualified} calls authorize in bind() but does not appear to "
            f"enforce the verdict: expected an `isinstance(decision, Deny)` "
            f"check and a `raise`. Calling the gate without raising on Deny "
            f"is not a gate."
        )
        return

    pytest.fail(
        f"{qualified} appears to run without authorizing: bind() has no "
        f"deps.authz.authorize(...) call and no delegation to a sanctioned "
        f"authorizing factory. Either call authorize (and raise on Deny) "
        f"before loading/appending, delegate to one of the update/list-query "
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


@pytest.mark.architecture
def test_bcs_covers_all_feature_bearing_packages() -> None:
    """Every package under src/cora with a features/ tree must be listed
    in conftest.BCS. Otherwise a new BC's handlers silently drop out of
    Level 2 enumeration (parts[0] in BCS) without tripping the >=200
    floor."""
    missing = sorted(_feature_bearing_packages() - set(BCS))
    assert not missing, (
        f"Packages with a features/ tree that are NOT in conftest.BCS: "
        f"{missing}. Add them to BCS so their handlers are checked for "
        f"authz coverage (and surface_id, etc.)."
    )
