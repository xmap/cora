"""Architecture fitness functions for HTTP edge-auth invariants.

Four invariants surfaced at gate review that the import
graph + AST can prove WITHOUT running the test suite:

  1. `get_principal_id` is the SOLE reader of `X-Principal-Id`. No
     route / tool file outside `cora.infrastructure.routing` may
     declare a Header parameter with that alias. The centralized
     extraction ensures the three-mode priority (bearer →
     bearer-mode 401 → legacy) lands uniformly on every endpoint.

  2. Every concrete `TokenVerifier` implementor in
     `cora.infrastructure.auth` has the `verify` method whose
     signature matches the Protocol. Protocols are structural in
     Python; a typo in a future adapter's kwarg name (for example
     `expected_aud` instead of `expected_audience`) would NOT be
     caught at static-analysis time without this pin.

  3. `BearerAuthMiddleware` is added EXACTLY ONCE to the FastAPI
     app, AFTER `BodySizeLimitMiddleware`. The ordering matters:
     Starlette dispatches in add-order (first-added = outermost =
     runs first); BodySize-then-Bearer means a 100MB body gets
     rejected with 413 before any verifier work runs.

  4. Skip-path parity: the paths the contract tests assert as
     unauthenticated (/health, /metrics,
     /.well-known/oauth-protected-resource) match the centralized
     `_UNAUTHENTICATED_PATHS` + `_is_unauthenticated_path` in
     `bearer_auth_middleware.py`. A future "add /readiness skip" that
     updates only the test side without touching the middleware
     (or vice versa) fails this fitness. `/mcp/*` is no longer in
     the skip set — MCP routes are verified with audience-per-Surface
     dispatch; positive probes pin the inversion.

Gate-review trail: test-axis reviewer's 4 recommended fitness
tests; see edge-auth close-out memo for the discussion that led to
this file.
"""

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false

import ast
import inspect
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

# ---------- Invariant 1: X-Principal-Id sole-reader ----------


_ROUTING_MODULE_REL = Path("infrastructure/routing.py")
"""The single module where `Header(alias="X-Principal-Id")` is allowed.

`get_principal_id` reads X-Principal-Id via the standard FastAPI
`Header` machinery; any other route that re-declares the header
would bypass the bearer-mode silent-ignore rule, so this fitness
pins the centralization."""


def _slice_files() -> list[Path]:
    """Every BC's `features/*/route.py` and `features/*/tool.py`."""
    out: list[Path] = []
    for path in sorted(tracked_python_files()):
        if not path.is_relative_to(CORA_ROOT):
            continue
        rel = path.relative_to(CORA_ROOT)
        parts = rel.parts
        if len(parts) < 4:
            continue
        if parts[1] != "features":
            continue
        if parts[-1] not in ("route.py", "tool.py"):
            continue
        out.append(path)
    return out


def _ast_has_x_principal_id_header(tree: ast.AST) -> bool:
    """Walk the tree for a call like `Header(alias="X-Principal-Id")`."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match bare `Header(...)` or `fastapi.Header(...)`.
        func_name: str | None = None
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr
        if func_name != "Header":
            continue
        for kw in node.keywords:
            if kw.arg != "alias":
                continue
            if (
                isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
                and kw.value.value.lower() == "x-principal-id"
            ):
                return True
    return False


@pytest.mark.architecture
def test_x_principal_id_header_only_declared_in_infrastructure_routing() -> None:
    """No BC slice may re-declare a Header(alias='X-Principal-Id')
    parameter. The centralized `get_principal_id` in
    `cora.infrastructure.routing` is the single extraction point;
    a slice that declares its own X-Principal-Id header would
    bypass the bearer-mode silent-ignore rule
    and the bearer-mode 401 path (Mode 2).
    """
    offending: list[str] = []
    for path in _slice_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _ast_has_x_principal_id_header(tree):
            offending.append(str(path.relative_to(CORA_ROOT)))
    assert not offending, (
        "X-Principal-Id header MUST only be declared in "
        f"cora/{_ROUTING_MODULE_REL.as_posix()}. Re-declarations in slice "
        f"files bypass the bearer-mode three-mode priority. Offending: {offending}"
    )


# ---------- Invariant 2: TokenVerifier signature pin ----------


@pytest.mark.architecture
def test_every_concrete_token_verifier_matches_protocol_signature() -> None:
    """Every concrete class in `cora.infrastructure.auth` that exposes
    an async `verify` method MUST match the `TokenVerifier` Protocol
    signature exactly: `(self, token: str, *, expected_audience: UUID)
    -> VerifiedPrincipal`. Protocols are structural -- a typo in a
    future adapter's kwarg name (for example `expected_aud`) would still
    pass pyright but break at runtime when the middleware passes
    `expected_audience=...`.
    """
    from uuid import UUID

    from cora.infrastructure.adapters.introspection_token_verifier import IntrospectionTokenVerifier
    from cora.infrastructure.adapters.jwt_token_verifier import JwtTokenVerifier
    from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
    from cora.infrastructure.ports.token_verifier import TokenVerifier, VerifiedPrincipal

    # Enumerate every concrete TokenVerifier-conforming class shipped
    # today. Add new adapter classes here when they land; the next
    # change to this list is the prompt to re-check the Protocol.
    concrete_verifiers: list[type] = [
        JwtTokenVerifier,
        IntrospectionTokenVerifier,
        IdentityProviderRegistry,
    ]

    # The Protocol's `verify` is the source of truth for the expected
    # signature; we pin it programmatically rather than hard-code
    # `(self, token, *, expected_audience)` so the test follows the
    # Protocol if it evolves.
    protocol_sig = inspect.signature(TokenVerifier.verify)
    protocol_params = list(protocol_sig.parameters.values())
    # Drop `self` to align with concrete methods that bind it.
    protocol_params = [p for p in protocol_params if p.name != "self"]

    for cls in concrete_verifiers:
        method = cls.verify  # type: ignore[attr-defined]
        sig = inspect.signature(method)
        params = [p for p in sig.parameters.values() if p.name != "self"]

        assert len(params) == len(protocol_params), (
            f"{cls.__name__}.verify has {len(params)} params; "
            f"TokenVerifier.verify Protocol has {len(protocol_params)}. "
            f"Signatures: concrete={sig}, protocol={protocol_sig}"
        )
        for p_concrete, p_proto in zip(params, protocol_params, strict=True):
            assert p_concrete.name == p_proto.name, (
                f"{cls.__name__}.verify param {p_concrete.name!r} does not match "
                f"TokenVerifier.verify param {p_proto.name!r}. "
                f"Sigs: concrete={sig}, protocol={protocol_sig}"
            )
            assert p_concrete.kind == p_proto.kind, (
                f"{cls.__name__}.verify param {p_concrete.name!r} kind "
                f"{p_concrete.kind} does not match Protocol kind {p_proto.kind}. "
                "Most common cause: missing `*,` to mark the kwarg as "
                "keyword-only per the Protocol."
            )

        # Return annotation must be VerifiedPrincipal (sync-wise; the
        # method is `async def` so the runtime returns a Coroutine).
        assert sig.return_annotation in (VerifiedPrincipal, "VerifiedPrincipal"), (
            f"{cls.__name__}.verify return annotation is {sig.return_annotation!r}; "
            f"TokenVerifier.verify Protocol returns {VerifiedPrincipal.__name__}."
        )
        # `expected_audience` MUST be typed as UUID.
        audience_param = sig.parameters.get("expected_audience")
        assert audience_param is not None, (
            f"{cls.__name__}.verify is missing the `expected_audience` parameter."
        )
        assert audience_param.annotation in (UUID, "UUID"), (
            f"{cls.__name__}.verify expected_audience must be typed UUID, "
            f"got {audience_param.annotation!r}"
        )


# ---------- Invariant 3: BearerAuthMiddleware registered once + ordering ----------


@pytest.mark.architecture
def test_bearer_auth_middleware_registered_exactly_once_after_body_size_limit() -> None:
    """`BearerAuthMiddleware` MUST be added exactly once in
    `cora.api.main.create_app`, AFTER `BodySizeLimitMiddleware`.

    Order rationale (Starlette runs first-added = outermost = runs
    first): BodySize before Bearer means a 100MB body is rejected
    with 413 before any verifier work runs. Reversing the order
    would burn JWT verification cycles on bodies that will be
    rejected anyway.

    Duplicate registration would invoke the middleware twice per
    request (extra verifier latency, double-log on every auth
    failure). One-shot registration matches the edge-auth design.
    """
    main_py = CORA_ROOT / "api" / "main.py"
    src = main_py.read_text(encoding="utf-8")

    # `add_middleware(...)` can be either a one-liner or multi-line.
    # Scan for the middleware-class line that appears INSIDE an
    # add_middleware(...) call by parsing the AST.
    tree = ast.parse(src, filename=str(main_py))
    bearer_lines: list[int] = []
    body_size_lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match `app.add_middleware(...)` or bare `add_middleware(...)`.
        if isinstance(func, ast.Attribute):
            if func.attr != "add_middleware":
                continue
        elif isinstance(func, ast.Name):
            if func.id != "add_middleware":
                continue
        else:
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Name):
            if first_arg.id == "BearerAuthMiddleware":
                bearer_lines.append(node.lineno)
            elif first_arg.id == "BodySizeLimitMiddleware":
                body_size_lines.append(node.lineno)

    assert len(bearer_lines) == 1, (
        f"BearerAuthMiddleware must be registered exactly once in main.py; "
        f"found {len(bearer_lines)} call sites at lines {bearer_lines}."
    )
    assert len(body_size_lines) == 1, (
        f"BodySizeLimitMiddleware must be registered exactly once in main.py; "
        f"found {len(body_size_lines)} call sites at lines {body_size_lines}."
    )
    assert body_size_lines[0] < bearer_lines[0], (
        f"BodySizeLimitMiddleware (line {body_size_lines[0]}) must be added BEFORE "
        f"BearerAuthMiddleware (line {bearer_lines[0]}) so the size cap runs first. "
        "Starlette dispatches first-added = outermost = runs first inbound. "
        "Reversing burns JWT verify on bodies that will be 413-rejected."
    )


# ---------- Invariant 4: Skip-path parity ----------


# Source of truth: the path the contract tests assert as unauthenticated
# must appear in the middleware's skip list. Add to this set when a new
# unauthenticated path lands; both the middleware AND the test must update
# in sync (this fitness is the cross-check).
_EXPECTED_UNAUTHENTICATED_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/readyz",
        "/metrics",
        "/.well-known/oauth-protected-resource",
    }
)
_EXPECTED_UNAUTHENTICATED_PREFIXES: frozenset[str] = frozenset()
"""`/mcp/` is no longer in the skip prefix set. MCP routes
are verified with audience-per-Surface dispatch; the set is
empty today but stays as a typed frozenset so future skip-prefixes
can land here without changing the test shape."""


@pytest.mark.architecture
def test_bearer_middleware_skip_paths_match_canonical_set() -> None:
    """The middleware's `_UNAUTHENTICATED_PATHS` + `_is_unauthenticated_path`
    function MUST cover the exact set of paths the contract tier asserts
    as unauthenticated. A drift between the two sites (for example adding a new
    `/readiness` skip in the middleware but not exercising it in tests,
    or vice versa) is exactly the gap this fitness catches.

    Today's canonical set lives in `_EXPECTED_UNAUTHENTICATED_PATHS` /
    `_EXPECTED_UNAUTHENTICATED_PREFIXES` above. Both sides import from
    this fitness's frozensets ONLY conceptually -- the middleware has
    its own hardcoded list (intentional: avoid a test-imports-prod
    cycle), and the test cross-checks them.
    """
    from cora.infrastructure.auth.bearer_auth_middleware import (
        _UNAUTHENTICATED_PATHS,
        _is_unauthenticated_path,
    )

    # Exact-path parity: middleware's frozenset must equal expected.
    assert _UNAUTHENTICATED_PATHS == _EXPECTED_UNAUTHENTICATED_PATHS, (
        f"Middleware _UNAUTHENTICATED_PATHS drift detected: "
        f"middleware={_UNAUTHENTICATED_PATHS}, expected={_EXPECTED_UNAUTHENTICATED_PATHS}. "
        "Update both `bearer_auth_middleware.py:_UNAUTHENTICATED_PATHS` AND "
        "`test_edge_auth_invariants.py:_EXPECTED_UNAUTHENTICATED_PATHS` "
        "in the same commit so they stay in sync."
    )

    # Prefix-path parity: probe each expected prefix.
    for prefix in _EXPECTED_UNAUTHENTICATED_PREFIXES:
        probe = prefix + "anything"
        assert _is_unauthenticated_path(probe), (
            f"Expected prefix-skip {prefix!r} not honored by "
            f"_is_unauthenticated_path({probe!r}). Middleware prefix logic "
            "drifted from the expected set."
        )

    # Positive verification probes: MCP paths are NOT
    # skipped any more. They get bearer-verified with the MCP Surface
    # audience.
    assert not _is_unauthenticated_path("/mcp"), (
        "/mcp must be bearer-verified (not skipped). "
        "If a regression brings the skip back, MCP write tools silently "
        "bypass token verification."
    )
    assert not _is_unauthenticated_path("/mcp/anything"), (
        "/mcp/anything must be bearer-verified (not skipped). "
        "If a regression brings the prefix skip back, every MCP JSON-RPC "
        "call goes through unauthenticated."
    )

    # Negative: an unrelated /.well-known/ MUST NOT be skipped just
    # because it starts with /.well-known/.
    assert not _is_unauthenticated_path("/.well-known/openid-configuration"), (
        "/.well-known/openid-configuration must NOT be skipped; only the "
        "specific RFC 9728 protected-resource-metadata path is unauthenticated. "
        "Over-skipping /.well-known/ in general would expose any future "
        "well-known endpoint."
    )
