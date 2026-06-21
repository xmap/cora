"""Typed application configuration loaded from environment variables.

`Settings` is loaded once at process start (in `build_kernel`) and passed
to adapters that need values from it. Domain and application layers never read
environment variables directly.
"""

from typing import Literal
from uuid import UUID

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cora.infrastructure.auth.config import IdentityProviderConfig
from cora.infrastructure.control_port_route import ControlPortRoute

_ALLOWED_DATABASE_SCHEMES = ("postgresql://", "postgres://")

OtelExporter = Literal["otlp", "console", "none"]

# ComputePort substrate selector. Mirrors the operation-tier
# `ComputeSubstrate` in `cora.operation.adapters.compute_port_config`
# (a trivial 2-value Literal kept per tier rather than centralised in a
# new infrastructure module, since there is no shared route model the
# way ControlPort's `Substrate` rides `ControlPortRoute`).
ComputeSubstrate = Literal["in_memory", "local_process"]


class Settings(BaseSettings):
    """Application configuration. Reads from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "local"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://cora:cora@localhost:5432/cora"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    # HTTP
    # Default 1 MiB. JSON command bodies are tiny (a few hundred bytes
    # at most). The application middleware is defense in depth — production
    # deployments should also configure body limits at the reverse proxy
    # (for example nginx `client_max_body_size`) for transport-layer rejection.
    max_request_body_size_bytes: int = 1024 * 1024

    # Observability — OpenTelemetry
    # `none` keeps the global no-op tracer (used by tests so spans don't
    # accumulate across many `create_app()` instances). `console` writes
    # spans to stdout (handy for local dev). `otlp` exports to a
    # collector via the standard `OTEL_EXPORTER_OTLP_*` env vars
    # (we deliberately do NOT shadow them with our own setting so
    # existing OTel deployment tooling Just Works).
    # Resource attribute `service.name` defaults to `cora-api`; override
    # if the same code is deployed under multiple service identities.
    # Sampler ratio is only consulted when otel_exporter == "otlp"; the
    # console exporter always exports every span (development is loud
    # by design). 1.0 = sample everything; lower in high-traffic prod.
    otel_exporter: OtelExporter = "none"
    otel_service_name: str = "cora-api"
    otel_sampler_ratio: float = 1.0

    # Authorization — Trust BC wiring
    # When None, `build_kernel` wires `AllowAllAuthorize` and every
    # command is permitted (legacy default; matches dev/test). When
    # set to a UUID, `TrustAuthorize` is wired and gates every command
    # through that single Policy aggregate. Multi-policy resolution
    # via projections lands in a later phase; until then this is one
    # policy per deployment.
    #
    # The bootstrap migration seeded the System Bootstrap Policy at a
    # fixed UUID so production deployments can enable real authz with
    # a single env var instead of the old 3-step dance:
    #
    #   TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002
    #
    # The seed permits SYSTEM_PRINCIPAL_ID to call DefinePolicy +
    # RegisterActor on the nil conduit, bound to the seeded HTTP
    # Surface — the minimum needed to register a real admin Actor and
    # promote a real admin Policy.
    # The default stays None (AllowAllAuthorize) for now because
    # ~2400 tests pass arbitrary principal_ids; flipping the default
    # is gated on a test-fixture audit (memory:
    # project_bootstrap_policy_design.md, WI8).
    trust_policy_id: UUID | None = None

    # Production deployments behind an auth proxy that sets
    # `X-Principal-Id` should set this true: requests without the
    # header are then rejected with 401 instead of silently falling
    # back to `SYSTEM_PRINCIPAL_ID`. Default false matches the
    # dev / test posture where the fallback is convenient.
    # The startup check in `create_app()` refuses to boot when
    # `app_env` is production-tier ({"prod", "production", "staging"}) and
    # this is False, so a production-tier deployment cannot accidentally
    # launch with the permissive default.
    require_authenticated_principal: bool = False

    # Escape hatch for intentionally running the permit-everyone
    # `AllowAllAuthorize` stub (no command gating) in a production-tier
    # env, e.g. an airgapped single-operator pilot that genuinely wants
    # no authz. Default false: under production-tier `app_env`
    # ({"prod", "production", "staging"}) with no `trust_policy_id` set,
    # `create_app()` refuses to boot unless this is True, so such a
    # deployment cannot silently ship the permissive default. Other envs
    # ignore this (permissive is the dev / test posture). Mirrors the
    # per-IdP `allow_insecure_*` opt-in shape: the insecure choice is
    # allowed, but only as a conscious one.
    allow_permissive_authz: bool = False

    # Federation / event-signing posture.
    # The signing seam ships with in-memory adapters by default: the
    # crypto-free `InMemorySignaturePort` (federation envelope sign /
    # verify), the dict-backed `InMemoryPublishPort`, and the real-but-
    # ephemeral-key `InMemorySigner` (event provenance). These are the
    # documented test-tier stubs per memory:
    # project_federation_port_design.md, kept until the rule-of-two
    # adapter trigger fires; the wire-tier DSSE / COSE / SCITT verifiers
    # are deliberately deferred.
    #
    # The startup check in `create_app()` refuses to boot when
    # `app_env` is production-tier ({"prod", "production", "staging"},
    # the same set the authz guards key on) and any signing factory
    # still resolves to one of those stubs, so a production-tier
    # deployment cannot silently ship crypto-free signing (the
    # federation SignaturePort) or non-durable signatures (the
    # ephemeral-key event Signer). Set this true only for an environment
    # intentionally exercising the prod posture before the wire-tier
    # adapters land (e.g. a staging deployment).
    allow_insecure_inmemory_signing: bool = False

    # Projection worker
    # `projection_use_listen_notify=True` (default) wires the worker's
    # wake-up signal to LISTEN on the `events` channel emitted by the
    # AFTER INSERT trigger from migration 20260509120000. Latency from
    # event commit to projection write is ~tens of ms under normal load.
    # Flip to False to fall back to polling-only when LISTEN/NOTIFY's
    # global commit lock causes contention (per Recall.ai July 2025
    # incident; trigger documented in `memory/project_deferred.md` under
    # the NATS deferred entry). Polling fallback latency is bounded by
    # `projection_poll_interval_seconds`.
    projection_use_listen_notify: bool = True
    # Safety-net poll interval when NOTIFY mode is on (catches missed
    # signals from listener disconnect). Becomes the primary signal
    # when NOTIFY is off — recommended values are very different
    # between the two modes (5s with NOTIFY, 1-2s without). Floor of
    # 0.1s prevents accidental tight-loop misconfiguration.
    projection_poll_interval_seconds: float = 5.0

    # LLM provider — Agent BC wiring
    # When None, `build_kernel` wires no LLM and the Kernel
    # carries `llm=None`; subscribers that depend on the LLM (the
    # RunDebriefer subscriber) raise / log-and-skip when they
    # try to use it. The dev / test default of None matches the
    # `AllowAllAuthorize` / `AlwaysCoveredClearanceLookup` test-
    # bypass convention: tests don't need real API credentials.
    # Production deployments that ship RunDebriefer MUST set this;
    # the wire-up adds a startup gate that refuses
    # to register `run_debriefer_subscriber` when this is unset (so
    # the agent never runs blind).
    #
    # Read from `ANTHROPIC_API_KEY` env var (case-insensitive per
    # pydantic-settings; matches the bare-field-name convention
    # `APP_ENV` / `DATABASE_URL` / `TRUST_POLICY_ID` already follow).
    # `SecretStr` ensures the key is never serialised by `repr()`,
    # `str()`, or `model_dump_json()` (Pydantic redacts it to
    # `**********` in all three paths). Production deploys MUST
    # access the key via `.get_secret_value()` — only the
    # `AnthropicLLM` factory does this today. A watch-item
    # follow-up promotes `database_url` to the same shape so the
    # whole Settings surface is repr-safe.
    anthropic_api_key: SecretStr | None = None

    # Idempotency
    # `idempotency_ttl_hours` is read by the pruner background task
    # which periodically deletes idempotency_keys rows older than this.
    # Stripe's industry default is 24h; clients are expected to retry
    # within that window or accept that a duplicate request will hit
    # a fresh handler invocation. Set to 0 to disable the pruner
    # entirely (rows live forever — useful for forensic deployments).
    idempotency_ttl_hours: int = 24
    # `idempotency_lock_stale_seconds` is the threshold above which an
    # in-flight (locked) idempotency row is considered stale and re-
    # claimable. Covers the case where a process crashed mid-handler
    # and never released its lock. Default 60s is generous over typical
    # handler latency (~100ms) but short enough that a crashed worker's
    # locked rows recover within a minute.
    idempotency_lock_stale_seconds: int = 60

    # `run_supervisor_enabled` gates the RunSupervisor background runtime (the
    # first ACTIVE in-loop agent). Default off: deployments opt in explicitly.
    # `run_supervisor_tick_seconds` is the supervision cadence (>= 0.1s).
    run_supervisor_enabled: bool = False
    run_supervisor_tick_seconds: float = 30.0

    # `run_supervisor_resume_enabled` is a SEPARATE opt-in for the gated wind-up
    # (autonomous ResumeRun), so a deployment may run auto-hold without auto-
    # resume. Default off; requires run_supervisor_enabled too (the loop must
    # be running). `run_supervisor_resume_settle_ticks` is the anti-flap settle
    # window: the start-safety envelope must read good for this many consecutive
    # ticks before an autonomous resume fires (>= 1).
    run_supervisor_resume_enabled: bool = False
    run_supervisor_resume_settle_ticks: int = 2

    # `run_liveness_ceiling_seconds` gates the run-liveness shadow rule
    # inside the RunSupervisor loop: a Run that has been Running longer than this
    # (now - running_since) is flagged as possibly-hung. Default None = OFF (a
    # second off-gate above run_supervisor_enabled). No safe universal default
    # exists -- the implausible-runtime ceiling is a per-beamline fact an
    # operator sets on enable. Shadow v1 only LOGS would-flag; it records no
    # Decision and issues no command.
    run_liveness_ceiling_seconds: float | None = None

    # `caution_promoter_enabled` gates the CautionPromoter subscriber (the 2nd
    # ACTIVE agent). Default off: it is operational only once the
    # operator-retirement-memory guard lands (it must not re-create a Notice an
    # operator deliberately retired). The subscriber is deterministic and needs
    # no LLM, so it registers independently of ANTHROPIC_API_KEY.
    caution_promoter_enabled: bool = False

    # `clearance_expirer_enabled` gates the ClearanceExpirer background runtime
    # (the 3rd ACTIVE agent). Default off: deployments opt in explicitly.
    # `clearance_expirer_tick_seconds` is the sweep cadence (>= 0.1s); clearance
    # windows elapse on hour/day timescales so the default is far slower than the
    # RunSupervisor's beam-tracking cadence.
    clearance_expirer_enabled: bool = False
    clearance_expirer_tick_seconds: float = 300.0

    # `clearance_watcher_enabled` gates the ClearanceWatcher background runtime
    # (the 4th ACTIVE agent, first pure flag-only). Default off: deployments opt
    # in explicitly. `clearance_watcher_tick_seconds` is the sweep cadence
    # (>= 0.1s). `clearance_watcher_stale_after_seconds` is how long a clearance
    # may sit in Submitted/UnderReview/Approved before it is flagged; the real
    # review-turnaround SLA is a facility fact, so the default is only a
    # placeholder (the runtime is off by default and an operator sets it on
    # enable).
    clearance_watcher_enabled: bool = False
    clearance_watcher_tick_seconds: float = 300.0
    clearance_watcher_stale_after_seconds: float = 604800.0

    # Edge auth
    # `identity_providers` is the list of IdPs CORA accepts tokens
    # from. Empty (default) keeps the legacy X-Principal-Id-with-
    # SYSTEM-fallback shape; the bearer middleware uses this list
    # when populated. Production deployments set this via env
    # var as JSON, for example:
    #
    #   IDENTITY_PROVIDERS='[{"issuer":"https://idp.example.com",
    #     "jwks_url":"https://idp.example.com/jwks.json",
    #     "audiences":{"00000000-0000-0000-0000-000000000020":"https://cora.example/http"},
    #     "allowed_algorithms":["RS256"]}]'
    #
    # pydantic-settings parses the JSON automatically when the env
    # value starts with `[`. Schema validation runs at startup so
    # malformed config fails fast, not on first auth attempt.
    identity_providers: list[IdentityProviderConfig] = []

    # Federation BC — self-Facility identity (Session 5 Slice 5)
    # `self_facility_code` is the cross-deployment convergent slug for
    # THIS deployment's own Facility row, seeded at lifespan startup by
    # `bootstrap_federation` per [[project_facility_aggregate_design]].
    # The value is consumed by `FacilityCode(...)` at startup; any
    # violation of the alphanumeric-and-dash 1-32-char pattern raises
    # `InvalidFacilityCodeError` and fails the lifespan fast.
    #
    # Default `"cora"` matches the existing `facility_publisher: str = "CORA"`
    # placeholder convention; production deployments override with the
    # actual facility slug (for example `aps`, `maxiv`, `nsls2`) via
    # the `SELF_FACILITY_CODE` env var. Two CORA deployments that both
    # leave the default in place WILL collide on the same code when
    # federating, so production sets this without exception.
    self_facility_code: str = "cora"

    # Data BC — Distribution backfill (Session 6 Slice 2)
    # `self_facility_default_storage_supply_code` names the
    # storage-kind Supply that the lifespan-time Distribution
    # backfill binds every legacy `Dataset.uri` row to per
    # [[project_data_distribution_design]] L23 + L24. Read at
    # lifespan startup by `bootstrap_default_storage_supply`; resolved
    # against `proj_supply_summary` (must exist, must have
    # `kind == "Storage"`, must have `status == "Available"`). Default
    # `None` lets clean-install deployments boot without setting the
    # env var; when set the value is operator-supplied via the
    # `SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE` env var.
    #
    # Fail-loud surface (one lifespan error class per L23a with a
    # DefaultStorageSupplyBootstrapFailure discriminator):
    #   - unset + legacy Datasets exist -> CODE_UNSET
    #   - set + Supply missing (or wrong kind / wrong facility / ambiguous)
    #                                   -> NOT_FOUND
    #   - resolved Supply not Available -> NOT_AVAILABLE
    self_facility_default_storage_supply_code: str | None = None

    # Equipment BC — PIDINST integration (slice E.1)
    # `facility_publisher` is the institutional `publisher` field emitted
    # on every PIDINST record produced by `GET /assets/{asset_id}/pidinst`
    # per L13 of project_asset_persistent_id_design. Default "CORA" is a
    # placeholder; production deployments override with the operator
    # facility name (for example "Argonne National Laboratory").
    facility_publisher: str = "CORA"
    # `landing_page_template` is the URL template used by the PIDINST
    # view assembler to derive the per-asset landing page (PIDINST v1.0
    # Property 3) per L12. Carries the literal `{asset_id}` substitution
    # token; expanded via `str.format(asset_id=...)`. Default points at
    # a placeholder URL; production deployments override with the public
    # URL of their operator-facing asset landing page. Bootstrap fails
    # fast at startup when this is the empty string (see
    # `check_pidinst_landing_page_template`).
    landing_page_template: str = "https://cora.local/assets/{asset_id}/landing"

    # ControlPort routing — Operation BC Conductor
    # When empty (default), `wire_operation` builds an
    # `InMemoryControlPort` (legacy + test convenience: the conduct_procedure
    # endpoint is reachable but no real substrate is exercised). When
    # populated, `build_control_port` constructs a `ControlPortRegistry`
    # with each route's substrate adapter under its prefix; the
    # Conductor + registry handle longest-prefix dispatch.
    #
    # Read from `CONTROL_PORT_ROUTES` env var as JSON, for example:
    #
    #   CONTROL_PORT_ROUTES='[
    #     {"prefix":"2bma:cam1:image","substrate":"epics_pva"},
    #     {"prefix":"2bma:","substrate":"epics_ca"}
    #   ]'
    #
    # See `cora.infrastructure.control_port_route` for the route shape +
    # `cora.operation.adapters.control_port_config` for the factory.
    control_port_routes: list[ControlPortRoute] = []

    # ComputePort substrate selection for the conduct runtime.
    # `in_memory` (default) is the Simulated fake: the conduct surface
    # is reachable but every job is Simulated, so no real subprocess
    # runs (right for tests + a generic boot). `local_process` runs
    # compute jobs as OS subprocesses on the host via
    # `LocalProcessComputePort`. A single scalar, not a route table:
    # ComputePort has one real adapter and no routing registry (the
    # registry is the second-substrate trigger). Read from
    # `COMPUTE_SUBSTRATE` / `COMPUTE_DEFAULT_TIMEOUT_S`. See
    # `cora.operation.adapters.compute_port_config`.
    compute_substrate: ComputeSubstrate = "in_memory"
    compute_default_timeout_s: float = 3600.0

    # When True (default, migration window), the conduct endpoint still
    # accepts a raw caller-supplied `command` for a Method that has NO
    # launch_spec. A Method WITH a launch_spec always builds its argv
    # server-side and rejects a raw command regardless of this flag.
    # Flip to False to lock conduct to vetted launch_spec recipes only
    # once every Method carries one. Read from `CORA_ALLOW_RAW_CONDUCT`.
    # See [[project-method-launch-spec-stage0-design]].
    cora_allow_raw_conduct: bool = True

    # Enclosure permit observer (PSS-1, beam-availability slice).
    # Maps each Enclosure name to the read-only Channel Access PV whose
    # value drives its permit (e.g. S02BM-PSS:StaA:SecureM, 1=secure).
    # When empty (default) the enclosure monitor loop is a no-op and no
    # deployment enclosures are seeded, so a generic boot is unaffected.
    # Read from ENCLOSURE_PERMIT_PVS as JSON, for example:
    #
    #   ENCLOSURE_PERMIT_PVS='{
    #     "2-BM-A":"S02BM-PSS:StaA:SecureM",
    #     "2-BM-B":"S02BM-PSS:StaB:SecureM"
    #   }'
    #
    # The keys are the enclosures to seed (under self_facility_code) and
    # monitor; the values are their SecureM PVs. See
    # `cora.enclosure.adapters.control_port_enclosure_observer`.
    enclosure_permit_pvs: dict[str, str] = {}

    # Beam-availability pre-flight (BEAM-1, beam-availability slice).
    # Role -> read-only PV for the run / procedure start gate. `fes` and
    # `sbs` are the front-end and station-shutter BeamBlockingM PVs
    # (INVERTED: 0 = open); `fes_permit` is the ACIS upstream composite.
    # When empty (default) the gate is skipped (beam-by-default), so a
    # generic boot is unaffected. Read from BEAM_AVAILABILITY_PVS as JSON:
    #
    #   BEAM_AVAILABILITY_PVS='{
    #     "fes":"S02BM-PSS:FES:BeamBlockingM",
    #     "sbs":"S02BM-PSS:SBS:BeamBlockingM",
    #     "fes_permit":"SR-ACIS:2BM:FesPermitM"
    #   }'
    #
    # See `cora.operation.adapters.control_port_beam_availability_lookup`.
    beam_availability_pvs: dict[str, str] = {}

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        """Catch malformed DATABASE_URL at startup, not on first asyncpg call."""
        if not value.startswith(_ALLOWED_DATABASE_SCHEMES):
            schemes = " or ".join(_ALLOWED_DATABASE_SCHEMES)
            msg = (
                f"DATABASE_URL must start with {schemes} (got: {value[:40]!r}). "
                "asyncpg accepts both; SQLAlchemy-style 'postgresql+psycopg2://' "
                "URLs are not supported here."
            )
            raise ValueError(msg)
        return value

    @field_validator("otel_sampler_ratio")
    @classmethod
    def _validate_otel_sampler_ratio(cls, value: float) -> float:
        """Sampler ratio must be in [0.0, 1.0]; outside that range is meaningless."""
        if not 0.0 <= value <= 1.0:
            msg = f"otel_sampler_ratio must be in [0.0, 1.0], got {value}"
            raise ValueError(msg)
        return value

    @field_validator("projection_poll_interval_seconds")
    @classmethod
    def _validate_projection_poll_interval(cls, value: float) -> float:
        """Floor of 0.1s prevents accidental tight-loop misconfiguration."""
        if value < 0.1:
            msg = (
                f"projection_poll_interval_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the projection worker"
            )
            raise ValueError(msg)
        return value

    @field_validator("idempotency_ttl_hours")
    @classmethod
    def _validate_idempotency_ttl_hours(cls, value: int) -> int:
        """0 disables the pruner; negative values would invert the
        TTL window (always-prune-everything) so are rejected."""
        if value < 0:
            msg = f"idempotency_ttl_hours must be >= 0 (0 disables pruner), got {value}"
            raise ValueError(msg)
        return value

    @field_validator("idempotency_lock_stale_seconds")
    @classmethod
    def _validate_idempotency_lock_stale_seconds(cls, value: int) -> int:
        """Floor of 1s prevents a tight stale-lock recovery loop where
        every claim immediately considers prior locks stale."""
        if value < 1:
            msg = (
                f"idempotency_lock_stale_seconds must be >= 1, got {value}; "
                "values below 1s would treat every concurrent claim as stale"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_supervisor_tick_seconds")
    @classmethod
    def _validate_run_supervisor_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight supervision loop."""
        if value < 0.1:
            msg = (
                f"run_supervisor_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the supervisor"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_supervisor_resume_settle_ticks")
    @classmethod
    def _validate_run_supervisor_resume_settle_ticks(cls, value: int) -> int:
        """Floor of 1: a resume needs at least one good envelope read first."""
        if value < 1:
            msg = (
                f"run_supervisor_resume_settle_ticks must be >= 1, got {value}; "
                "an autonomous resume requires at least one good envelope read"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_liveness_ceiling_seconds")
    @classmethod
    def _validate_run_liveness_ceiling_seconds(cls, value: float | None) -> float | None:
        """None disables the run-liveness rule; a set ceiling must be
        positive (a non-positive ceiling would flag every Running Run at once)."""
        if value is not None and value <= 0:
            msg = (
                f"run_liveness_ceiling_seconds must be > 0 when set, got {value}; "
                "None disables the run-liveness rule"
            )
            raise ValueError(msg)
        return value

    @field_validator("clearance_expirer_tick_seconds")
    @classmethod
    def _validate_clearance_expirer_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight expiry-sweep loop."""
        if value < 0.1:
            msg = (
                f"clearance_expirer_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the expirer"
            )
            raise ValueError(msg)
        return value

    @field_validator("clearance_watcher_tick_seconds")
    @classmethod
    def _validate_clearance_watcher_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight watch-sweep loop."""
        if value < 0.1:
            msg = (
                f"clearance_watcher_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the watcher"
            )
            raise ValueError(msg)
        return value

    @field_validator("clearance_watcher_stale_after_seconds")
    @classmethod
    def _validate_clearance_watcher_stale_after_seconds(cls, value: float) -> float:
        """Must be positive: a non-positive window would flag every clearance."""
        if value <= 0:
            msg = (
                f"clearance_watcher_stale_after_seconds must be > 0, got {value}; "
                "a non-positive window would flag every front-of-lifecycle clearance"
            )
            raise ValueError(msg)
        return value
