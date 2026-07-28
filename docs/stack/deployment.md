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
| `LLM_ENABLED` | `false` → CORA calls no external model | The switch for the egress + spend axis. Required (with the key) for RunDebriefer / CautionDrafter |
| `ANTHROPIC_API_KEY` | unset → AI subscribers skipped | The credential. Setting it alone changes nothing; `LLM_ENABLED` decides |
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

If you do enable `local_process`, `COMPUTE_PERMITTED_EXECUTABLES` bounds
what it may spawn. The substrate refuses any `command[0]` outside the
set, before the spawn. It is EMPTY by default and empty permits nothing,
so enabling the substrate without naming an executable yields a port that
refuses every job rather than one that runs any. Matching is exact: the
check does no PATH resolution and no basename fallback, so
`/tmp/evil/tomopy` does not ride in on an allowlisted `tomopy`.

Two rules follow, and neither is optional:

- **Allowlist tools, never interpreters.** Permitting `python` or `sh`
  re-opens arbitrary execution through `-c`, and the check cannot tell
  the difference. Permit the tomopy binary, not the thing that can run
  it.
- **Declare absolute paths.** The check is exact, but the spawn still
  resolves a bare name against PATH afterwards, so allowlisting `tomopy`
  permits whatever PATH finds at that moment. A request cannot reach
  that (the conduct body carries no `env`), but a writable PATH entry on
  the host would still decide what runs. An absolute path settles it.

The allowlist is the belt, not the trousers: it bounds WHAT runs, it does
not authorize the path. Nothing in Trust gates the spawn, so every gate
here is authentication or configuration. The complementary fix is to give
every compute Method a `launch_spec`, so argv builds server-side from the
vetted, event-sourced recipe, and then set `CORA_ALLOW_RAW_CONDUCT=false`,
which deletes the caller-supplied argv path instead of bounding it. The
two compose: the allowlist bounds a `launch_spec`'s `base_command` at
submit exactly as it bounds a raw one, so a Method author cannot name an
executable this host does not permit either.

The gates that do and do not apply to a submit are documented at the top
of `cora.api._conduct_run_route`.

| Setting | Default | What it does |
| --- | --- | --- |
| `COMPUTE_SUBSTRATE` | `in_memory` | `local_process` spawns subprocesses on this host |
| `COMPUTE_PERMITTED_EXECUTABLES` | empty (permits nothing) | Exact-match allowlist for `command[0]` |
| `CORA_ALLOW_RAW_CONDUCT` | `true` | `false` rejects request-supplied argv outright |

## Container image

`apps/api/Dockerfile`. Build from the repo root:

```
docker build -f apps/api/Dockerfile -t cora-api:<tag> apps/api
```

Three facts about this image are not negotiable, and each one is a
property of the EPICS ecosystem rather than a preference:

- **It is linux/amd64, pinned.** `epicscorelibs`, `pvxslibs` and `p4p`
  publish x86_64 wheels only; there is no linux/aarch64 wheel for any of
  them. On an arm64 host the build runs under emulation and is slow.
  That is the cost of the wheels being what they are.
- **The builder needs gcc/g++.** `aioca` publishes no linux wheel at
  all, so it compiles its Channel Access extension against
  `epicscorelibs` at install time. The compiler stays in the builder
  stage and never reaches the runtime image.
- **One process per container.** No `--workers`. The lifespan starts
  in-process background workers (projection worker, subscribers,
  watchers); forking N copies would run N of each against one database.
  Scale with replicas, not workers.

The image does not run migrations. Atlas applies them out of band
(`make migrate-apply`) with a Go binary that is deliberately not
installed here: migrations are forward-only and operator-sequenced, so
an image that migrated itself on boot would let a rolling deploy race
two schema versions against one database. Apply migrations first, then
roll the image.

The image carries no configuration. `create_app()` runs at import and
its boot gates raise there, so a misconfigured container exits instead
of serving: `APP_ENV=prod` with no `TRUST_POLICY_ID` dies at import
rather than starting up permissive. Supply config as environment
variables (see `.env.example`), and note that `APP_ENV=test` builds the
in-memory kernel with no persistence, so it must never be set on a real
deployment.

The `HEALTHCHECK` probes `/health` (liveness) only, never `/readyz`.
Docker restarts a container whose HEALTHCHECK fails, and restarting an
app because its database is down is how one outage becomes a crash
loop. Readiness belongs on the orchestrator's `readinessProbe`.

Still deferred, and each now has a live trigger: an image registry, the
orchestrator (k8s / Cloud Run / bare VM + systemd), TLS termination,
and secrets management. See `docs/stack/deferred.md`.

## Probes

Two endpoints, both unauthenticated (a probe that has to hold a token
reports an expired token as a dead process) and both answering
different questions.

| Endpoint | Question | Checks | Point it at |
| --- | --- | --- | --- |
| `GET /health` | Is the process alive? | Nothing, deliberately | `livenessProbe` |
| `GET /readyz` | Can it serve a correct request? | Postgres | `readinessProbe` |

`/health` checks nothing and must keep checking nothing. Every
dependency it could check is one a restart cannot fix, and CORA is a
worse case than most: the pool is built once at startup with no retry,
so Postgres being down at boot exits the process before it binds a
socket. A liveness probe that checked the DB would therefore restart
every pod into an outage the restart cannot mend, converting one
database blip into a fleet-wide crash loop.

`/readyz` returns 200 `{"status": "ready", ...}` or 503
`{"status": "not_ready", "database": "..."}`, plus `actuation` and `llm`
fields on both (see below). `database` is a fixed vocabulary: `ok`,
`unreachable`, `saturated`, `closing`, `skipped` (this deployment has no
pool, the in-memory kernel), `error`. The body carries no URLs, no
driver error text, and no projection or bounded context names: it is
unauthenticated, and none of that helps a probe while all of it
describes the deployment to whoever can reach it. The logs carry the
detail.

Postgres is the only check, because readiness must report what can
CHANGE after a successful boot rather than restate boot. Every config
gate runs at import and every seed check at lifespan start, so a
process alive enough to answer `/readyz` has already passed all of
them. Postgres is the one thing that can fail afterwards.

Projection health is deliberately not gated on. A wedged projection is
a global condition: it would pull every replica at once, including the
pod hosting the in-band repair tool. Watch projection lag with a metric
and an alert, not with a traffic-routing signal.

### Verifying the observe-only posture

`/readyz` also carries `actuation`, either `inert` or `reachable`, and a
matching `boot.actuation_posture` line lands in the startup log. This is
the field that lets someone who will never hold credentials, a beamline
manager or a controls engineer, curl the observe-only claim instead of
trusting it. `inert` means CORA can observe but cannot move hardware;
`reachable` means at least one actuation path is open.

It is a REPORT, not a gate: it reads the settings the real gates already
use and summarises them, deciding and refusing nothing. It folds in BOTH
ways CORA can reach the beamline, and says `inert` only when both are
shut:

- the ControlPort write path (`CONTROL_WRITES_ENABLED`), and
- the ComputePort exec path, where a compute job's argv could itself be
  `caput ...`. Only `COMPUTE_SUBSTRATE=in_memory` is provably unable to
  spawn anything, so any other substrate reads `reachable`.

It errs toward `reachable` when uncertain: a false `reachable` is an
alarm someone investigates, a false `inert` is a facility discovering
CORA moved their stage after being told it could not. The boot log
prints the raw inputs (`control_writes_enabled`, `compute_substrate`,
`compute_permitted_executable_count`, `cora_allow_raw_conduct`, route
count) beside the summary so it can be audited against its own sources.

Scope, stated so it is not mistaken for more: `actuation` covers the
hardware axis only. Sending data OUT and SPENDING money are separate
promises, and they now have a switch and a summary of their own.

### The egress and spend axis

`LLM_ENABLED` (default `false`) is the switch; `ANTHROPIC_API_KEY` is the
credential. Both are required before CORA calls an external model, and
`/readyz` reports the effective state as `llm`, either `off` or `live`,
with a matching `boot.llm_posture` line at startup.

**Upgrading:** a deployment that ran the LLM subscribers on
`ANTHROPIC_API_KEY` alone must now also set `LLM_ENABLED=true`, or those
two subscribers stop registering. Nothing breaks and nothing crashes; a
boot warning names the switch, and `GET /readyz` reports `"llm": "off"`.

The switch exists because the credential alone used to be enough. A key
present in the environment for an unrelated reason silently registered
the RunDebriefer and CautionDrafter subscribers, which call an external
API on every terminal Run: experiment metadata leaving the facility, and
money spent, because of a side effect. Every sibling subscriber already
carried its own default-off flag; this seam was the outlier.

Turning it off is graceful. The two LLM-backed subscribers are skipped
with a warning naming which of the two settings is missing,
`regenerate_run_debrief` answers unavailable, and a conduct command that
explicitly asks for the `llm` decide substrate gets a 422 at
construction, before any FSM transition.

Read `llm` narrowly: it reports ONE outbound path, not a perimeter.
CORA's HTTP checksum adapter is wired unconditionally for http/https
Distributions, so the process can still make outbound requests with the
LLM entirely off. That is why the field is named `llm` and not `egress`.

Two adapter families remain dormant on this axis: the outbound transfer
adapters and the remote-compute adapter exist but are wired nowhere, and
a fitness test (`test_dormant_outbound_seams_unwired`) fails the build if
one gets constructed without the derivation being revisited. The trigger
to build a genuinely spanning egress summary is the first of those paths
that gets wired at the composition root.

**Probe budget invariant.** The app bounds `/readyz` at 1.5s total.
Set the orchestrator's own probe timeout ABOVE that (2s or more).
Nothing enforces this. If the orchestrator gives up first, its
disconnect rather than the app's timeout ends the request, and
`/readyz` silently degrades from a diagnostic endpoint into a hang
detector: the `{"database": "saturated"}` body that is the entire point
never gets written. Suggested: `timeoutSeconds: 2`, `periodSeconds: 10`,
`failureThreshold: 3`.

Two limits worth knowing before the pilot:

- **Readiness buys little at one replica**, which is the 2-BM pilot's
  shape. Pulling the only pod from a Service gives callers
  connection-refused instead of a 503 they can read. At one replica,
  treat `/readyz` as a signal to scrape and alert on; its traffic-shifting
  value arrives at replica two.
- **There is no graceful drain.** Nothing flips `/readyz` to not_ready
  before shutdown begins, so during a rolling deploy the endpoint still
  answers ready while the app is tearing down. `database: closing` is
  the symptom of that gap, not a substitute for fixing it. Expect
  rolling deploys to drop in-flight requests until a drain lands.

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
| Container image | SHIPPED | `apps/api/Dockerfile`; see "Container image" above |
| Image registry | Deferred | Where the orchestrator pulls from; decided with the orchestrator |
| Runtime orchestrator (k8s / Cloud Run / ECS / bare VMs) | Deferred | First non-local deployment |
| Event-sourced `ActorIdpBindings` (JIT Actor provisioning) | Deferred | First case where adding an operator is too high-friction via config-time bindings |
| `trust.check_others` permission separation | Watch item | When ABAC lands or first cross-tenant deploy |

Bootstrap policy, Surface decomposition, HTTP edge auth, permission queries, and MCP edge-auth parity are all in place.
