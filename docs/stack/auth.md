# Auth

For implementers wiring authentication and authorization. Each row names a role, the current pick, and the trigger that would force a swap. Edge authentication is in place for both HTTP and MCP streamable-HTTP; the proxy-only contract is a legacy fallback.

## Authentication

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| REST + MCP edge | `BearerAuthMiddleware` reading `Authorization: Bearer <token>`; per-path audience dispatch routes `/mcp/*` to the MCP Surface UUID, every other path to the HTTP Surface UUID | Single ingress shape across transports; standard RFC 6750; per-Surface audience binding prevents cross-Surface token replay | Stays |
| Token verification | `TokenVerifier` port + `IdentityProviderRegistry` routing by `iss` claim | One registry per process, per-IdP verifier behind it, shared by both transports | Stays |
| JWT path | `JwtTokenVerifier` (PyJWT, JWKS + RFC 9068 profile) | OIDC IdPs that publish JWKS (Entra, Okta, Auth0) | Stays |
| Opaque-token path | `IntrospectionTokenVerifier` (RFC 7662 introspection) | IdPs whose tokens are opaque (Globus Auth) | Stays |
| Subject mapping | `StaticSubjectMapper` (config-time `(issuer, subject) → actor_id`) | Pilot has bounded operator + agent set; explicit binding is auditable | Move to event-sourced `ActorIdpBindings` aggregate when first JIT-provisioning case lands |
| IdP metadata endpoint | RFC 9728 OAuth 2.0 Protected Resource Metadata at `/.well-known/oauth-protected-resource` | Lets clients discover accepted IdPs | Stays |
| MCP tool resolver | `get_mcp_principal_id(ctx)` reads the verified principal off `ctx.request_context.request.state.principal` | FastMCP framing methods (initialize / tools/list / notifications) get bearer-required enforcement at the middleware; tool handlers get the verified `principal_id` via the resolver | Stays |
| MCP_STDIO posture | Not bearer-verified; inherits local OS identity per MCP spec | Stdio is a subprocess transport; bearer-token shape doesn't fit | Wire HMAC or signed-bus when stdio is exposed over a network |
| Legacy fallback | `X-Principal-Id` header from a verifying proxy | Pre-bearer deployments; production refuses to boot without `REQUIRE_AUTHENTICATED_PRINCIPAL=true` | Removed once all fleets configure `IDENTITY_PROVIDERS` |

`get_principal_id` (REST) and `get_mcp_principal_id(ctx)` (MCP) share the same 3-mode priority: (1) bearer-verified principal on `request.state.principal` wins; (2) under bearer-auth mode without a verified principal, raise 401 (REST) / `McpUnauthenticatedError` (MCP); (3) legacy `X-Principal-Id` fallback (REST only) or `SYSTEM_PRINCIPAL_ID` (MCP, dev/test only). Bearer-mode 401s carry RFC 6750 `WWW-Authenticate: Bearer` challenges; introspection unavailability returns 503 + `Retry-After`.

## Authorization

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| `Authorize` port | Single `authorize(subject, command_name, conduit_id, surface_id) → AuthorizeDecision` | Surface_id threading lets one Policy bind to one surface (HTTP / MCP stdio / MCP streamable-http) | Stays |
| Policy engine | Trust BC `evaluate()` over current Policy aggregate | Inline; no external engine yet | First non-Cedar rule forces SpiceDB or OpenFGA |
| Authz model (planned) | ReBAC (SpiceDB or OpenFGA) | Multi-stakeholder ownership in shared facilities | Locked when first non-Cedar authz rule lands |
| Decision-BC policy language | Cedar | Used in Decision predicates (`has_determining_policies`) | Stays |
