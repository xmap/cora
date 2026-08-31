"""Architecture fitness functions for surface_id + surface_kind contextvars.

`BearerAuthMiddleware` binds the resolved arrival Surface UUID and kind
to structlog contextvars at the start of every authenticated request
(see `cora.infrastructure.observability.surface_context`). The binding
is a parallel observability dimension to the domain-pass `surface_id`
that handlers carry as a function arg; both pull from the same
middleware-resolved value, but the contextvars carry it through every
log line emitted in the request without per-handler ceremony.

Three invariants the AST + filesystem can prove:

  1. `merge_contextvars` is present in the structlog processor chain
     configured by `configure_logging`. Without it, contextvars-bound
     `surface_id` / `surface_kind` would be silently stripped before
     the JSON renderer ran.

  2. `BearerAuthMiddleware.dispatch` calls `bind_surface_context` AND
     `clear_surface_context`. Paired calls = no contextvars leakage
     between requests reusing the same asyncio task. The
     `_dispatch_authenticated` helper is the post-bind body so the
     bind/clear pair lives only in `dispatch`.

  3. Every HTTP-reachable seeded Surface UUID has a kind mapping in
     `_SURFACE_KIND_BY_UUID`. A new Surface seeded without a kind
     entry is a deploy-time bug; this fitness pins the map shape so
     additions land in both places together.

A fourth invariant pins the local kind-string literals against the
authoritative `SurfaceKind` StrEnum: `cora.infrastructure` cannot
import `cora.trust.aggregates` (tach BC isolation), so the kind
strings are mirrored locally. The test cross-checks parity.
"""

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false

import ast

import pytest
import structlog
from structlog.contextvars import merge_contextvars

from cora.infrastructure.auth import bearer_auth_middleware
from cora.infrastructure.logging import configure_logging
from cora.infrastructure.observability.surface_context import (
    _SURFACE_KIND_BY_UUID,
    SURFACE_KIND_HTTP,
    SURFACE_KIND_MCP_STREAMABLE_HTTP,
)
from cora.infrastructure.routing import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_IN_PROCESS_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)
from cora.trust.aggregates.surface.surface_kind import SurfaceKind


@pytest.mark.architecture
def test_structlog_config_includes_contextvars_merge_processor() -> None:
    """`configure_logging` must include `merge_contextvars` in the structlog
    processor chain. Without it, `bind_contextvars(surface_id=..., surface_kind=...)`
    calls would have no observable effect on log output: the JSONRenderer
    only emits keys present on the event_dict, and merge_contextvars is
    what pulls the contextvar-bound keys onto the event_dict.

    Asserts presence rather than first-position to tolerate downstream
    processor reordering, but does require the processor to be there.
    """
    configure_logging()
    config = structlog.get_config()
    processors = config["processors"]
    assert merge_contextvars in processors, (
        "structlog processor chain is missing `merge_contextvars`. Without "
        "it, `bind_surface_context()` calls bind to contextvars but the "
        "values are silently dropped before the JSONRenderer runs. Both "
        "`shared_processors` (configured chain) and "
        "`ProcessorFormatter.foreign_pre_chain` (stdlib bridge) must include "
        "merge_contextvars so log lines from both paths carry surface_id / "
        "surface_kind."
    )


@pytest.mark.architecture
def test_bearer_middleware_dispatch_binds_and_clears_surface_context() -> None:
    """`BearerAuthMiddleware.dispatch` MUST call both `bind_surface_context`
    and `clear_surface_context`. Paired calls in a try/finally guarantee
    no contextvars leak across requests reusing the same asyncio task
    (BaseHTTPMiddleware quirk).

    AST-walks the `dispatch` method body for `Call` nodes whose func name
    is `bind_surface_context` / `clear_surface_context`. Both MUST be
    present; the helper `_dispatch_authenticated` is the post-bind body
    so the bind/clear pair lives only in `dispatch`.
    """
    source = bearer_auth_middleware.__file__
    assert source is not None
    with open(source, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=source)

    dispatch_node: ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != "BearerAuthMiddleware":
            continue
        for member in node.body:
            if isinstance(member, ast.AsyncFunctionDef) and member.name == "dispatch":
                dispatch_node = member
                break
    assert dispatch_node is not None, (
        "Could not locate BearerAuthMiddleware.dispatch in bearer_auth_middleware.py. "
        "The fitness function's AST locator drifted from the source."
    )

    called_names: set[str] = set()
    for node in ast.walk(dispatch_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in {"bind_surface_context", "clear_surface_context"}:
            called_names.add(name)

    assert "bind_surface_context" in called_names, (
        "BearerAuthMiddleware.dispatch is missing a `bind_surface_context(...)` "
        "call. After resolving the arrival Surface UUID, dispatch MUST bind "
        "surface_id + surface_kind to structlog contextvars so downstream "
        "log lines carry the observability dimension."
    )
    assert "clear_surface_context" in called_names, (
        "BearerAuthMiddleware.dispatch is missing a `clear_surface_context()` "
        "call. The bind MUST be paired with a clear in a `finally` block "
        "so contextvars do not leak across requests reusing the same "
        "asyncio task."
    )


@pytest.mark.architecture
def test_surface_kind_map_covers_all_http_reachable_seeded_surfaces() -> None:
    """`_SURFACE_KIND_BY_UUID` MUST map every HTTP-reachable seeded Surface
    UUID to a kind string. `SYSTEM_MCP_STDIO_SURFACE_ID` and
    `SYSTEM_IN_PROCESS_SURFACE_ID` are intentionally excluded: stdio is a
    subprocess transport, and internal is CORA's own in-process work,
    neither ever reachable via the HTTP middleware. A new HTTP-reachable
    Surface seeded without a kind entry would cause `surface_kind_for` to
    raise `UnknownSurfaceError` at request time; better to catch the gap
    at architecture-test time.
    """
    http_reachable_surfaces = {
        SYSTEM_HTTP_SURFACE_ID,
        SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    }
    for surface_id in http_reachable_surfaces:
        assert surface_id in _SURFACE_KIND_BY_UUID, (
            f"HTTP-reachable Surface {surface_id} is missing from "
            f"_SURFACE_KIND_BY_UUID. Add an entry mapping the UUID to "
            f"its kind string in cora/infrastructure/observability/"
            f"surface_context.py."
        )
    assert SYSTEM_MCP_STDIO_SURFACE_ID not in _SURFACE_KIND_BY_UUID, (
        "SYSTEM_MCP_STDIO_SURFACE_ID is in _SURFACE_KIND_BY_UUID; "
        "stdio MCP is a subprocess transport that never flows through "
        "the HTTP middleware. If stdio observability binding lands, it "
        "should bind at the FastMCP server entrypoint, not via the "
        "HTTP-middleware-bound map."
    )
    assert SYSTEM_IN_PROCESS_SURFACE_ID not in _SURFACE_KIND_BY_UUID, (
        "SYSTEM_IN_PROCESS_SURFACE_ID is in _SURFACE_KIND_BY_UUID; the "
        "internal Surface names CORA's own in-process work, which by "
        "definition never arrives over the HTTP middleware and so has "
        "no arrival kind to bind for observability."
    )


@pytest.mark.architecture
def test_local_kind_string_literals_match_surface_kind_enum_values() -> None:
    """The kind string literals in `cora.infrastructure.observability.surface_context`
    mirror the authoritative `SurfaceKind` StrEnum values. Tach forbids
    `cora.infrastructure` from importing `cora.trust.aggregates` (BC
    isolation), so the strings are duplicated locally. This fitness
    pins the duplicated literals against the enum so drift is caught
    at architecture-test time.
    """
    assert SurfaceKind.HTTP.value == SURFACE_KIND_HTTP, (
        f"SURFACE_KIND_HTTP={SURFACE_KIND_HTTP!r} drifted from "
        f"SurfaceKind.HTTP.value={SurfaceKind.HTTP.value!r}."
    )
    assert SurfaceKind.MCP_STREAMABLE_HTTP.value == SURFACE_KIND_MCP_STREAMABLE_HTTP, (
        f"SURFACE_KIND_MCP_STREAMABLE_HTTP={SURFACE_KIND_MCP_STREAMABLE_HTTP!r} drifted "
        f"from SurfaceKind.MCP_STREAMABLE_HTTP.value="
        f"{SurfaceKind.MCP_STREAMABLE_HTTP.value!r}."
    )
