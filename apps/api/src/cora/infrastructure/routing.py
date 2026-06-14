"""Cross-BC route helpers and the system-principal fallback constant.

Hosts the three pieces every BC's slice routes need:

  - `get_correlation_id` — FastAPI Depends that returns the current
    request's correlation UUID derived from the active OTel span
    (or a fresh UUIDv4 when no span is active, for example in tests using
    the no-op tracer).
  - `get_principal_id` — FastAPI Depends that extracts the calling
    principal's UUID from the `X-Principal-Id` header (Pydantic
    UUID-validates -> 422 on malformed). When
    `Settings.require_authenticated_principal` is False (legacy
    dev / test default), an absent header falls back to
    `SYSTEM_PRINCIPAL_ID`. When True (production posture), an
    absent header raises HTTP 401 instead. See the "Production
    hardening conventions" section of CONTRIBUTING.md for the
    trust-the-proxy deployment requirement.
  - `ErrorResponse` — Pydantic body shape for OpenAPI documentation
    of error responses.

Also exposes `SYSTEM_PRINCIPAL_ID`, the canonical fallback principal
UUID. MCP tools resolve principals via
`cora.infrastructure.mcp_principal.get_mcp_principal_id(ctx)` instead
of importing this constant directly; the architecture fitness
`test_no_system_principal_id_in_mcp_tool_principal_kwarg` enforces
the swap. The constant is still imported by infra (bootstrap seed,
event-store envelope construction in tests, MCP resolver's dev/test
fallback path).

Lives at `cora/infrastructure/` (not in any single BC) because both
BCs need byte-identical implementations and a future BC-3 will too.
Per-BC `_bootstrap.py` modules re-export `SYSTEM_PRINCIPAL_ID` from
here so existing import paths stay stable; per-BC `_routing.py`
modules are gone (their helpers moved here).

Slice routes still own their handler-fetcher (`_get_handler`)
because it pulls a per-slice field off `app.state.<bc>` — different
per slice. That's the only per-slice DI helper left.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from cora.infrastructure.observability import current_correlation_id

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
"""Fallback principal used when no `X-Principal-Id` header is supplied.

Used only when `Settings.require_authenticated_principal` is False
(legacy dev / test posture). Production deployments behind an auth
proxy set the header on every request and turn the setting on so
header-absent requests are rejected at the boundary instead of
silently running as SYSTEM. Under `TrustAuthorize` with a real
policy that doesn't permit `SYSTEM_PRINCIPAL_ID`, fallback-using
requests get 403 even with the setting off — defense in depth pinned
by `tests/contract/test_principal_header.py`.
"""


NIL_SENTINEL_ID = UUID(int=0)
"""Canonical unspecified-id sentinel.

`UUID(int=0)` means "unspecified" wherever the Authorize port quadrant
takes a UUID identifier (conduit_id, surface_id, and any future axis).
It is NOT a wildcard: `Policy.evaluate` strict-matches every axis, so a
policy bound to conduit_id=NIL matches only a call that also presents
NIL, and likewise for surface_id. The conduit axis is operationally
inert today because every handler passes NIL on both sides (nil matches
nil); the surface axis is bound to a real Surface on the bootstrap
policy and every request resolves a real arrival surface. (An earlier
nil-as-wildcard fold for surface_id was removed when the nil-surface
bootstrap policy was retired.)

Previously declared as `_NIL_SENTINEL_ID` / `_CONDUIT_DEFAULT_ID`
per-file in ~80 slice handlers + 3 cross-BC factories. Consolidated
here so a single canonical name covers both axes — the prior
`_CONDUIT_DEFAULT_ID` reading was a future-reader trap when used as
a `surface_id` default."""


SYSTEM_HTTP_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000020")
SYSTEM_MCP_STDIO_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000021")
SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000022")
"""Seeded arrival-Surface UUIDs.

These three constants are written by the
20260519200000_seed_default_surfaces_and_v2_policy.sql migration and
referenced by `cora.trust._bootstrap` (verify_bootstrap_seed_present)
and by `get_surface_id` / `get_mcp_surface_id` below.

Lives in `cora.infrastructure.routing` rather than `cora.trust._bootstrap`
so every BC's route / tool can import the resolver helpers without
violating the tach BC-isolation rule (BCs may import infrastructure
but not other BCs or `cora.api`). `cora.trust._bootstrap` re-exports
these for backward compatibility with existing trust-internal callers.
"""


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def get_correlation_id() -> UUID:
    """Derive the request's correlation UUID from the active OTel span.

    OpenTelemetry is the source of truth for "this request" identity:
    `FastAPIInstrumentor` extracts the inbound W3C `traceparent` header
    (or starts a fresh trace when absent) and exposes the trace_id
    through the active span. `current_correlation_id` formats the
    128-bit trace_id as a UUID; if no span is active (test environments
    using the no-op tracer), it generates a fresh UUID.
    """
    return current_correlation_id()


def _require_authenticated_principal(request: Request) -> bool:
    """Read the `require_authenticated_principal` flag off the running
    app's settings (carried on the kernel attached to `app.state.deps`).

    Lives as its own Depends so `get_principal_id` stays testable in
    isolation and so the read happens at request time (the kernel
    isn't attached to app.state until the lifespan runs).
    """
    return bool(request.app.state.deps.settings.require_authenticated_principal)


def _bearer_principal_id(request: Request) -> UUID | None:
    """Return `request.state.principal.principal_id` if set, else None.

    `BearerAuthMiddleware` populates `request.state.principal` when
    an `Authorization: Bearer` header verified successfully.
    `get_principal_id` reads through this Depends so the existing
    in-isolation unit tests for `get_principal_id` keep working
    without a Request object.

    Gate-review SEC S2: `isinstance(principal, VerifiedPrincipal)`
    guard. Today only BearerAuthMiddleware writes to
    `request.state.principal`, but a future middleware that
    accidentally writes a duck-typed object with a `.principal_id`
    attribute would silently authenticate callers. Pinning the type
    here closes that footgun before it ships.
    """
    # Lazy import: matches the cycle-break pattern in
    # bearer_auth_middleware.py + auth/config.py.
    from cora.infrastructure.ports import VerifiedPrincipal

    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, VerifiedPrincipal):
        return None
    return principal.principal_id


def _bearer_auth_enabled(request: Request) -> bool:
    """Return True when `kernel.token_verifier` is non-None.

    `BearerAuthMiddleware` populates `request.state.principal` from a
    verified bearer when this is True. `get_principal_id` consults
    this to refuse X-Principal-Id fallback under bearer-auth mode
    (the cleartext header is unauthenticated in that posture, so
    accepting it would defeat the bearer gate).
    """
    deps = getattr(request.app.state, "deps", None)
    if deps is None:
        return False
    return deps.token_verifier is not None


def get_principal_id(
    x_principal_id: Annotated[
        UUID | None,
        Header(
            alias="X-Principal-Id",
            description=(
                "Legacy principal-id header (trust-the-proxy shape). "
                "When IDENTITY_PROVIDERS is configured (bearer-auth mode), "
                "this header is IGNORED and the verified bearer token "
                "from `BearerAuthMiddleware` (Authorization: "
                "Bearer) sets the principal. When no IdPs are configured "
                "(legacy mode), the application TRUSTS this header (no "
                "cryptographic verification) -- production deployments in "
                "legacy mode MUST front the API with an auth proxy that "
                "strips any client-supplied X-Principal-Id and sets it to "
                "the verified principal UUID. Behavior when absent: see "
                "Settings.require_authenticated_principal."
            ),
        ),
    ] = None,
    bearer_principal_id: Annotated[
        UUID | None,
        Depends(_bearer_principal_id),
    ] = None,
    bearer_auth_enabled: Annotated[
        bool,
        Depends(_bearer_auth_enabled),
    ] = False,
    require_authenticated: Annotated[
        bool,
        Depends(_require_authenticated_principal),
    ] = False,
) -> UUID:
    """Resolve the calling principal's id.

    Three modes, in priority order:

      1. **Bearer-auth mode + valid bearer**:
         `BearerAuthMiddleware` verified an `Authorization: Bearer
         <token>` and stashed the `VerifiedPrincipal` on
         `request.state.principal`. Return its
         `principal_id`. X-Principal-Id is silently IGNORED in this
         mode (cleartext header is unauthenticated; honoring it
         would defeat the bearer gate).

      2. **Bearer-auth mode + no bearer**:
         No verified principal on request.state. The middleware
         already let the request through (it doesn't impose a 401
         policy on its own). Refuse here with 401 -- the legacy
         X-Principal-Id fallback is NOT allowed under bearer-auth
         mode regardless of `require_authenticated_principal`.

      3. **Legacy mode** (no IdPs configured):
         - X-Principal-Id present -> use it.
         - Absent + `require_authenticated_principal=True` -> 401.
         - Absent + `require_authenticated_principal=False` ->
           SYSTEM_PRINCIPAL_ID fallback (legacy dev / test).
    """
    # Mode 1: bearer-verified principal wins unconditionally.
    if bearer_principal_id is not None:
        return bearer_principal_id

    # Mode 2: bearer-auth on but no bearer presented.
    if bearer_auth_enabled:
        # Gate-review DESIGN M1: format the challenge via the shared
        # helper so the realm + resource_metadata constants live in
        # exactly one place (exception_handlers.py). A future rename
        # (realm cluster naming, RFC 9728 path move) updates one site.
        # Lazy import matches the established cycle-break pattern.
        from cora.infrastructure.auth.exception_handlers import missing_bearer_challenge

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing Authorization: Bearer header; this deployment "
                "requires a verified bearer token. See "
                "/.well-known/oauth-protected-resource for issuer metadata."
            ),
            headers={"WWW-Authenticate": missing_bearer_challenge()},
        )

    # Mode 3: legacy X-Principal-Id path.
    if x_principal_id is None:
        if require_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing X-Principal-Id header; this deployment "
                    "requires an authenticated principal."
                ),
            )
        return SYSTEM_PRINCIPAL_ID
    return x_principal_id


def get_surface_id(request: Request) -> UUID:
    """Resolve the arrival Surface for an HTTP request.

    v1: static return. Process-derived (no client-asserted header /
    query param). A future revision extends the body to
    validate the bearer token's `aud` claim against the Surface's
    expected audience before returning — `request: Request` is in
    the signature today so the body can extend without changing the
    dependency API.
    """
    _ = request
    return SYSTEM_HTTP_SURFACE_ID


def get_mcp_surface_id() -> UUID:
    """Resolve the arrival Surface for an MCP tool call.

    CORA only serves MCP over streamable-http in production (per
    `cora/api/main.py` mounting `streamable_http_app()`). Stdio is
    unreachable in production. The adapter returns the streamable-
    http constant unconditionally — no `ctx` parameter needed, so
    existing MCP tool signatures don't change.

    If stdio shipping is added later, pin the surface id on a
    closure parameter at tool-registration time
    (`register(mcp, *, surface_id=...)`) rather than inspecting
    `ctx` — no client-asserted surface is preserved either
    way. GR3 RISK-1 + RISK-4.
    """
    return SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID


__all__ = [
    "NIL_SENTINEL_ID",
    "SYSTEM_HTTP_SURFACE_ID",
    "SYSTEM_MCP_STDIO_SURFACE_ID",
    "SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID",
    "SYSTEM_PRINCIPAL_ID",
    "ErrorResponse",
    "get_correlation_id",
    "get_mcp_surface_id",
    "get_principal_id",
    "get_surface_id",
]
