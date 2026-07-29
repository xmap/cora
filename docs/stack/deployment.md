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
| `ALLOW_SCHEMA_VERSION_MISMATCH` | `false` | Boot against a schema this build does not expect, with all writes refused, to read a restored database. Not a way to run a mismatched deployment: see [Restoring an old backup under a newer image](#restoring-an-old-backup-under-a-newer-image) |
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

### Seeding the beamline the pilot needs

`ingest_scan` refuses to record until two things exist: a registered
Asset whose family affordances include Capturing, and a registered
Storage-kind Supply. Neither appears by itself. The pilot seed
ceremony registers them, idempotently:

```bash
python -m cora.api.pilot_seed --dry-run
```

then the same command without `--dry-run` once the report reads right.
It registers the beamline root Unit Asset, the camera Device Asset,
its Camera family attachment (the Camera seed family carries
Capturing), and one Storage Supply which it also marks Available (a
merely-registered Supply satisfies neither the run-preflight gates nor
the legacy-Distribution backfill). It prints one line per instance:
`seeded`, `exists`, `retired` (a decommissioned stream is reported and
never resurrected; decommission-then-re-register is an operator
rebind, not a seeding concern), or `error`. Exit codes: 0 when
everything already existed, 2 when anything was seeded (or would be,
under `--dry-run`), 1 on any error. Re-running is always safe and
changes nothing.

The seeded supply's name (default `analysis-tier`) pairs with
`SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`: the lifespan-time
Distribution backfill resolves that env var against the same supply
name. A deployment that will ever hold legacy Datasets should set the
env var to the seeded name in the same breath as running the ceremony.

Two facts worth knowing before running it. The ceremony runs the same
idempotent bootstrap hooks the app lifespan runs and drains the
relevant projections itself, so it works against a never-booted
database; and `--facility-code` must name the code this deployment
self-seeds (`SELF_FACILITY_CODE`), or the run stops with a loud
FacilityNotFound rather than registering under the wrong facility.

A database seeded before the Camera family carried Capturing reports
`error: family Camera lacks the Capturing affordance` and names the
remedy (`version_family` adding it); the ceremony never mutates a
family itself, because family definitions belong to the seed
registry's graduation governance.

This is deliberately NOT a descriptor import. The full
beamline-descriptor onboarding is a later slice with its own trigger;
the ceremony seeds exactly what the read-only pilot's ingest path
exercises, with explicit arguments and no hidden inputs.

## Recovery

### Backup and point-in-time recovery

CORA is described as the system of record for the experiment, and the
Postgres event store is where that record physically lives: every Run,
every provenance chain, every Decision. A system of record with no
restore path is the one claim a facility reviewer can disprove in a
single question, so this section describes a posture that has been
executed rather than designed.

**The tool is pgBackRest.** The candidates were pgBackRest, WAL-G, and a
managed service. Managed Postgres is not available for an on-premises
beamline deployment holding facility data, which leaves two, and the
choice between them turns on who runs the restore. That person is a
beamline scientist at an awkward hour, not a database administrator.

| | pgBackRest | WAL-G |
| --- | --- | --- |
| Recovery configuration | Generated into `postgresql.auto.conf` by `restore` | Operator writes `recovery.signal` and `restore_command` by hand |
| Point-in-time restore | One command with `--type=time --target=` | Assembled from several |
| Verifying the setup | `check` forces a WAL segment through `archive_command` and confirms it reached the repository | `wal-verify` checks WAL history, not that `archive_command` works |
| Repository targets | posix, cifs, sftp, s3, gcs, azure | Object stores, with local disk secondary |
| Retention | Declared in config, applied automatically | Manual `delete` |

The first row decides it. WAL-G asks a non-expert to hand-author Postgres
recovery configuration at exactly the moment they are least equipped to,
and a restore path that depends on remembering syntax is a restore path
that fails when used. The last two rows matter for a different reason:
retention that has to be remembered is retention that lapses, and the
repository target is a single configuration key, so the backup
destination can be decided later without changing one operator-facing
command.

`pg_dump` was not a candidate. It produces a snapshot, so the best any
restore can do is return the database to the moment the dump ran. That is
not point-in-time recovery, and for an append-only event store it means
discarding every event since the last dump.

#### What is configured

Everything lives in `infra/backup/`: a Postgres image with pgBackRest
installed (`Dockerfile`), the configuration (`pgbackrest.conf`), and an
isolated stack used by the drill (`docker-compose.backup.yml`).

The settings come in two halves, and an installation needs both. The
first three belong to **PostgreSQL**, not to pgBackRest, so they are not
in `pgbackrest.conf`: the drill stack sets them in its compose file, and a
package-managed host sets them in `postgresql.conf` or a `conf.d`
fragment. Copying `pgbackrest.conf` alone yields a cluster with no WAL
archive, which is the one condition its own first row rules out.

| Setting | Owner | Value | Why |
| --- | --- | --- | --- |
| `archive_mode` | PostgreSQL | `on` | Without it there is no point-in-time recovery, only snapshots |
| `archive_command` | PostgreSQL | `pgbackrest --stanza=cora archive-push %p` | Ships each WAL segment as it closes |
| `archive_timeout` | PostgreSQL | `60` | This is the recovery point objective. See below |
| `repo1-retention-full` | pgBackRest | `4` | Roughly a month at the cadence below, chosen to outlive a beamtime cycle |
| `compress-type` | pgBackRest | `zst` | jsonb payloads compress well, and zstd costs less CPU than gzip on the host running the beamline's record |

Set the PostgreSQL three through a configuration file rather than the
`postgres` command line. Command-line settings outrank both
`postgresql.conf` and `ALTER SYSTEM`, so a cluster started that way
cannot be adjusted without a restart, and pgBackRest's own
`--archive-mode=off` restore option, which works by writing to
`postgresql.auto.conf`, silently does nothing. The drill's compose file
uses the command line anyway, for its own convenience, and says so.

**`archive_timeout` is the recovery point objective, so read it as a
number and not as a tunable.** Postgres ships a WAL segment when it fills
(16MB) or when this timer expires, whichever comes first. CORA's event
store is append-heavy but low-volume, so on a quiet beamline the fill
condition may not arrive for a long time, and without a timer the newest
events would sit unarchived until it did. A host loss at that point takes
them. At 60 seconds the worst case is losing the last minute of events.
The cost of lowering it is one mostly-empty 16MB segment per interval.

Suggested cadence, which nothing currently automates (see the limits
below): a full backup weekly, a differential daily.

```bash
pgbackrest --stanza=cora --type=full backup
```

```bash
pgbackrest --stanza=cora --type=diff backup
```

#### Restoring

Stop Postgres, run the command below, start Postgres. How you stop and
start it depends on the host, which is why only the middle step is
written out here. That middle step generates the recovery configuration
itself, into `postgresql.auto.conf`, which is the reason this tool was
chosen: there is nothing to hand-author while the beamline is down.

```bash
pgbackrest --stanza=cora --delta --type=time --target="2026-07-28 09:07:51+00" --target-action=promote restore
```

To recover everything rather than to a chosen moment, drop the `--type`
and `--target` arguments. To see what is available first:

```bash
pgbackrest --stanza=cora info
```

**`--delta` is not optional in practice.** pgBackRest's own help says the
data directory is "expected to be present but empty" without it, and a
restore into a populated PGDATA aborts with `ERROR: [040]: unable to
restore to path ... because it contains files`. Every real reason to
reach for this runbook (corruption, a bad migration, a wrong-image
deploy) leaves PGDATA fully populated, so a runbook without `--delta`
fails at exactly the moment it is needed. `--delta` instead compares
checksums and restores in place. It is also correct against an empty
directory, which is why the drill runs this same command after wiping
PGDATA; both paths are exercised.

Two properties of the target are worth knowing before you need them.
The backup set is selected by comparing its stop time to your target at
**whole-second resolution**, and the stop time must be strictly earlier,
so a target inside the same second as the backup finished is rejected
with "unable to find backup set with stop time less than". Name a target
at least a second later. And recovery stops at the first transaction that
committed after the target, so the target should sit between the last
event you want and the first you do not.

#### After a point-in-time restore, before anything else

`--target-action=promote` ends recovery and starts a **new timeline**,
which branches from the target. Two consequences an operator has to act
on, neither of which pgBackRest will prompt for:

- **Take a full backup immediately.** The stanza now holds a branch
  point, and later backups build on the new timeline.
- **`recovery_target_timeline` defaults to `latest`.** So a SECOND
  point-in-time restore after this one follows the branch by default,
  not the original history. If you need to reach a moment on the
  abandoned timeline, name it with `--target-timeline`. Its WAL is still
  in the repository; it is just no longer the default path.

And check the schema, which is the next subsection.

#### The drill

The restore path is exercised, not assumed:

```bash
make restore-drill
```

`scripts/restore_drill.py` stands up an isolated cluster on port 5433
(override with `CORA_DRILL_PORT`), applies the real Atlas migrations,
writes three known Run streams, deletes the contents of PGDATA, restores
to a chosen moment, and verifies the result. It never touches the dev
database on 5432.

The three streams are what make the verification mean something:

    Run A  ->  full backup  ->  Run B  ->  [target]  ->  Run C

Run A is inside the base backup. Run B is written afterwards, so only
replayed WAL can bring it back. Run C is written after the target and
must not return. A snapshot-only strategy recovers Run A and fails both
of the others.

Verification is at the domain level, which event sourcing makes possible
in a way most systems are not. "Postgres started" says nothing about
whether the record survived, so for the two streams that should come back
the drill hashes each one's ordered fold, in `version` order, the same
order the evolver reads, and compares the digests across the restore. A
restore that dropped, duplicated or reordered an event inside a stream
changes the digest even when the row count does not move.

Last executed 2026-07-28 against `pgvector/pgvector:pg18` and pgBackRest
2.58.0, with all 8 checks passing: Run A and Run B recovered with
matching fold digests and commit order intact, Run C absent, schema at
revision `20260713000000`.

Read the evidence at its real strength. Three of those checks carry the
claim: Run B's event sequence and fold digest, which only replayed WAL
can satisfy, and Run C's absence. The Run A pair would also pass under a
snapshot-only strategy. The remaining three, the Atlas revision and the
two commit-order checks, cannot fail in a state the drill constructs;
they are regression guards, not evidence.

The Run C check earns its place because the drill also asserts that Run
C's WAL segment reached the repository before the restore. Without that,
its later absence would be equally consistent with an archive that simply
stopped early.

#### Restoring an old backup under a newer image

Migrations are applied out of band by Atlas (`make migrate-apply`), a Go
binary that is deliberately not in the runtime image. So restoring a
backup taken before a migration, under an image built after it, leaves a
database whose schema is older than the code expects.

**CORA refuses to start in that state.** `build_kernel` reads the applied
migration version out of Atlas's own bookkeeping before it constructs
anything that can write, and compares it against the version the build
was written for. A mismatch fails the lifespan, which exits the process
with the two versions and the remedy on stderr. The two directions get
different remedies, because only one of them has one: a database BEHIND
the build is fixed by applying migrations, while a database AHEAD of it
cannot be, since forward-only means there is nothing to apply and the
answer is to run the right image.

That check exists because the failure it prevents is quiet rather than
loud. A missing column crashes and gets noticed. A migration that added a
CONSTRAINT, absent after a restore, leaves every write succeeding and
admits exactly the records the constraint existed to reject, into an
append-only log where they become history rather than rows to correct.

The check runs at boot, so the command below is now a way to see the same
answer before starting, and to see WHICH files are pending rather than
just that some are. After any restore:

```bash
LOCAL_DB_URL="postgres://cora:cora@<restored-host>:<port>/cora?sslmode=disable" make migrate-status
```

The override matters: `make migrate-status` alone reads `LOCAL_DB_URL`,
which defaults to the dev database on `localhost:5432`, so without it you
would inspect the wrong cluster and learn nothing about the one you just
restored.

A restored database that is current reports `Migration Status: OK` with
`Pending Files: 0`. One that predates a migration reports
`Migration Status: PENDING` and counts the files it is missing, and the
same override on `make migrate-apply` brings it forward. Migrations are
forward-only, so this direction always works; a backup NEWER than the
code has no equivalent remedy and means the wrong image is deployed.

The drill checks the restored revision too, but scope that honestly: it
migrates before it backs up, so its recovery targets all sit after every
migration and that check cannot fail in a state the drill constructs. It
confirms the schema came back with the data. The stale-schema case it
cannot reach is the one the boot gate covers.

##### Reading a restored database without migrating it

Sometimes the point of a restore is to look at old data, not to bring it
forward. Setting `ALLOW_SCHEMA_VERSION_MISMATCH=true` boots against a
mismatched schema instead of refusing, with the event store wrapped so
that every append raises and reads still work. `/readyz` reports
`"schema": "degraded"` for as long as the process runs that way.

Scope that precisely: what the override protects is the **event log**,
not every write. Each bounded context builds its own Postgres-backed
stores from the pool (inferences, activities, outcomes, observations,
and the projection workers), and those are not wrapped. The ordering is
deliberate rather than accidental: the event log is the append-only
record of truth and cannot be corrected once written, while everything
else is derived state a rebuild reconstructs from it. Protect the
irreversible thing first.

The asymmetry is the point: reading a database with the wrong schema
costs nothing, and writing to one cannot be undone. The override buys
inspection and never damage, so it is not a way to run a mismatched
deployment in production. `/readyz` keeps reporting `ready`, deliberately:
a degraded process serves reads correctly, and marking it unready would
have an orchestrator pull it from rotation and remove the access the
override was set to grant.

It does not cover a database with no schema at all. An override meant for
reading a restored database has nothing to offer an empty one, and
letting it through would boot a process that reports an empty database as
serviceable.

#### Limits, stated plainly

- **The repository target is not decided.** `repo1-type=posix` writes to
  local disk, which survives a database being dropped, corrupted, or
  wrongly migrated, and does not survive losing the host. It is the right
  starting point and the wrong ending point. The tool does not change
  when the target does: see the row in [Deferred](deferred.md).
- **Deferring the target defers repository encryption, and that one has
  a deadline.** Encryption is fixed when a stanza is created and cannot
  be added afterwards without deleting the stanza and every backup in it.
  Local disk on the database's own host is inside the same trust boundary
  as PGDATA, so it is reasonable to run unencrypted today, but the
  decision has to be made BEFORE the first backup at a shared or
  off-site target, not after. That deadline now has a mechanism, not
  just a sentence: `tests/unit/deployments/test_pgbackrest_conf.py`
  fails CI on any `repo1-type` other than `posix` that lacks a
  `repo1-cipher-type`, so re-pointing the repository without deciding
  encryption cannot merge.
- **Scheduling, expiry, alerting, and verification now exist as
  artifacts; installing them is the host's question.**
  `infra/backup/systemd/` carries four timers and their services:
  weekly full (Sun 02:00), daily differential (Mon..Sat 02:00), hourly
  `check` (a real WAL segment pushed through the archive and confirmed,
  which is the alert for a broken archive before it fills the volume),
  and weekly `verify` (Wed 03:00, every stored checksum read back, so
  bit rot surfaces on a timer rather than at the next restore, which is
  the worst time to learn about it). Retention is applied when a backup
  finishes, so the backup timers are also the expiry mechanism. Every
  unit routes failure through one `cora-backup-failure@.service` hook,
  which ships writing a high-priority journal line
  (`journalctl -p err -t cora-backup`) and is the single place a
  deployment attaches its pager. The units are INERT until copied to
  `/etc/systemd/system/` and enabled; whether the operating account may
  do that is HOST-5 on the 2-BM questions page, and a docker-shaped
  deployment invokes the same four commands through the compose tools
  profile on any scheduler it has. Until one of those happens, the
  cadence remains a recommendation, the repository grows without
  bound, and `pgbackrest --stanza=cora check` is the command an
  operator runs by hand to ask whether archiving works today.
- **The cluster's configuration files may not be in the backup.** pgBackRest
  backs up PGDATA. In the container layout used here `postgresql.conf`
  and `pg_hba.conf` live inside PGDATA and are included, but the
  Debian and Ubuntu packaged layout puts them under `/etc/postgresql/`,
  outside it. On that layout a host loss restores the data and loses the
  configuration, `archive_command` included. Back up `/etc/postgresql/`
  separately there.
- **Postgres major versions are not interchangeable.** A PG18 cluster
  will not start under a PG19 image, and the base image tag
  (`pgvector/pgvector:pg18`) pins only the major. After any major
  upgrade, `pgbackrest --stanza=cora stanza-upgrade` is required before
  the next backup will succeed.
- **The drill proves the mechanism, not the site.** It runs the real
  tool, the real image, the real schema and a real destruction, but on a
  Docker volume rather than on 2-BM's host and storage. Re-run it there
  once the host is chosen; that run is what makes the claim local.
- **Enable archiving and create the stanza together.** Postgres starts
  archiving the moment it boots with `archive_mode=on`, so a cluster
  brought up before `pgbackrest --stanza=cora stanza-create` logs a burst
  of `FileMissingError` failures against `archive.info` and retains the
  WAL it could not push. This is recoverable and looks alarming. Create
  the stanza as part of bringing the cluster up.

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
| Backup and point-in-time recovery | SHIPPED | pgBackRest, `infra/backup/`, drill in `scripts/restore_drill.py`; see "Backup and point-in-time recovery" above |
| Backup repository target | Deferred | Where the host can durably write. Carries two coupled decisions: a credential for the s3 and sftp targets (not for a mounted share), and repository encryption, which cannot be added after the first backup |
| Backup scheduling and archive alerting | Deferred | Decided with the orchestrator, which is where a timer and an alert belong |
| Schema-version assertion at boot | Deferred | Today the restore procedure carries this check, not the application. First restore of a backup that predates a migration |
| Image registry | Deferred | Where the orchestrator pulls from; decided with the orchestrator |
| Runtime orchestrator (k8s / Cloud Run / ECS / bare VMs) | Deferred | First non-local deployment |
| Event-sourced `ActorIdpBindings` (JIT Actor provisioning) | Deferred | First case where adding an operator is too high-friction via config-time bindings |
| `trust.check_others` permission separation | Watch item | When ABAC lands or first cross-tenant deploy |

Bootstrap policy, Surface decomposition, HTTP edge auth, permission queries, and MCP edge-auth parity are all in place.
