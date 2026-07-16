# Deployment

For operators bringing CORA up at a new facility (pilot: APS 2-BM). Covers env-var posture, the bootstrap authz workflow, the first-boot Actor + Policy registration, and the recovery path when the seed gets corrupted.

## Env vars

The load-bearing auth vars (full list in `.env.example`):

| Var | Default | When you set it |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://cora:cora@localhost:5432/cora` | Always |
| `TRUST_POLICY_ID` | unset → `AllowAllAuthorize` | When you want real authz. In a production-tier env (`prod`/`production`/`staging`) it is required unless `ALLOW_PERMISSIVE_AUTHZ=true` (see below) |
| `REQUIRE_AUTHENTICATED_PRINCIPAL` | `false` | Must be `true` whenever `TRUST_POLICY_ID` is set, and in any production-tier env (the boot gate refuses otherwise; see below) |
| `ALLOW_PERMISSIVE_AUTHZ` | `false` | Production-tier escape hatch: set `true` to run the permit-everyone `AllowAllAuthorize` stub on purpose in a `prod`/`production`/`staging` env (airgapped / single-operator pilot) |
| `IDENTITY_PROVIDERS` | unset → legacy `X-Principal-Id` header mode | JSON list of `IdentityProviderConfig` entries (see [Auth](auth.md)); enables bearer-token mode at the HTTP edge |
| `ANTHROPIC_API_KEY` | unset → AI subscribers log-and-skip | When you want RunDebriefer / CautionDrafter live |
| `CONTROL_WRITES_ENABLED` | `false` → CORA never drives through the ControlPort | Set `true` only when this deployment is meant to actuate hardware (see below; it does not cover `COMPUTE_SUBSTRATE`) |
| `CONTROL_PORT_ROUTES` | unset → `InMemoryControlPort` (no real substrate) | When CORA talks to a real control system. JSON list of `ControlPortRoute` |

### Observe-only deployments

`CONTROL_WRITES_ENABLED` defaults to `false`, and that default is the
mechanism behind an observe-only deployment such as the APS 2-BM pilot.
Every adapter the ControlPort factory builds is wrapped in a
`ReadOnlyControlPort`: `read` and `subscribe` pass through, and `write`
raises `ControlWritesDisabledError` before any substrate is contacted.
The Conductor records that refusal as a step failure naming the address.

Two properties are worth stating plainly, because they are what make the
observe-only claim true rather than aspirational:

- **It cannot be partially applied.** There is no per-substrate or
  per-route exemption, not even for `in_memory`. Inferring safety from
  the substrate is the mistake `is_simulated` exists to prevent: a soft
  IOC speaks real Channel Access.
- **It fails closed.** The refusal is decided when the port is built, not
  consulted at write time, so there is no "flag could not be read" state
  that silently permits a write.

`ControlPortRoute.read_only` is the per-route counterpart, but it
defaults to writable, so it is expressiveness within a *writable*
deployment ("CORA may drive the sample stage but must never touch the
shutter"), NOT the safety gate. To make a deployment observe-only, use
the switch.

Scope this honestly when describing the pilot: the switch closes CORA's
*modeled* actuation path (`ControlPort`). It does not by itself make the
host incapable of touching the beamline.

The other path is `ComputePort`. With `COMPUTE_SUBSTRATE=local_process` a
conduct job's argv runs as an OS subprocess under the API service
account, so an argv like `["caput", ...]` reaches a control system
without passing through any ControlPort, whatever
`CONTROL_WRITES_ENABLED` says. Two properties make this sharper than it
first looks: with `CORA_ALLOW_RAW_CONDUCT=true` (the current default) the
argv can come straight from the request body for any Method with no
`launch_spec`; and no Trust policy gates the spawn, because the Authorize
port gates the run transition (`complete_run` / `abort_run`), which
happens after the subprocess has already run.

What keeps this inert today is the default: `compute_substrate` is
`in_memory` (`cora.infrastructure.config`), which mints a Simulated
result and spawns nothing. An observe-only deployment leaves it there.
Before enabling `local_process` at a beamline, give every compute Method
a `launch_spec` so argv is built server-side from the vetted recipe, then
set `CORA_ALLOW_RAW_CONDUCT=false` to close the caller-supplied path. The
gates that do and do not apply to a submit are documented at the top of
`cora.api._conduct_run_route`.

### Startup boot gate

If you set `TRUST_POLICY_ID` without `REQUIRE_AUTHENTICATED_PRINCIPAL=true`, `create_app()` raises `RuntimeError` at boot. Without the header check, anyone could send `X-Principal-Id: 00000000-…0` and impersonate SYSTEM under the configured policy, so the two must be set together.

In a production-tier env (`APP_ENV` = `prod`, `production`, or `staging`), `create_app()` also raises `RuntimeError` if `TRUST_POLICY_ID` is unset, because a None policy wires `AllowAllAuthorize`, which permits every command. Point `TRUST_POLICY_ID` at the seeded bootstrap policy (`00000000-0000-0000-0000-000000000002`) to enable real authz, or set `ALLOW_PERMISSIVE_AUTHZ=true` to run permissive on purpose. The opt-in mirrors the per-IdP `allow_insecure_*` flags: the insecure choice stays available, but only as a conscious one. `staging` is treated as production-tier (it usually handles real data and is network-reachable); other env names (dev/local/ci/e2e) keep the permissive default.

Test env (`APP_ENV=test`) is exempt: legitimate test fixtures exercise the SYSTEM-fallback-under-real-policy scenario.

## Edge authentication

Two supported postures, picked by whether `IDENTITY_PROVIDERS` is configured.

### Bearer mode (recommended)

When `IDENTITY_PROVIDERS` is set, `BearerAuthMiddleware` reads `Authorization: Bearer <token>` from every request, routes to the right `TokenVerifier` per the token's `iss` claim, and stashes a `VerifiedPrincipal` on `request.state.principal`. `get_principal_id` reads it from there.

- **JWT IdPs** (Entra, Okta, Auth0, Helmholtz AAI): set `jwks_url`. PyJWT verifies signature + audience + expiry locally.
- **Opaque-token IdPs** (Globus Auth): set `introspection_url` + `introspection_client_id` + `introspection_client_secret`. Verifier calls RFC 7662 introspection per request (per-token TTL cache).
- **Subject mapping**: each IdP carries `subject_bindings: list[IdpSubjectBinding]`, each a `(subject, actor_id, kind?)` triple. Tokens whose subject is unbound get 401. JIT provisioning is deferred until the first concrete use case.
- **Discovery**: `GET /.well-known/oauth-protected-resource` returns RFC 9728 metadata listing accepted IdPs.

Token-related failures:

| Outcome | HTTP | Headers |
| --- | --- | --- |
| Missing / malformed bearer | 401 | `WWW-Authenticate: Bearer realm="cora"` |
| Invalid signature / expired / unknown issuer | 401 | `WWW-Authenticate: Bearer realm="cora", error="invalid_token", error_description="..."` |
| Subject unbound in CORA | 401 | `WWW-Authenticate: Bearer realm="cora", error="invalid_token"` |
| Introspection endpoint unavailable | 503 | `Retry-After: 5` |

`Kernel.token_verifier=None` (no `IDENTITY_PROVIDERS`) leaves the middleware off and the legacy header-only path live. This is the path test fixtures take.

### Legacy proxy mode (fallback)

Without `IDENTITY_PROVIDERS`, production MUST still sit behind a verifying proxy (nginx, Caddy, Cloud-IAP, AWS ALB, Globus Auth at APS) that:

1. Verifies the caller's identity via your facility's identity protocol (OIDC / Globus / SAML / mTLS).
2. **Strips any client-supplied `X-Principal-Id` header.** Critical: otherwise the boot gate's protection is bypassed by a header injection.
3. Sets `X-Principal-Id: <verified-caller-uuid>` based on the verified identity.

The proxy owns the identity → UUID mapping in this mode. Migrating to bearer mode replaces the mapping step (and the strip step) with `subject_bindings`.

### MCP edge

MCP streamable-HTTP runs the same `BearerAuthMiddleware` as REST. Per-path audience dispatch binds `/mcp/*` to the MCP Surface UUID (`SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID`); a token issued for HTTP cannot replay against MCP. Under bearer-auth posture the middleware enforces bearer-required for every `/mcp/*` path including FastMCP framing methods (`initialize`, `tools/list`, `notifications/initialized`), so a missing-bearer request returns 401 before reaching the tool layer. Tool handlers resolve the calling `principal_id` via `get_mcp_principal_id(ctx)`, the MCP-side mirror of `get_principal_id`. Write tools remain visible in `tools/list` and are gated at call time, not by deregistration. MCP_STDIO (subprocess transport) inherits the operator's local OS identity per spec; bearer auth is HTTP-edge only.

## Surface decomposition and the bootstrap policy

The Trust BC carries a `Surface` aggregate (HTTP, MCP stdio, MCP streamable-http) and a bootstrap policy bound to the HTTP Surface. `evaluate` strict-matches a policy's `surface_id` against the request's arrival surface, so every policy binds a concrete Surface.

| Id | Surface binding | Status |
| --- | --- | --- |
| `00000000-0000-0000-0000-000000000002` | HTTP Surface (`...0020`) | The bootstrap policy. Set `TRUST_POLICY_ID` to this. |
| `00000000-0000-0000-0000-000000000001` | nil | Retired. Its nil surface no longer matches any real arrival surface, so it strict-denies every call. Do not point `TRUST_POLICY_ID` at it; a deployment that does is locked out. The stream stays in the event log (forward-only migrations) but is operationally inert. |

To enable real authz:

1. Apply the seed migration: `make migrate-apply`. Seeds the 3 default Surfaces and the bootstrap policy. Idempotent.
2. Set `TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002` and `REQUIRE_AUTHENTICATED_PRINCIPAL=true`.
3. Restart. At lifespan start the verifier confirms the policy stream exists, binds to `SYSTEM_HTTP_SURFACE_ID`, and that all 3 seeded Surfaces are present; boot fails loud if anything is missing.

## First-boot workflow

A fresh deployment with `TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002` (the bootstrap policy) starts in a deliberate narrow-permissive state.

- The seed permits `SYSTEM_PRINCIPAL_ID` (the nil UUID `00000000-…0`) to call `DefinePolicy` and `RegisterActor` on the nil conduit + the HTTP Surface.
- That's it. Every other command Denies.

The operator's bootstrap path:

1. **Boot CORA** with both env vars set + the auth proxy in front.
2. **Configure the auth proxy to set `X-Principal-Id: 00000000-0000-0000-0000-000000000000`** for the operator's initial admin session. (Document this as a temporary "bootstrap session" in your proxy config; strip it after step 4.)
3. **Register your real admin Actor** via the API:

   ```
   POST /actors
   X-Principal-Id: 00000000-0000-0000-0000-000000000000
   Content-Type: application/json
   { "name": "<real admin name>" }
   ```

   Record the returned `actor_id`; this is your real admin's principal UUID.

4. **Define your real admin Policy** via the API:

   ```
   POST /policies
   X-Principal-Id: 00000000-0000-0000-0000-000000000000
   Content-Type: application/json
   {
     "name": "Real Admin Policy",
     "conduit_id": "00000000-0000-0000-0000-000000000000",
     "permitted_principal_ids": ["<actor_id from step 3>"],
     "permitted_commands": ["DefinePolicy", "RegisterActor", "DefineZone", "DefineConduit", "..."]
   }
   ```

   Record the returned `policy_id`.

5. **Re-configure the auth proxy** to set `X-Principal-Id` to the real admin's UUID (from step 3) for the admin's verified identity. Remove the bootstrap-session SYSTEM override.

6. **Update `TRUST_POLICY_ID`** to the new `policy_id` from step 4 and restart.

The bootstrap seed stays on disk + in the event log forever; you can re-point at it during recovery scenarios.

## Recovery

### Bootstrap seed missing at startup

If the boot gate succeeds but `TRUST_POLICY_ID` points at `SYSTEM_BOOTSTRAP_POLICY_ID` and the seed stream is missing, `create_app()` raises `RuntimeError` at lifespan start with a runbook pointer. Cause: stale DB, restored backup that missed the seed, manual SQL that deleted it.

Recovery:

```
make migrate-apply
```

The seed migration (`infra/atlas/migrations/20260519200000_seed_default_surfaces_and_v2_policy.sql`) is idempotent (`ON CONFLICT DO NOTHING`) and safe to re-apply. After it lands, restart CORA.

### Real admin policy unreachable

If you've promoted a real admin Policy and lost the ability to call into it (compromised credentials, dropped key, etc.), re-point `TRUST_POLICY_ID` back to `SYSTEM_BOOTSTRAP_POLICY_ID` and run the first-boot workflow again with a new admin Actor. The old policy stays in the event log; the new one shadows it via `TRUST_POLICY_ID`.

### Diagnosing 403s in production

Logs to grep (structlog JSON):

| Symptom | Event name | Field to filter |
| --- | --- | --- |
| Every API call 403s | `trust_authorize.policy_missing` | `policy_id` |
| One principal can't call a command | `trust_authorize.deny` | `principal_id`, `command_name`, `reason` |
| One slice path 403s | `<slice_name>.denied` | `correlation_id` (joins to the underlying `trust_authorize` event) |

The `correlation_id` field is present on every `trust_authorize.*` event and every slice handler event, so a single Loki query `correlation_id="..."` traces the full request path.

For self-service "what CAN I do?" debugging, use:

```
GET /policies/{policy_id}/permissions?evaluated_principal_id=<me>&evaluated_conduit_id=00000000-0000-0000-0000-000000000000
```

This returns the sorted list of commands the named principal can run via the named conduit. The result is **not authoritative for authorization decisions**: it's a UX / debugging aid; only the PEP at each handler actually authorizes.

## Deferred

| Concern | Status | Trigger |
| --- | --- | --- |
| Container image + registry | Deferred | First non-local deployment |
| Runtime orchestrator (k8s / Cloud Run / ECS / bare VMs) | Deferred | First non-local deployment |
| Event-sourced `ActorIdpBindings` (JIT Actor provisioning) | Deferred | First case where adding an operator is too high-friction via config-time bindings |
| `trust.check_others` permission separation | Watch item | When ABAC lands or first cross-tenant deploy |

Bootstrap policy, Surface decomposition, HTTP edge auth, permission queries, and MCP edge-auth parity are all in place.
