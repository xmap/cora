"""HTTP middleware that verifies `Authorization: Bearer` tokens.

Sits between the inbound HTTP request and route dispatch. On every
request it:

  1. Skips paths that MUST be unauthenticated (health, metrics,
     RFC 9728 protected-resource metadata). These exist so external
     monitoring + OAuth clients can probe the deployment without
     credentials.
  2. Skips when no `TokenVerifier` is configured on the kernel
     (today's default: legacy `X-Principal-Id`-with-`SYSTEM`-fallback
     stays in effect — see `cora.infrastructure.routing.get_principal_id`).
  3. Skips when no `Authorization` header is present. The route-layer
     `get_principal_id` Depends decides whether to 401 based on
     `Settings.require_authenticated_principal`; the middleware does
     NOT impose its own policy.
  4. Parses the `Authorization` header for `Bearer <token>`; mangled
     shapes raise `InvalidTokenError("malformed", ...)`.
  5. Resolves the arrival Surface UUID (today: the single SYSTEM HTTP
     Surface; future: per-app-state lookup if multiple HTTP Surfaces
     ever ship) and calls
     `verifier.verify(token, expected_audience=surface_id)`.
  6. Stores the resulting `VerifiedPrincipal` on `request.state.principal`
     so the route-layer `get_principal_id` can read it without another
     verification call.

`InvalidTokenError` + `IntrospectionUnavailableError` propagate out of
the middleware and are converted to HTTP responses by the BC-style
exception handlers registered at app construction (see
`register_auth_exception_handlers(app)`).

## Why BaseHTTPMiddleware over raw ASGI

`BodySizeLimitMiddleware` uses raw ASGI because it must short-circuit
before any body is read — the receive() must NOT be called. Bearer
auth has no such constraint; it just needs the request scope. Using
Starlette's `BaseHTTPMiddleware` lets exceptions propagate cleanly
through FastAPI's registered exception handlers (the BC convention)
instead of constructing JSON responses inline.

## Why the path-skip list lives here, not in the route layer

Routes that need to be unauthenticated (health, metrics, .well-known)
don't have a single FastAPI-layer marker today (no `@unauthenticated`
decorator). Centralising the list here keeps the auth boundary
explicit and grep-able: one file lists every unauthenticated path.
If the project later adds a per-route marker, this list collapses to
"check the marker on the matched route" without touching this file's
shape.

## MCP path coverage

`/mcp/...` and `/mcp` (exact) are verified here just like REST routes.
The middleware dispatches `expected_audience` per-path: MCP paths
bind to `SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID`, other paths bind to
`SYSTEM_HTTP_SURFACE_ID`. Tool handlers read the verified principal
via `cora.api.mcp_principal.get_mcp_principal_id(ctx)`, which pulls
`ctx.request_context.request.state.principal` — the same Starlette
Request object this middleware stashed on.

MCP_STDIO is NOT covered: stdio MCP servers inherit local OS identity
per spec; bearer-token shape doesn't fit a subprocess transport.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from cora.infrastructure.auth._routed_path import _routed_path
from cora.infrastructure.logging import get_logger
from cora.infrastructure.observability.surface_context import (
    bind_surface_context,
    clear_surface_context,
    surface_kind_for,
)
from cora.infrastructure.routing import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)

if TYPE_CHECKING:
    from cora.infrastructure.ports import TokenVerifier
# `InvalidTokenError` is RAISED at runtime so it can't be
# TYPE_CHECKING-gated; it's imported lazily inside the helper that
# raises it. The runtime path: middleware -> auth/__init__ ->
# bearer_auth_middleware -> ports/__init__ -> port modules -> routing ->
# observability -> config (Settings) -> auth.config -> back into
# `cora.infrastructure.auth` which is mid-load. Pinning the
# `InvalidTokenError` import inside `_extract_bearer_token` breaks
# the cycle at module-init time without sacrificing the typed-error
# contract.

_log = get_logger(__name__)

# Paths the middleware MUST never authenticate. Health, readiness and
# metrics are unauthenticated by deployment convention (k8s probes,
# Prometheus scrape): a probe that has to hold a token is a probe that
# reports an expired token as a dead process.
# `/.well-known/oauth-protected-resource` (RFC 9728) is
# unauthenticated by spec: clients discover where to get a token.
_UNAUTHENTICATED_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/readyz",
        "/metrics",
        "/.well-known/oauth-protected-resource",
    }
)


def _is_unauthenticated_path(path: str) -> bool:
    """Return True if `path` MUST be skipped by the bearer middleware.

    Exact-match against the four unauthenticated paths only. MCP
    routes are verified with audience-per-Surface binding (see
    `_resolve_expected_audience`).
    """
    return path in _UNAUTHENTICATED_PATHS


def _resolve_expected_audience(path: str) -> UUID:
    """Return the Surface UUID the bearer token's `aud` MUST match.

    Per-path dispatch: MCP routes bind to the
    `SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID` audience; everything else
    binds to `SYSTEM_HTTP_SURFACE_ID`. A token issued for HTTP MUST
    NOT verify against the MCP Surface and vice versa (no shared
    `aud` across Surfaces).

    MCP_STDIO is NOT routed here (stdio is a subprocess transport,
    never reachable over HTTP).
    """
    if path == "/mcp" or path.startswith("/mcp/"):
        return SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID
    return SYSTEM_HTTP_SURFACE_ID


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Verify `Authorization: Bearer <token>` against the kernel TokenVerifier.

    Stateless: every request reads `kernel.token_verifier` off
    `request.app.state.deps`. The verifier is process-singleton built
    once at lifespan start; the middleware just dispatches.

    When `kernel.token_verifier is None` (no IdPs configured) the
    middleware no-ops and the legacy `X-Principal-Id` path takes over.
    This is the "edge-auth disabled" mode; flipping it on is one
    `IDENTITY_PROVIDERS=[...]` env var away.

    ## Why exceptions are caught inline (not propagated)

    Starlette's `BaseHTTPMiddleware` has a known quirk: exceptions
    raised in `dispatch()` are NOT routed through the app's
    registered `add_exception_handler` chain (they short-circuit to
    `ServerErrorMiddleware` and emit `500 Internal Server Error`
    plaintext). To preserve the BC-style typed-error contract while
    still emitting the RFC 6750 401 / RFC 7231 503 responses, the
    middleware catches the two auth errors here and delegates to the
    same handler functions used in `register_auth_exception_handlers`.
    This keeps the response shape in exactly one place
    (`exception_handlers.py`) and gives unit tests a single seam to
    pin the wire format.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Per `_routed_path` module docstring: read the routed path from
        # the ASGI scope, never from `request.url.path`. The two desync
        # under a crafted Host header on vulnerable Starlette versions
        # (CVE-2026-48710); skipping auth or picking the wrong audience
        # off the reconstructed path is a bypass.
        routed_path = _routed_path(request)
        if _is_unauthenticated_path(routed_path):
            # Unauthenticated paths (health / metrics / OAuth metadata) are
            # deployment-plumbing endpoints with no arrival-Surface semantics;
            # do NOT bind the observability dimension or it pollutes the log
            # with a Surface those probes never actually invoked.
            return await call_next(request)

        expected_audience = _resolve_expected_audience(routed_path)
        bind_surface_context(expected_audience, surface_kind_for(expected_audience))
        try:
            return await self._dispatch_authenticated(
                request, call_next, expected_audience=expected_audience
            )
        finally:
            clear_surface_context()

    async def _dispatch_authenticated(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
        *,
        expected_audience: UUID,
    ) -> Response:
        # `app.state.deps` is populated by the lifespan; the only path
        # where it could be unset is a request that hits before the
        # lifespan finishes. Starlette / FastAPI hold requests until
        # then so this is defensive — pyright doesn't know it.
        deps = getattr(request.app.state, "deps", None)
        verifier: TokenVerifier | None = deps.token_verifier if deps is not None else None
        if verifier is None:
            return await call_next(request)

        authorization = request.headers.get("authorization")
        if authorization is None:
            # For non-MCP paths: defer the 401-or-fallback decision to
            # get_principal_id which knows about
            # `require_authenticated_principal` + `app_env`.
            #
            # For /mcp/* paths under bearer-auth mode the middleware
            # MUST enforce here. FastMCP framing calls (initialize,
            # tools/list, notifications/*) don't reach tool-handler
            # code where `get_mcp_principal_id(ctx)` would raise, so
            # without a middleware-side 401 they'd flow through
            # unauthenticated. REST gets per-route `Depends(get_principal_id)`
            # for free; MCP has no equivalent layer below the tool
            # handler.
            routed_path = _routed_path(request)
            if routed_path == "/mcp" or routed_path.startswith("/mcp/"):
                # Lazy import: see module-level cycle-break note.
                from cora.infrastructure.auth.exception_handlers import (
                    missing_bearer_challenge,
                )

                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": (
                            "Missing Authorization: Bearer header for MCP. "
                            "This deployment requires a verified bearer "
                            "token; see /.well-known/oauth-protected-resource "
                            "for issuer metadata."
                        )
                    },
                    headers={"WWW-Authenticate": missing_bearer_challenge()},
                )
            return await call_next(request)

        # Lazy imports: ports module + handler module both live in
        # cora.infrastructure and would trigger the auth-package-init
        # cycle if imported at module top-level (see module docstring).
        from cora.infrastructure.auth.exception_handlers import (
            handle_introspection_unavailable,
            handle_invalid_token,
        )
        from cora.infrastructure.ports import (
            IntrospectionUnavailableError,
            InvalidTokenError,
        )

        try:
            token = _extract_bearer_token(authorization)
            principal = await verifier.verify(
                token,
                expected_audience=expected_audience,
            )
        except InvalidTokenError as exc:
            return await handle_invalid_token(request, exc)
        except IntrospectionUnavailableError as exc:
            return await handle_introspection_unavailable(request, exc)
        except Exception as exc:
            # Gate-review IMPL M1: any unexpected exception from the
            # verifier (httpx network blip, asyncpg failure, PyJWT
            # internal bug) would otherwise escape BaseHTTPMiddleware
            # and emit `500 Internal Server Error` plaintext via
            # Starlette's ServerErrorMiddleware -- bypassing the
            # FastAPI exception-handler chain AND the structured-log
            # pipeline. Catch + log + return a structured 500 JSON so
            # operators still get path/method context and clients see
            # the same envelope as every other error response.
            _log.exception(
                "bearer_auth.verifier_unexpected_error",
                path=_routed_path(request),
                method=request.method,
                error_type=type(exc).__name__,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": ("An unexpected error occurred while verifying the bearer token.")
                },
            )

        # Stash on request.state so get_principal_id can pull it
        # without re-verifying. Per-request state; no cross-request
        # leakage even with worker reuse.
        request.state.principal = principal
        _log.debug(
            "bearer_auth.verified",
            path=_routed_path(request),
            principal_id=str(principal.principal_id),
            issuer=principal.issuer,
            kind=principal.kind,
        )
        return await call_next(request)


def _extract_bearer_token(authorization_header: str) -> str:
    """Parse `Bearer <token>` from an Authorization header value.

    RFC 6750 §2.1 specifies a single space between the scheme and
    the credentials, case-insensitive scheme. Tolerate extra
    whitespace; reject every other shape.
    """
    # Lazy import: see module-level note for the cycle this breaks.
    from cora.infrastructure.ports import InvalidTokenError

    parts = authorization_header.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError(
            "malformed",
            "Authorization header is not a `Bearer <token>` shape",
        )
    token = parts[1].strip()
    if not token:
        raise InvalidTokenError(
            "malformed",
            "Authorization Bearer token value is empty",
        )
    return token


__all__ = ["BearerAuthMiddleware"]
