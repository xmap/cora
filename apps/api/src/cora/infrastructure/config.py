"""Typed application configuration loaded from environment variables.

`Settings` is loaded once at process start (in `build_kernel`) and passed
to adapters that need values from it. Domain and application layers never read
environment variables directly.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cora.infrastructure.auth.config import IdentityProviderConfig
from cora.infrastructure.capture_scan_ingestor_binding import CaptureScanIngestorBinding
from cora.infrastructure.control_port_route import ControlPortRoute
from cora.shared.capture_phase import CapturePhase
from cora.shared.storage_root import normalize_storage_root, require_nonempty_absolute_root


class BlepsSupplyChannelConfig(BaseModel):
    """One BLEPS channel bound to the Supply it feeds.

    Typed rather than a bare dict so a missing or misspelled key is a
    startup validation error naming the field, instead of a `KeyError`
    raised deep inside the lifespan with the whole boot failing around it.

    `supply` is the Supply name this channel contributes to; `trip` is the
    process-axis PV; `fault` is the optional trust-axis PV (that same
    channel's instrumentation fault). `warning` is the optional, less-
    severe process-axis PV on the same physical quantity (e.g.
    `Flow2.Under_Range_Warning`); it is read from config unconditionally,
    but `main.py` only passes it through to `BlepsChannel` when
    `bleps_supply_warnings_enabled` is set, so declaring it here has no
    effect until that flag is on. `label` is what an operator reads in
    the transition reason, and defaults to the trip PV when omitted.
    """

    supply: str
    trip: str
    fault: str = ""
    warning: str = ""
    label: str = ""


_ALLOWED_DATABASE_SCHEMES = ("postgresql://", "postgres://")

# Closed role vocabulary for `Settings.capture_experiment_identity_pvs`
# (slice 14a), dispatched on by name in
# `cora.api._capture_experiment_identity_reader`.
_EXPERIMENT_IDENTITY_ROLES = frozenset({"proposal_number", "esaf_number", "esaf_doi_number"})

OtelExporter = Literal["otlp", "console", "none"]

# ComputePort substrate selector. Deliberately NARROWER than the
# operation-tier `ComputeSubstrate` in
# `cora.operation.adapters.compute_port_config`, which is a 3-value
# Literal (adds `globus`). `globus` is excluded here on purpose: it
# cannot be built from a flat config string (it needs an authorized
# client + endpoint id + a remote artifact probe), so it is injected as
# a prebuilt port at the composition root, never selected via this env
# var. This tier therefore names only the substrates a deployment can
# actually pick with `COMPUTE_SUBSTRATE`. Kept per-tier rather than
# centralised because there is no shared route model the way
# ControlPort's `Substrate` rides `ControlPortRoute`.
#
# `derive_actuation` (cora.api._readiness) reads this as an allowlist
# (`== "in_memory"` is the only provably-inert value), so if a real
# selectable substrate is ever added here, it correctly reads as
# actuation-reachable by default.
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

    # Escape hatch for booting against a schema this build does not
    # expect. Default false: `build_kernel` refuses to start when the
    # applied migration version is not `EXPECTED_SCHEMA_VERSION`, which
    # is the state a restore leaves behind (see
    # `cora.infrastructure.schema_version`).
    #
    # Setting it True does NOT restore normal service. The process boots
    # with its event store wrapped in `ReadOnlyEventStore`, so a restored
    # database can be read and nothing can be appended to it. That
    # asymmetry is the whole point: the event log is append-only, so a
    # write against the wrong schema is history rather than a row to fix,
    # while a read costs nothing.
    #
    # It does not cover a database with NO schema. An override meant for
    # reading a restored database has nothing to offer an empty one, and
    # letting it through would boot a process that reports an empty
    # database as fine.
    allow_schema_version_mismatch: bool = False

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

    # `llm_enabled` is the SWITCH; `anthropic_api_key` below is the
    # CREDENTIAL. Both are required before CORA calls an external model,
    # and this one defaults OFF.
    #
    # Why a switch at all, when a key is already needed: the key is often
    # present in an environment for an unrelated reason, and its mere
    # presence used to be enough to auto-register RunDebriefer +
    # CautionDrafter, which call an external API on EVERY terminal Run.
    # That is experiment metadata leaving the facility (EGRESS) and money
    # being spent (SPEND), switched on by a side effect. Every one of the
    # ~13 sibling subscribers carries its own `*_enabled` default-off
    # flag; this seam was the outlier.
    #
    # Egress and spend are a DIFFERENT axis from actuation (the
    # ControlPort write gate and the ComputePort exec allowlist, see
    # `control_writes_enabled`). A facility told "read-only, CORA cannot
    # touch my hardware" hears a claim about actuation, and would still
    # be unhappy to discover CORA phoned its data out. Both promises
    # belong to the observe-only posture; neither subsumes the other.
    #
    # Turning this off is graceful, never a crash: `build_llm` returns
    # None, and every consumer already treats `llm=None` as a supported
    # state because the key-absent case always produced it. The
    # LLM-backed subscribers log-and-skip and `regenerate_run_debrief`
    # answers unavailable. The `llm` decide substrate is not selectable
    # over the wire at all, so its factory guard is an internal-caller
    # guard rather than a request-reachable path.
    llm_enabled: bool = False

    # LLM provider — Agent BC wiring
    # When None (or when `llm_enabled` is False above), `build_kernel`
    # wires no LLM and the Kernel carries `llm=None`; the LLM-backed
    # subscribers log-and-skip rather than refusing to boot, so a
    # deployment may defer Agent rollout. The dev / test default of None
    # matches the `AllowAllAuthorize` / `AlwaysCoveredClearanceLookup`
    # test-bypass convention: tests don't need real API credentials.
    # Production deployments that ship RunDebriefer MUST set BOTH this
    # and `llm_enabled`.
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

    # `llm_provider` selects the LLM adapter the composition root
    # builds: `anthropic` (the external, token-billed default), `argo`
    # (Argonne's internal gateway, which buys the same vendor models
    # through facility-funded infrastructure), or `local` (a
    # facility-hosted open model over an OpenAI-compatible endpoint).
    # All three debit the same beamline envelope at the catalog's rate
    # for the entry, which is what makes the envelope source-agnostic.
    llm_provider: Literal["anthropic", "argo", "local"] = "anthropic"

    # `run_debriefer_agent_id` / `caution_drafter_agent_id` let a deployment
    # designate WHICH Agent each LLM subscriber acts as, instead of always
    # acting as the seeded singleton (`RUN_DEBRIEFER_AGENT_ID` /
    # `CAUTION_DRAFTER_AGENT_ID`). Unset (None, the default) means the seeded
    # singleton, so nothing changes on upgrade. The named Agent must already
    # exist, defined through the gated `define_agent` path: this setting only
    # SELECTS among Agents that already passed that gate, the same way
    # `run_initiator_plan_id` below selects among Plans rather than
    # declaring one. A deployment whose configured `llm_provider` cannot
    # reach the seeded agents' declared provider (eg. `anthropic` from a
    # controls network with no internet) defines its own Agent against a
    # reachable provider and names it here.
    run_debriefer_agent_id: UUID | None = None
    caution_drafter_agent_id: UUID | None = None

    # Bought-through-gateway path. Argo authenticates with a bare ANL
    # domain username in the API-key position, so there is no issued
    # credential to rotate; it is held as a SecretStr anyway because it
    # travels in the same header an API key would and should not reach
    # a log through a stray repr. Prefer a service account over a person:
    # Argo records it separately in usage tracking, so an unattended
    # deployment's calls are attributable to the application rather than
    # mixed into someone's personal usage. The service account still
    # belongs to the ANL account and division that registered it, so
    # this separates attribution rather than ownership.
    argo_username: SecretStr | None = None
    argo_base_url: str = "https://apps.inside.anl.gov/argoapi"

    # In-house (built) serving path. The `local` branch requires
    # `local_llm_base_url` and `local_llm_model`, or `build_llm` returns
    # None and subscribers fail-fast. `local_llm_gpu_usd_per_hour` feeds
    # the GPU shadow-cost observability signal (0 = no shadow cost), and
    # `local_llm_device_id` labels the served device in the meter.
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    local_llm_gpu_usd_per_hour: float = 0.0
    local_llm_device_id: str = "gpu0"

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

    # `run_supervisor_envelope_hold_enabled` is a SEPARATE opt-in widening the
    # hold trigger beyond beam: a Running Run also holds when a non-beam
    # start-safety gate (clearance, supply, or enclosure -- the same four
    # gates `check_safety_envelope` enforces at start, minus beam, which the
    # v1 hold rule already covers) confirms-fails and stays failed through
    # the settle window below. Default off: this pays for a full envelope
    # assembly (aggregate loads + cross-BC lookups) per Running Run per tick
    # whenever beam is open, a real cost the v1 beam-only hold never paid.
    # `run_supervisor_envelope_hold_settle_ticks` is its own anti-flap window
    # (>= 1), separate from the resume settle window above: a transient
    # eventual-consistency miss on one aggregate load must not hold a Run
    # that a moment later reads fine.
    run_supervisor_envelope_hold_enabled: bool = False
    run_supervisor_envelope_hold_settle_ticks: int = 2

    # `run_supervisor_advise_enabled` promotes the supervisor's shadow rules
    # (run-liveness, signal-quality, signal-stall) one rung from observe to
    # advise: on each breach EDGE the supervisor records ONE
    # Decision(context=RunSupervision, choice=SupervisionQuieted/Stalled/
    # Breached) for a human, still issuing NO command. Default off, a further
    # opt-in above each rule's own enable (a rule with no channel / ceiling
    # configured stays silent regardless). Shadow logging continues unchanged;
    # advise only adds the edge-triggered Decision.
    run_supervisor_advise_enabled: bool = False

    # `run_liveness_ceiling_seconds` gates the run-liveness shadow rule
    # inside the RunSupervisor loop: a Run that has been Running longer than this
    # (now - running_since) is flagged as possibly-hung. Default None = OFF (a
    # second off-gate above run_supervisor_enabled). No safe universal default
    # exists -- the implausible-runtime ceiling is a per-beamline fact an
    # operator sets on enable. Shadow v1 only LOGS would-flag; it records no
    # Decision and issues no command.
    run_liveness_ceiling_seconds: float | None = None

    # `run_supervisor_truncate_enabled` is the ACT rung of the run-liveness rule:
    # a SEPARATE opt-in (default off) above `run_liveness_ceiling_seconds` that
    # lets the supervisor autonomously issue TruncateRun (the terminal,
    # partial-data exit) for a Run that has stayed past the operator ceiling. It
    # is inert unless the ceiling is set (the rule's own gate) AND
    # run_supervisor_enabled is on. `run_supervisor_truncate_settle_ticks` is the
    # anti-flap settle window: the Run must read liveness-stale for this many
    # CONSECUTIVE ticks before the terminal truncate fires (>= 1), so a
    # transiently-stale or recovering Run is never killed. Truncate is terminal,
    # so the default settle is higher than the resume wind-up's.
    run_supervisor_truncate_enabled: bool = False
    run_supervisor_truncate_settle_ticks: int = 3

    # ACT rungs for the two observation rules (Rule Q quality, Rule R stall),
    # each a SEPARATE opt-in (default off) above its rule's own channel gate and
    # run_supervisor_enabled. When on, the supervisor escalates from advise to a
    # terminal command after the breach persists for the settle window:
    #   - Rule Q (data below the quality limit) -> AbortRun (data suspect).
    #   - Rule R (data stopped arriving) -> StopRun (data to the cutoff valid).
    # The `*_settle_ticks` are anti-flap windows: the breach must read for this
    # many CONSECUTIVE ticks before the terminal command fires (>= 1), so a
    # transient dip or a recovering Run is never killed. (Rule R also has its own
    # `run_stall_hysteresis_ticks` BEFORE it flags; the act settle is on top.)
    run_supervisor_quality_act_enabled: bool = False
    run_supervisor_quality_settle_ticks: int = 3
    run_supervisor_stall_act_enabled: bool = False
    run_supervisor_stall_settle_ticks: int = 2

    # Observation-signal closed-loop rules (SHADOW, inside the RunSupervisor
    # loop; [[project_observation_signal_port_design]]). Both default OFF and
    # are a second off-gate above run_supervisor_enabled.
    #
    # Rule Q (quality-within-limits) is active for a Run iff
    # `run_quality_channel_name` is set AND the Run's precomputed snr_limit is
    # non-NULL. It flags when the channel's latest value is below the limit.
    #
    # Rule R (rate-dropout / stall) is active for a Run iff
    # `run_stall_channel_name` is set AND the Run's precomputed
    # expected_observation_interval_seconds is non-NULL AND
    # `run_feed_heartbeat_ceiling_seconds` is set (the dead-feeder anchor). It
    # flags when no values arrived for `run_stall_window_factor` x the expected
    # interval, while the beam is up and the feeder heartbeat is fresh, for
    # `run_stall_hysteresis_ticks` consecutive ticks (anti-flap for top-ups).
    # The channel names are deployment facts (which PV is the quality / progress
    # channel); no safe universal default exists.
    run_quality_channel_name: str | None = None
    run_stall_channel_name: str | None = None
    run_stall_window_factor: float = 3.0
    run_stall_hysteresis_ticks: int = 2
    run_feed_heartbeat_ceiling_seconds: float | None = None

    # `run_initiator_enabled` gates the RunInitiator background runtime: the
    # agent that autonomously STARTS Runs (vs the RunSupervisor, which watches
    # in-flight ones). Default off. `run_initiator_tick_seconds` is the initiation
    # cadence (>= 0.1s); `run_initiator_max_in_flight` caps how many Runs may be
    # in flight at once (>= 1; one-stage CT keeps it at 1). `run_initiator_plan_id`
    # is the BOOT-TIME FALLBACK recipe Plan: the loop prefers the runtime
    # designation on the agent (`target_plan_id`, set by update_agent_target_plan)
    # and falls back to this when none is designated. None here just means no
    # fallback; the loop still runs when enabled and idles until a Plan is
    # designated at runtime.
    run_initiator_enabled: bool = False
    run_initiator_tick_seconds: float = 30.0
    run_initiator_max_in_flight: int = 1
    run_initiator_plan_id: UUID | None = None

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

    # `calibration_watcher_enabled` gates the CalibrationWatcher background
    # runtime (7th seeded agent, deterministic flag-only). Default off:
    # deployments opt in explicitly. `calibration_watcher_tick_seconds` is the
    # sweep cadence (>= 0.1s). `calibration_watcher_stale_after_seconds` is how
    # long a Provisional calibration may sit unverified (measured from its newest
    # revision) before it is flagged; the real re-verification interval is a
    # facility fact, so the default is only a placeholder (off by default; an
    # operator sets it on enable).
    calibration_watcher_enabled: bool = False
    calibration_watcher_tick_seconds: float = 300.0
    calibration_watcher_stale_after_seconds: float = 2592000.0

    # `procedure_watcher_enabled` gates the ProcedureWatcher background runtime
    # (8th seeded agent, deterministic flag-only). Default off: deployments opt in
    # explicitly. `procedure_watcher_tick_seconds` is the sweep cadence (>= 0.1s).
    # `procedure_watcher_stale_after_seconds` is how long an in-conduct procedure
    # (Running / Held) may sit without progressing before it is flagged; live
    # conduct is far shorter-lived than a clearance or calibration, so the default
    # is an hour (off by default; an operator sets the real window on enable).
    procedure_watcher_enabled: bool = False
    procedure_watcher_tick_seconds: float = 300.0
    procedure_watcher_stale_after_seconds: float = 3600.0

    # `campaign_watcher_enabled` gates the CampaignWatcher background runtime
    # (9th seeded agent, deterministic flag-only). Default off: deployments opt in
    # explicitly. `campaign_watcher_tick_seconds` is the sweep cadence (>= 0.1s).
    # `campaign_watcher_stale_after_seconds` is how long a campaign may sit Held
    # (operator-paused) without being resumed or closed before it is flagged; a
    # forgotten pause is a slow failure, so the default is a week (off by default;
    # an operator sets the real window on enable).
    campaign_watcher_enabled: bool = False
    campaign_watcher_tick_seconds: float = 300.0
    campaign_watcher_stale_after_seconds: float = 604800.0

    # `watcher_authz_strict` governs every watcher agent's STARTUP read-grant
    # probe (shared across the flag-only watchers + the acting agents). Each tick
    # a watcher issues an authz-gated list read; under a real Authorize policy a
    # missing grant for the agent principal silently blinds the watchdog (a
    # worse-than-none failure). At startup an ENABLED watcher probes that grant:
    # default (False) logs a loud `<watcher>.read_unauthorized_at_startup`
    # warning and starts anyway; True escalates a denied probe to a boot refusal
    # for any enabled-but-blind watcher. The per-tick runtime warning is emitted
    # regardless. No-op under a permissive Authorize (dev/test).
    watcher_authz_strict: bool = False

    # `liveness_posture` governs whether the authorization gate reads
    # `Actor.active` for the calling principal, the switch an operator flips
    # with deactivate_actor / reactivate_actor. Three states, because
    # measuring must be possible without refusing:
    #   - "off"     (default) the gate performs no liveness read at all, and
    #               `Conjunct.LIVENESS` never appears in a result.
    #   - "shadow"  resolve and log every non-active caller WITHOUT denying.
    #               This is the adoption measurement: how many live requests
    #               would enforcement have refused, and which remedy each
    #               would have needed. Run it for a full beamtime cycle
    #               before "enforce".
    #   - "enforce" a deactivated or unregistered principal is denied even
    #               where the Policy permits it.
    # Default "off" because turning this on refuses requests that succeed
    # today, and the human-envelope design requires the measurement to
    # precede the enforcement rather than follow it.
    liveness_posture: Literal["off", "shadow", "enforce"] = "off"

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

    # Data BC — in-band checksum verification (record_attestation).
    # `posix_checksum_roots` is the allowlist of absolute filesystem roots
    # the POSIX (file://) ChecksumVerifier may read. Empty (default)
    # disables POSIX verification entirely: a file:// Distribution URI then
    # lands at ChecksumVerifierUnsupportedSchemeError (HTTP 400), so a
    # deployment whose host cannot reach the bytes ships nothing readable
    # by accident. Set it ONLY where CORA's host actually mounts the
    # storage; the adapter refuses any path whose resolved realpath is
    # outside these roots (path-traversal and symlink-escape safe). Read
    # from POSIX_CHECKSUM_ROOTS as JSON, for example:
    #
    #   POSIX_CHECKSUM_ROOTS='["/gpfs/2bm/archive","/local/data"]'
    #
    # See `cora.data.adapters.posix_checksum`.
    posix_checksum_roots: tuple[str, ...] = ()

    # End-to-end budget for one POSIX digest walk, seconds. The bound
    # exists so a file on a hung mount, or one still growing, cannot
    # occupy a worker indefinitely; it is not a performance knob.
    #
    # The 60 s default suits the small files the adapter was written
    # against and is far too short for a tomography scan. Measured on
    # the 2-BM pilot: `sha256sum` alone takes 82 s on a 24.5 GB scan
    # (77 s of it CPU), and CORA's chunked read is slower still, so the
    # first real ingest refused with `walk exceeded max_walk_seconds`.
    # A deployment holding files of that size raises this to something
    # that bounds a hang without forbidding its own data. Read from
    # POSIX_CHECKSUM_MAX_WALK_SECONDS.
    posix_checksum_max_walk_seconds: float = 60.0

    # Data BC -- which of a scan file's timestamps is the acquisition
    # time. `start_date` (the default) preserves the behaviour every
    # deployment had before this setting existed.
    #
    # A deployment overrides it when its writer emits a timestamp that
    # is wrong rather than merely different. At 2-BM, measured across
    # six consecutive files, `start_date` is the PREVIOUS scan's
    # `end_date` because the areaDetector timestamp attribute refreshes
    # only while frames flow; `end_date` is correct to within seconds of
    # the file's own close. Ingesting there without `end_date` records a
    # capture time that is wrong by however long the gap between scans
    # was, and the policy that a file value beats an operator's means
    # nobody can correct it afterwards.
    #
    # The value is validated against the layout's own timestamp set by
    # the reader, which refuses a name the layout does not offer rather
    # than silently reading nothing. Read from
    # SCAN_CAPTURED_AT_SOURCE.
    scan_captured_at_source: str = "start_date"

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

    # Deployment-wide control-write switch. False (default) means CORA
    # may observe every configured route but drives none: every adapter
    # `build_control_port` hands the registry is wrapped in a
    # `ReadOnlyControlPort`, so a write raises
    # `ControlWritesDisabledError` before any substrate is contacted.
    #
    # Default-deny is deliberate and is the safety mechanism behind an
    # observe-only deployment (the APS 2-BM pilot posture). It cannot be
    # partially applied: it admits no per-substrate or per-route
    # exemption, so a config that forgets something fails closed rather
    # than silently driving hardware. `ControlPortRoute.read_only` is
    # the per-route counterpart, but it defaults to writable and so is
    # expressiveness within a writable deployment, NOT a safety gate.
    #
    # A deployment that drives hardware sets `CONTROL_WRITES_ENABLED=true`
    # once, on purpose. Local development and tests that exercise writes
    # through Settings must set it too; that keystroke is the point.
    control_writes_enabled: bool = False

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

    # Exactly what the `local_process` substrate may spawn. Empty
    # (default) permits NOTHING, so selecting local_process without
    # naming an executable yields a port that refuses every job rather
    # than one that runs any. The CHECK matches command[0] exactly: no
    # PATH resolution, no basename fallback. Read from
    # `COMPUTE_PERMITTED_EXECUTABLES` as JSON, for example:
    #
    #   COMPUTE_PERMITTED_EXECUTABLES='["/opt/conda/bin/tomopy"]'
    #
    # Declare ABSOLUTE paths. The check is exact, but the spawn still
    # PATH-resolves a bare name afterwards, so allowlisting `tomopy`
    # permits whatever PATH finds then. A request cannot reach that (the
    # conduct body carries no env), but a writable PATH entry on the
    # host would still decide what runs.
    #
    # Allowlist TOOLS, never interpreters: permitting `python` or `sh`
    # re-opens arbitrary execution via `-c`, and the check cannot tell.
    # This bounds WHAT runs; it does not authorize the conduct path (no
    # Trust policy gates the spawn). See `cora_allow_raw_conduct` below
    # and docs/stack/deployment.md.
    compute_permitted_executables: frozenset[str] = frozenset()

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
    # `cora.api._enclosure_permit_observer`.
    enclosure_permit_pvs: dict[str, str] = {}

    # Permit probe trail (coverage-window commissioning ladder item 3;
    # [[project_enclosure_permit_probe_design]]). Bounds how often
    # `ControlPortEnclosureObserver` re-reads each configured permit PV
    # independent of push traffic, so a quiet PV (EPICS CA monitors are
    # change-only) does not leave a probe-trail gap that reads as a
    # coverage outage when CORA was in fact still watching. `None`
    # (default) disables polling entirely: the trail is then push-only,
    # written only when the substrate itself sends something. This is an
    # OPERATIONAL KILL SWITCH, not just a test-determinism convenience:
    # setting it back to `None` stops the periodic read against the PSS
    # gateway (a shared facility resource) without any other code change,
    # and is the correct rollback for this feature if the poll cadence
    # ever needs revisiting. Confirm a cadence with beamline staff before
    # setting this in a deployment: it polls a facility resource on a
    # timer. Irrelevant when `enclosure_permit_pvs` is empty.
    enclosure_permit_probe_tick_seconds: float | None = None

    # Bounds how long boot waits for the permit monitor's first settled read
    # per configured enclosure before serving requests (the startup-race
    # window documented in `cora.enclosure._monitor`, "Startup race"). A PV
    # that has not settled by the deadline does not delay boot further: the
    # monitor keeps retrying in the background and that enclosure's existing
    # `permit_status` stands. Irrelevant when `enclosure_permit_pvs` is empty.
    #
    # `main.py` always passes this value explicitly, so it is the LIVE
    # default; `_monitor._STARTUP_TIMEOUT_SECONDS` only covers a caller that
    # skips Settings entirely. Keep both above EpicsCaControlPort's own
    # `_DEFAULT_TIMEOUT_S` (5.0s): a dead PV's per-code settlement needs
    # room to finish before this outer bound gives up, or a dead-PV boot
    # always falls through to the blunter warn-and-proceed path. These two
    # defaults drifted out of sync once already; if you change one, change
    # both.
    enclosure_permit_monitor_startup_timeout_seconds: float = 8.0

    # BLEPS supply observer (BLEPS-1/2/3, #562-#564). Equipment-protection
    # channels whose trips drive a Supply's status. Each entry binds one
    # BLEPS channel to the Supply it feeds:
    #
    #   BLEPS_SUPPLY_CHANNELS='[
    #     {"supply":"2-BM cooling water",
    #      "label":"Flow2 (M1 and DMM circuit)",
    #      "trip":"2bmBLEPS:BLEPS:FLOW2_TRIP",
    #      "fault":"2bmBLEPS:BLEPS:FLOW2_OVER_RANGE",
    #      "warning":"2bmBLEPS:BLEPS:FLOW_2_UNDER_WRN"},
    #     {"supply":"2-BM beamline vacuum",
    #      "label":"Vacuum section 1",
    #      "trip":"2bmBLEPS:BLEPS:VS1_TRIP"}
    #   ]'
    #
    # Those are the REAL 2-BM PV names, read off the running IOC on
    # 2026-08-23, not names derived from the PLC tags. The tags use dots
    # and the PVs are abbreviated inconsistently: PLC
    # `Flow2.Below_Set_Point_Trip` is `FLOW2_TRIP`, and its sibling
    # warning `Flow2.Under_Range_Warning` is `FLOW_2_UNDER_WRN`, with an
    # underscore before the digit that the trip does not have. An earlier
    # version of this example spelled them out longhand and none of those
    # PVs exist, so the config it suggested would have bound nothing.
    # `iocBoot/ioc2bmBLEPS/dbl-all.txt` is the authoritative list.
    #
    # A typed model rather than bare dicts, because a missing key used to
    # surface as a `KeyError` inside the lifespan, which fails the whole
    # boot with nothing naming the offending entry.
    #
    # `trip` is the process axis: the measured value crossed its limit, or
    # a valve disobeyed. `fault` is the OPTIONAL trust axis, the same
    # channel's instrumentation fault; while it stands, that channel is
    # excluded from its Supply's verdict rather than obeyed. Many channels
    # per Supply is the normal case (eight cooling circuits, seven vacuum
    # sections); the failing channel's `label` lands in the transition
    # reason. When empty (default) the supply monitor loop is a no-op, so
    # a generic boot is unaffected.
    #
    # Read-only is enforced STRUCTURALLY, not by naming discipline: the
    # composition root wraps the observer's port in `ReadOnlyControlPort`,
    # so it cannot write whatever the route table says. That matters
    # because route-level `read_only` defaults False, so a `2bmBLEPS:`
    # route in a writes-enabled deployment would otherwise accept writes.
    # `test_bleps_binding_is_read_only` is a tripwire against an
    # accidental hardcode of a BLEPS write PV; it greps names and makes
    # nothing read-only. See `cora.api._bleps_supply_observer`.
    bleps_supply_channels: list[BlepsSupplyChannelConfig] = []

    # The BLEPS system's own communications flag (PLC to EtherNet/IP
    # gateway). While it is asserted, or while it cannot be believably
    # read, NO BLEPS observation is recorded: a reading we cannot trust
    # must not overwrite a Supply's status with a guess. Read from
    # BLEPS_COMMUNICATIONS_FAULT_PV, for example
    # `2bmBLEPS:BLEPS:COMMUNICATIONS_FAULT`. Empty (default) disables the
    # system-wide trust gate, which is only correct when no BLEPS channels
    # are configured either; `_require_communications_fault_pv_with_bleps_channels`
    # enforces that pairing rather than leaving it as a comment.
    bleps_communications_fault_pv: str = ""

    # Whether a configured channel's optional `warning` PV is passed
    # through to the observer at all. Default false: nobody has measured
    # how often BLEPS warnings latch at 2-BM, and a channel that warns
    # routinely would park its Supply in `Degraded` semi-permanently,
    # which fails the run-start supply gate (`Degraded` does not satisfy
    # it). `main.py` reads this flag when building each `BlepsChannel`;
    # the observer itself is unconditionally warning-aware and has no
    # setting of its own. Flip a deployment to True to observe the real
    # base rate directly instead of asking staff to estimate it. See
    # `cora.api._bleps_supply_observer`'s "Warnings, gated off by
    # default" section.
    bleps_supply_warnings_enabled: bool = False

    @model_validator(mode="after")
    def _require_communications_fault_pv_with_bleps_channels(self) -> "Settings":
        """BLEPS channels without the comms flag would trust a dark feed.

        The comms flag is the only signal that says the whole BLEPS
        reading is stale. Configuring channels without it silently
        disables the system-wide trust gate, which is the one failure
        mode where CORA keeps asserting a Supply's status from readings
        that stopped arriving.
        """
        if self.bleps_supply_channels and not self.bleps_communications_fault_pv:
            raise ValueError(
                "BLEPS_SUPPLY_CHANNELS is configured without "
                "BLEPS_COMMUNICATIONS_FAULT_PV; the comms flag is what makes a "
                "stale BLEPS feed detectable, so channels without it would be "
                "trusted indefinitely"
            )
        return self

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

    # Capture-observe seam (2-BM commissioning ladder rung 1: watch a
    # TomoScan capture live rather than learn of it from a staged file).
    # Outer key is the capture code (2-BM runs several tomoscan variants
    # off the same base class, e.g. tomoscan_2bm / tomoscan_2bm_step /
    # tomoscan_fpga_2bm; each gets its own code); inner dict is
    # role -> read-only PV. `status` is the only role every variant must
    # provide; the rest are optional per variant. When empty (default)
    # the capture-watch runtime is a no-op, so a generic boot is
    # unaffected. Read from CAPTURE_WATCH_PVS as JSON:
    #
    #   CAPTURE_WATCH_PVS='{
    #     "2bmb-tomoscan": {
    #       "status": "2bmb:TomoScan:ScanStatus",
    #       "server_running": "2bmb:TomoScan:ServerRunning",
    #       "abort": "2bmb:TomoScan:AbortScan",
    #       "images_saved": "2bmb:TomoScan:ImagesSaved",
    #       "images_collected": "2bmb:TomoScan:ImagesCollected",
    #       "testing": "2bmb:TomoScan:Testing",
    #       "full_file_name": "2bmSP2:HDF1:FullFileName_RBV"
    #     }
    #   }'
    #
    # `status` is a DBR_CHAR waveform at 2-BM; the deployment's
    # CONTROL_PORT_ROUTES must declare it in `text_addresses` or it
    # decodes as raw bytes, not text. `testing` (slice 11, optional per
    # code) is a DBR_ENUM, the same record type as `abort`: whether
    # tomoscan is bypassing its own beam preconditions for this capture,
    # carried onto the witnessed genesis, never onto
    # `Observation.is_simulated`. See `cora.api._capture_observer`.
    #
    # `full_file_name` (slice 13, optional per code) is ALSO a DBR_CHAR
    # waveform needing a `text_addresses` declaration, but deliberately
    # NOT `2bmb:TomoScan:FullFileName` (tomoscan's own mirror of it):
    # upstream `end_scan()` writes that PV four statements AFTER the
    # `ScanStatus='Scan complete'` write that fires CORA's terminal, so a
    # read there returns the PREVIOUS scan's filename. The areaDetector
    # file plugin's own readback is written at file OPEN, before the
    # terminal, and CORA's conducted path already reads the same PV
    # family (`operation/acquisitions.py`), so this is the correct
    # source, not a workaround. The value is PERSONAL DATA (2-BM's
    # directory layout embeds a surname and a proposal number): it is
    # never logged in full and never lands on an event; it goes to the
    # `run_capture_path` PII vault via `RunWitnessRecorder`'s dual-clock
    # guard. See `_run_witness.py`'s "Capture path pairing" section.
    #
    # `camera_selected` (optional per code) is a further role,
    # declared-and-unread by production exactly like `server_running`
    # (`ControlPortCaptureObserver` builds no pump for either): it names
    # the beamline's live camera-selection readback PV (2-BM:
    # `2bm:MCTOptics:CameraSelected`), read only by
    # `capture_watch_preflight`'s camera-prefix cross-check. That check
    # exists because `full_file_name`'s PV above is a hardcoded string
    # (2-BM's `2bmSP1:` / `2bmSP2:` are two separate cameras) with
    # nothing making it follow which camera is actually selected: an
    # operator's camera switch (as happened 2026-08-20) leaves it
    # reading the idle camera's stale value, which then reaches the
    # `run_capture_path` PII vault above unless caught first. See
    # `capture_camera_select_prefixes` below and
    # `capture_watch_preflight._camera_prefix_check`.
    capture_watch_pvs: dict[str, dict[str, str]] = {}

    # Deployment-declared table the `camera_selected` role's decoded
    # reading is looked up in, to resolve the `full_file_name` PV prefix
    # it should correspond to (the camera-prefix cross-check above).
    # CORA does not know, and must not guess, whether the substrate's
    # `CameraSelected` resolves to a bare index or an EPICS ENUM label:
    # that vocabulary belongs to one facility's IOC, exactly like
    # `capture_status_phases` below, so it is declared here rather than
    # hardcoded in the spine. Empty (default) means the cross-check
    # reports "not configured" rather than silently passing. Read from
    # CAPTURE_CAMERA_SELECT_PREFIXES as JSON:
    #
    #   CAPTURE_CAMERA_SELECT_PREFIXES='{
    #     "0": "2bmSP1:",
    #     "1": "2bmSP2:"
    #   }'
    #
    # The example above encodes the ONE fact confirmed in
    # `deployments/2-bm/beamline.yaml` (operator-verified 2026-06-19,
    # DET-11): camera 0 is the 5 MP `2bmSP1:` unit, camera 1 is the
    # 31 MP `2bmSP2:` unit. Whether `CameraSelected` actually reads back
    # as the bare literal `"0"` / `"1"` (rather than some other ENUM
    # label) is NOT confirmed against the live IOC; deploying this table
    # with the wrong keys would only ever produce "unrecognized-reading"
    # verdicts, never a false match, so it is safe to try and correct
    # once staff confirm the real readback shape.
    capture_camera_select_prefixes: dict[str, str] = {}

    # Genesis-baseline PVs (slice 12): a deployment-declared set read
    # ONCE, at the instant a capture promotes to a witnessed Run, and
    # written as `Observation` rows with `sampling_procedure="baseline"`.
    # This closes the conditions-snapshot gap without touching any event
    # payload: a witnessed Run's `effective_parameters` stays the
    # Plan's DECLARED defaults, and these rows carry what the substrate
    # actually read at that moment, discriminated from the progress
    # feeder's `sampling_procedure="monitor"` rows by that same field.
    #
    # Same `code -> inner-key -> PV` shape as `capture_watch_pvs`, but the
    # inner key is the observation's `channel_name`, not a role: baseline
    # needs on the order of twenty PVs per code (scan geometry plus
    # beamline conditions TomoScan never sees), which does not fit
    # `capture_watch_pvs`'s CLOSED role vocabulary (`status`, `abort`,
    # `images_saved`, `images_collected`, `testing`) and must not be
    # crammed into one by prefixing role keys. A sibling setting with an
    # open inner-key vocabulary is the natural fit; `capture_watch_pvs`
    # itself stays closed because ITS keys are dispatched on by name in
    # `_capture_observer.py` (an unrecognized role would silently do
    # nothing), which is not true here: every baseline channel is
    # treated identically (read once, coerced to float, appended), so an
    # open vocabulary costs nothing.
    #
    # `Observation.value` is `float` (`run/aggregates/run/entries.py`):
    # every PV declared here MUST read as numeric. A textual reading is
    # REJECTED (skipped and logged), never coerced. When empty (default)
    # no baseline read happens at genesis, so a generic boot is
    # unaffected. Read from CAPTURE_BASELINE_PVS as JSON:
    #
    #   CAPTURE_BASELINE_PVS='{
    #     "2bmb-tomoscan": {
    #       "ExposureTime": "2bmb:TomoScan:ExposureTime",
    #       "NumAngles": "2bmb:TomoScan:NumAngles",
    #       "RotationStart": "2bmb:TomoScan:RotationStart",
    #       "PropagationDistance": "2bmbAERO:m1"
    #     }
    #   }'
    #
    # The list is a UNION of two sources: TomoScan's own scan-geometry
    # records (`ExposureTime`, `NumAngles`, `RotationStart`, ... under
    # `2bmb:TomoScan:`) and beamline conditions TomoScan never reports
    # (propagation distance at `2bmbAERO:m1`). Beam energy has no
    # located readback PV as of this writing and is deliberately left
    # undeclared rather than guessed. See `cora.api._capture_baseline_reader`.
    capture_baseline_pvs: dict[str, dict[str, str]] = {}

    # The `status` role's raw substrate literal, mapped onto CORA's
    # closed `CapturePhase` vocabulary. These strings belong to one
    # tomoscan commit at one facility and MUST NOT be hardcoded in the
    # spine: 2-BM's `decarlof/tomoscan` reports free text like
    # "Beginning scan" / "Collecting projections" / "Scan complete" on
    # `ScanStatus`, and a different facility or a later tomoscan commit
    # may use different words for the same phase. A literal absent from
    # this table classifies as CapturePhase.UNRECOGNIZED rather than
    # being silently dropped or coerced into a nearby phase, so a
    # vocabulary drift (a tool upgrade renaming a status) is visible in
    # the watcher's log rather than misread as routine progress. Applies
    # across every code in `capture_watch_pvs`: the deployed variants
    # are confirmed byte-identical forks of one tomoscan base class, so
    # one shared table is the fact on the ground, not a shortcut.
    #
    #   CAPTURE_STATUS_PHASES='{
    #     "Beginning scan": "Begun",
    #     "Programming PSO": "Progressing",
    #     "Collecting dark fields": "Progressing",
    #     "Collecting flat fields": "Progressing",
    #     "Collecting projections": "Progressing",
    #     "fdt file transfer complete": "Progressing",
    #     "scp file transfer complete": "Progressing",
    #     "Scan complete": "Ended"
    #   }'
    #
    # NOTE the fdt / scp transfer messages map to Progressing, not
    # Ended: they mark transfer START, not arrival, per
    # docs/deployments/2-bm/operations.md. An `Aborted` phase reaches
    # `RunWitnessRecorder` via the separate `abort` role
    # (`_from_abort_reading` in `_capture_observer.py`), never through
    # this table: `decarlof/tomoscan@master` never calls
    # `ScanStatus.put("Scan aborted")` (verified by extracting every
    # `ScanStatus.put()` call in `tomoscan.py` / `tomoscan_2bm.py` /
    # `tomoscan_pso.py`), so that literal was never a real mapping
    # target and has been removed from this example. Two literals
    # upstream DOES write are deliberately absent here too: "Error
    # writing configuration" (`tomoscan.py`) and "Config File Write
    # Error" (`tomoscan_pso.py`). Both classify UNRECOGNIZED until an
    # operator decides what CapturePhase, if any, a config-write
    # failure should map to; inventing one here would be a guess this
    # table exists specifically to avoid.
    capture_status_phases: dict[str, str] = {}

    # Bounds how often the capture-watch runtime re-reads each
    # configured `status` PV independent of push traffic, mirroring
    # `enclosure_permit_probe_tick_seconds`. `None` (default) disables
    # polling entirely: reach is then push-only. OPERATIONAL KILL
    # SWITCH, not just a test convenience. Irrelevant when
    # `capture_watch_pvs` is empty.
    capture_watch_probe_tick_seconds: float | None = None

    # Runs the capture-watch loop in shadow mode: drains observations,
    # maps them through `capture_status_phases`, and logs. Writes no
    # event, no Run-scoped entries row, and promotes no Run unless
    # `run_witness_recording_enabled` is ALSO True (see below). ONE
    # exception, added by slice 16: `entries_run_capture_probes` writes
    # in shadow mode too, gated on its own
    # `capture_probe_recording_enabled` switch, precisely because that
    # trail exists to cover the gaps a promoted Run cannot -- including
    # the shadow-only window this comment used to say wrote nothing.
    # Default off; irrelevant when `capture_watch_pvs` is empty. See
    # `cora.api._run_witness`.
    run_witness_enabled: bool = False

    # Which Plan a promoted witnessed Run references (record_witnessed_run's
    # plan_id). Deployment-declared, not read from the substrate:
    # TomoScan reports a scan began, never which Plan it corresponds to.
    # `None` (default) disables promotion regardless of
    # `run_witness_recording_enabled` (see
    # `_enforce_run_witness_recording_gate` in `main.py`).
    capture_watch_plan_id: UUID | None = None

    # SECOND, independent kill switch above `run_witness_enabled`:
    # shadow mode (drain + log) stays default-on once `run_witness_enabled`
    # is True; this flag additionally gates whether a BEGUN observation is
    # actually promoted to a real witnessed Run via `record_witnessed_run`.
    # Default off, so enabling `run_witness_enabled` alone stays
    # shadow-only, unchanged from today. OPERATIONAL KILL SWITCH: boot
    # refuses to start if this is True without both
    # `run_witness_enabled=True` and `capture_watch_plan_id` set (see
    # `_enforce_run_witness_recording_gate` in `main.py`).
    run_witness_recording_enabled: bool = False

    # THIRD, independent kill switch (slice 10): gates whether the
    # `images_saved` / `images_collected` progress roles are buffered and
    # written as Observation entries against the promoted Run. Default
    # off. Refuses to boot if True without `run_witness_recording_enabled`
    # also True (see `_enforce_run_witness_recording_gate`): with no
    # promoted Run there is nothing to attach a progress reading to.
    # Writing to Postgres on a timer driven by a facility resource is
    # exactly the same operational-rollback shape as
    # `enclosure_permit_probe_tick_seconds`; this flag is the switch that
    # touches no code. See `cora.api._capture_progress_feeder`.
    capture_progress_recording_enabled: bool = False

    # Flush cadence for buffered progress readings, matching the
    # `*_tick_seconds` naming every other loop-cadence setting uses
    # (run_supervisor / run_initiator / clearance_expirer /
    # clearance_watcher / calibration_watcher / procedure_watcher /
    # campaign_watcher / enclosure_permit_probe / capture_watch_probe).
    # Bounds Postgres write rate to (codes x progress roles) per tick
    # regardless of substrate update rate: the buffer always holds only
    # the LATEST reading per (capture_code, role), so a shorter interval
    # raises time-resolution, never row count per tick. Irrelevant when
    # `capture_progress_recording_enabled` is False.
    capture_progress_flush_tick_seconds: float = 10.0

    # FOURTH, independent kill switch (slice 12): gates whether the
    # `capture_baseline_pvs` set is actually read and appended at
    # promotion. Default off. Refuses to boot if True without
    # `run_witness_recording_enabled` also True (see
    # `_enforce_run_witness_recording_gate`): with no promoted Run there
    # is nothing to attach a baseline reading to. Mirrors
    # `capture_progress_recording_enabled`'s gate exactly, for the same
    # reason: a one-time read driven by a facility resource is still a
    # write this switch must be able to turn off independently of
    # whether the PVs are merely declared. See
    # `cora.api._capture_baseline_reader`.
    capture_baseline_recording_enabled: bool = False

    # FIFTH, independent kill switch (slice 13): gates whether the
    # `full_file_name` role's observed path is actually resolved and
    # written to the `run_capture_path` PII vault at a witnessed Run's
    # terminal. Default off. Refuses to boot if True without
    # `run_witness_recording_enabled` also True (see
    # `_enforce_run_witness_recording_gate`): the write happens at a
    # promoted Run's terminal, so with no promotion there is no run_id
    # to write against. Independently revocable from the other four
    # switches because it is the one that writes personal data: an
    # operator must be able to turn OFF only this write (e.g. pending a
    # privacy review) without also disabling progress or baseline
    # recording. Declaring `full_file_name` in `capture_watch_pvs` alone
    # is necessary but not sufficient, mirroring every other switch
    # here. See `cora.api._run_witness`'s "Capture path pairing" section.
    capture_path_recording_enabled: bool = False

    # Experiment-identity PVs (slice 14a): a deployment-declared set read
    # ONCE, at the instant a capture promotes to a witnessed Run, mirroring
    # `capture_baseline_pvs`'s one-shot-at-BEGUN timing exactly. Same
    # `code -> inner-key -> PV` shape as `capture_watch_pvs`: a CLOSED
    # inner-key vocabulary (`proposal_number`, `esaf_number`, `esaf_doi_number`),
    # because these three roles are dispatched on by name in
    # `cora.api._capture_experiment_identity_reader` (an unrecognized role
    # would silently never be read), unlike `capture_baseline_pvs`'s open
    # per-channel vocabulary.
    #
    #   CAPTURE_EXPERIMENT_IDENTITY_PVS='{
    #     "2bmb-tomoscan": {
    #       "proposal_number": "2bmb:TomoScan:ProposalNumber",
    #       "esaf_number": "2bmb:TomoScan:ESAFNumber",
    #       "esaf_doi_number": "2bmb:TomoScan:ESAFDOINumber"
    #     }
    #   }'
    #
    # `ProposalNumber` / `ESAFNumber` are `stringout` records (native
    # DBR_STRING; no `text_addresses` declaration needed). `ESAFDOINumber`
    # is a `waveform` (DBR_CHAR), the identical wire shape as the
    # `full_file_name` role's PV: the deployment's `CONTROL_PORT_ROUTES`
    # MUST also declare it in `text_addresses`, or it decodes as a
    # character array, not text.
    #
    # These three values are stamped by dmagic from APS scheduling data,
    # not by the IOC itself, and are NOT personal data (unlike the `User*`
    # PVs under the same `2bmb:TomoScan:` prefix, which slice 14b leaves
    # unread): they are institutional identifiers for a funded experiment.
    # They default to the substrate literal `"Unknown"` when unpopulated;
    # CORA treats that literal, and an empty string, as ABSENT and records
    # nothing (see `cora.api._capture_experiment_identity_reader`'s
    # `resolved_experiment_identity_text`).
    #
    # Written to the `run_experiment_identity` PII-vault-shaped table
    # (mirroring `run_capture_path`), NEVER onto `RunStarted` or any other
    # event: the value read here is auto-harvested off an unauthenticated
    # channel with no operator gesture behind it, unlike `start_run`'s
    # operator-supplied `external_refs`, and events are immutable and
    # INSERT-only, so a harvested proposal/ESAF number written there could
    # never be withdrawn. A public-resolvability check against DataCite and
    # the upstream `dmagic`/APS-DM-SDK source found `ESAFDOINumber` is
    # populated from an internal, authenticated APS API
    # (`EsafApsDbApi.getStationEsafById`), with no public DOI-registry
    # record found; unconfirmed as a genuinely resolvable DOI, so it vaults
    # with the other two rather than riding an event. See
    # `cora.api._capture_experiment_identity_reader`'s module docstring for
    # the full argument (memory/project_witnessed_run_prelive_slices.md,
    # slice 14a).
    capture_experiment_identity_pvs: dict[str, dict[str, str]] = {}

    # SIXTH, independent kill switch (slice 14a): gates whether the
    # `capture_experiment_identity_pvs` set is actually read and vaulted at
    # promotion. Default off. Refuses to boot if True without
    # `run_witness_recording_enabled` also True (see
    # `_enforce_run_witness_recording_gate`): with no promoted Run there is
    # no run_id to vault a reading against. Independently revocable from
    # the other five switches for the same reason `capture_path_recording_enabled`
    # is: an operator must be able to turn OFF only this write pending a
    # privacy/provenance review, without disabling progress, baseline, or
    # path recording. Declaring the PVs in `capture_experiment_identity_pvs`
    # alone is necessary but not sufficient, mirroring every other switch
    # here.
    capture_experiment_identity_recording_enabled: bool = False

    # SEVENTH, independent kill switch (slice 16): gates whether reach to
    # the capture-watch substrate (`ControlPortCaptureObserver`'s status /
    # abort pumps) is recorded as `entries_run_capture_probes` rows.
    # Default off.
    #
    # DELIBERATELY DIVERGES from the THIRD/FOURTH/FIFTH/SIXTH switches
    # above: those four all require `run_witness_recording_enabled` also True,
    # because each writes against an already-promoted Run's row (a
    # progress reading, a baseline reading, a capture path, an
    # experiment identity), so with no promotion there is nothing to
    # attach a write to. This switch's
    # entire value is realized specifically while recording is OFF
    # (shadow-only) or between Runs: `entries_run_capture_probes` scopes
    # on `capture_code`, not `run_id` (see that table's migration header
    # and `cora.run.aggregates.run.capture_probes`), precisely so it can
    # answer "was CORA watching" during the gaps a promoted Run cannot
    # cover. Requiring `run_witness_recording_enabled` here would silence
    # the trail during exactly the shadow-only window it exists to cover
    # -- the live 2-BM state as of this writing (three days of a dead
    # IOC, `run_witness_enabled=True`, recording still off, and zero rows
    # recorded anywhere). Refuses to boot if True without
    # `run_witness_enabled` also True (see
    # `_enforce_run_witness_recording_gate`): with the shadow observer not
    # running there is nothing to write from. See
    # `cora.api._run_witness`'s probe-write section.
    capture_probe_recording_enabled: bool = False

    # EIGHTH kill switch (slice 17), and the only one so far that is NOT a
    # `*_recording_enabled`: the seven above gate entries or PII-vault
    # writes; this one gates real EVENT appends across three streams
    # (Dataset, Distribution, Acquisition) via `IngestScan`. Default off.
    # Refuses to boot if True without `capture_path_recording_enabled` also
    # True (see `_enforce_run_witness_recording_gate`): the sweep's only
    # candidate signal is a resolved `run_capture_path` row, so with no
    # path ever recorded there is nothing to ingest. Named after the
    # agent (`capture_scan_ingestor_*`), matching every other lifespan
    # switch's `snake(<AgentClass>)_enabled` convention. See
    # `cora.api._capture_scan_ingestor`.
    capture_scan_ingestor_enabled: bool = False

    # Sweep cadence, matching every other loop's `*_tick_seconds` naming.
    # Irrelevant when `capture_scan_ingestor_enabled` is False.
    capture_scan_ingestor_tick_seconds: float = 30.0

    # NINTH kill switch (durable-distribution sweep): gates whether
    # DurableCopyRegistrar's periodic sweep finds a Dataset's durable
    # copy (the archival tier an operator later copies the experiment
    # to, distinct from the transient acquisition tier) and registers it
    # as a second Distribution on the same Dataset. Default off.
    # Refuses to boot if True without `capture_path_recording_enabled`,
    # without at least one durable location configured, or with a
    # durable root outside `scan_probe_allowed_roots` specifically (see
    # `_enforce_run_witness_recording_gate`). Named after the sweep
    # (`durable_distribution_sweep_*`), matching every other lifespan
    # switch's `snake(<AgentClass>)_enabled` convention. See
    # `cora.api._durable_distribution`.
    durable_distribution_sweep_enabled: bool = False

    # Sweep cadence, matching every other loop's `*_tick_seconds` naming.
    # Irrelevant when `durable_distribution_sweep_enabled` is False.
    durable_distribution_sweep_tick_seconds: float = 30.0

    # SSH host holding the scan bytes (e.g. "tomdet"), or `None` for a
    # deployment where CORA's own host mounts the storage directly. When
    # set, `ingest_scan` reads and digests the file entirely on this host
    # via `cora.data._remote_scan_probe`, invoked over SSH, and only a
    # JSON verdict crosses the network -- measured at 2-BM, pulling one
    # ~24 GB scan file to CORA's host takes roughly twice the scan
    # cadence, so mounting the detector volume is not viable; see
    # `cora.data.adapters._ssh_probe`. `None` falls back to the local
    # `DataExchangeScanReader` / `PosixChecksumAdapter` pair keyed off
    # `posix_checksum_roots`, which suits a deployment or test
    # environment where the files really are local.
    #
    # `scan_probe_*`, not `capture_scan_ingestor_*`: `wire_data` selects
    # this pair unconditionally for `ingest_scan`, so it also governs the
    # human POST route and the MCP tool, not only the sweep agent. Sharing
    # the agent's own prefix would misname it as sweep-only.
    scan_probe_remote_host: str | None = None

    # Absolute path to the Python interpreter invoked on
    # `scan_probe_remote_host` (CORA's own venv, reachable from that host
    # over the same shared filesystem CORA itself runs from). Required
    # when `scan_probe_remote_host` is set; validated together below.
    scan_probe_remote_python: str | None = None

    # Allowlist of absolute filesystem roots the remote probe may read --
    # as valid ON `scan_probe_remote_host`, not on CORA's own filesystem.
    # ONLY takes effect when `scan_probe_remote_host` is set; with no
    # remote host, `_build_scan_ingest_pair` selects the LOCAL adapter
    # pair instead, which is keyed off `posix_checksum_roots`, a
    # separate setting (both enforce the same safety rule, via the same
    # `resolve_confined_file_uri` helper, just on different hosts and
    # under different names, since one governs a remote filesystem this
    # deployment's own roots have no bearing on). Empty (default)
    # refuses every locator, so scan-ingest is off until a deployment
    # opts in. Read from SCAN_PROBE_ALLOWED_ROOTS as JSON, for example:
    #
    #   SCAN_PROBE_ALLOWED_ROOTS='["/local1/2BM"]'
    scan_probe_allowed_roots: tuple[str, ...] = ()

    # SSH connect + end-to-end command budget for one remote probe
    # invocation. The command timeout must exceed the slowest expected
    # digest walk (measured ~26 s for a 24 GB file on tomdet's local
    # disk); the default gives roughly 2x headroom. A probe that exceeds
    # either bound is killed and reported as unreachable, never left to
    # hang a sweep tick indefinitely.
    scan_probe_ssh_connect_timeout_seconds: float = 10.0
    scan_probe_ssh_command_timeout_seconds: float = 60.0

    # Per-capture-code binding: what `IngestScan` needs that no file or PV
    # can say (which Asset produced it), plus one `CaptureScanIngestorLocation`
    # per storage root the finished file may land on. A Run holds one
    # vault row per storage location (the acquisition tier on fast local
    # disk, and the durable APS Data Management copy under `/gdata`),
    # each reached over a different access protocol from a different
    # Supply, so `locations` carries one entry per location -- keyed by
    # the location's OWN storage root rather than an invented tier name.
    # The vault's `root` column itself carries only a length CHECK, no
    # normalization guarantee; every row it holds is normalized in
    # practice because `_run_witness.py` is the column's single writer
    # and always writes through `matched_storage_root`
    # (`cora.shared.storage_root`), so `cora.api._capture_scan_ingestor`
    # reading a candidate's root straight off that row and joining
    # against these keys needs no separate normalization step. A code
    # absent from this map is never auto-ingested, mirroring every
    # other per-code table's optionality. See
    # `cora.infrastructure.capture_scan_ingestor_binding`
    # for the model shapes and their own validation. Read from
    # CAPTURE_SCAN_INGESTOR_BINDINGS as JSON, for example:
    #
    #   CAPTURE_SCAN_INGESTOR_BINDINGS='{
    #     "2bmb-tomoscan": {
    #       "producing_asset_id": "0c5e...-camera-asset-uuid",
    #       "locations": {
    #         "/local1/2BM": {
    #           "supply_id": "b2a1...-storage-supply-uuid",
    #           "access_protocol": "POSIX"
    #         },
    #         "/gdata/dm/2BM": {
    #           "supply_id": "77f0...-storage-supply-uuid",
    #           "access_protocol": "NFS",
    #           "durable": true,
    #           "subdirectory": "data"
    #         }
    #       }
    #     }
    #   }'
    capture_scan_ingestor_bindings: dict[str, CaptureScanIngestorBinding] = {}

    @field_validator("capture_scan_ingestor_bindings")
    @classmethod
    def _validate_capture_scan_ingestor_bindings(
        cls, value: dict[str, CaptureScanIngestorBinding], info: ValidationInfo
    ) -> dict[str, CaptureScanIngestorBinding]:
        """Refuse a location root that CORA can never actually read from, at boot.

        Per-binding shape (non-empty, absolute, normalized, no
        collapsing duplicates) is enforced by
        `CaptureScanIngestorBinding`'s own field validator, which runs
        before this one sees the value. What only `Settings` can check
        is reachability: a location root must be a member of either
        `posix_checksum_roots` or `scan_probe_allowed_roots`, the two
        allowlists `_build_scan_ingest_pair` actually reads from,
        because a root neither adapter can serve would sit in the map
        forever, refused by `_mint_locator`'s allowlist check on every
        tick. Checked as a plain UNION rather than by reproducing
        `active_scan_transport`'s host-conditional selection between the
        two: the deployment may reconfigure `scan_probe_remote_host`
        after boot's static validation runs, so a location valid under
        either allowlist must not be rejected here.
        """
        posix_roots = info.data.get("posix_checksum_roots", ())
        probe_roots = info.data.get("scan_probe_allowed_roots", ())
        allowed_roots = {normalize_storage_root(root) for root in (*posix_roots, *probe_roots)}
        for code, binding in value.items():
            for root in binding.locations:
                if root not in allowed_roots:
                    msg = (
                        f"capture_scan_ingestor_bindings[{code!r}] names location "
                        f"{root!r}, which is in neither posix_checksum_roots nor "
                        "scan_probe_allowed_roots. A location CORA can never "
                        "read from can never be ingested."
                    )
                    raise ValueError(msg)
        return value

    @field_validator("scan_probe_remote_python")
    @classmethod
    def _validate_scan_probe_remote_python(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        """`scan_probe_remote_host` with no interpreter path is a
        misconfiguration that would otherwise surface only as an
        `ssh ... -m cora.data._remote_scan_probe` invoked with `None` as
        an argv element, at the first sweep tick."""
        if info.data.get("scan_probe_remote_host") and not value:
            msg = (
                "scan_probe_remote_host is set but "
                "scan_probe_remote_python is not. The remote host needs "
                "an explicit interpreter path to run cora.data._remote_scan_probe."
            )
            raise ValueError(msg)
        return value

    @field_validator("scan_probe_remote_host")
    @classmethod
    def _validate_scan_probe_remote_host(cls, value: str | None) -> str | None:
        """Reject an empty or whitespace-only host rather than silently
        treating it as unset.

        `SCAN_PROBE_REMOTE_HOST=""` is a different
        signal than the variable being absent -- in a deployment's
        settings template it usually means an interpolation that
        resolved to nothing -- and `active_scan_transport` tests
        `is not None`, so a bare "" was passing through as a configured
        remote transport with no host to connect to, then failing the
        vault's own CHECK constraint on the first upsert instead of at
        boot. Coercing "" to `None` was the other option; rejecting is
        chosen instead so the misconfiguration surfaces immediately
        rather than being silently papered over. Leave the setting
        unset to mean "no remote probe."
        """
        if value is not None and not value.strip():
            msg = (
                "scan_probe_remote_host is set to an empty or "
                "whitespace-only string. Leave it unset to disable the "
                "remote scan probe, rather than setting it to an empty value."
            )
            raise ValueError(msg)
        return value

    @field_validator("posix_checksum_roots")
    @classmethod
    def _validate_posix_checksum_roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse a root that cannot name a real storage tier at boot,
        not at the first attestation. A relative path is meaningless to
        `PosixChecksumAdapter`, which treats every root as absolute, and
        `normalize_storage_root("/")` collapses to the empty string,
        which the run_capture_path vault's own CHECK constraint forbids
        -- so bare "/" would otherwise pass here and fail on the first
        write instead of at boot. A trailing slash is fine: normalization
        (`cora.shared.storage_root`) handles it.
        """
        for root in value:
            require_nonempty_absolute_root(root, label="posix_checksum_roots entry")
        return value

    @field_validator("scan_probe_allowed_roots")
    @classmethod
    def _validate_scan_probe_allowed_roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Same rule as `posix_checksum_roots`, applied to the roots
        allowlisted on `scan_probe_remote_host`: a relative path or a
        bare "/" is a misconfiguration worth refusing at boot rather
        than discovering when the remote probe's own resolver refuses
        every locator. A trailing slash is fine: normalization
        (`cora.shared.storage_root`) handles it.
        """
        for root in value:
            require_nonempty_absolute_root(root, label="scan_probe_allowed_roots entry")
        return value

    @field_validator("capture_experiment_identity_pvs")
    @classmethod
    def _validate_capture_experiment_identity_pvs(
        cls, value: dict[str, dict[str, str]]
    ) -> dict[str, dict[str, str]]:
        """Refuse an unrecognized role key at boot, not at the first
        promotion: `cora.api._capture_experiment_identity_reader` dispatches
        on exactly `{"proposal_number", "esaf_number", "esaf_doi_number"}` by name,
        so a typo'd role here would otherwise silently never be read, with
        no error anywhere -- the same class of silent-misconfiguration risk
        `_validate_capture_status_phases` already guards against."""
        bad = {
            code: sorted(set(roles) - _EXPERIMENT_IDENTITY_ROLES)
            for code, roles in value.items()
            if set(roles) - _EXPERIMENT_IDENTITY_ROLES
        }
        if bad:
            msg = (
                "capture_experiment_identity_pvs has roles outside "
                f"{sorted(_EXPERIMENT_IDENTITY_ROLES)}: {bad}. An unrecognized role "
                "is never read by cora.api._capture_experiment_identity_reader."
            )
            raise ValueError(msg)
        return value

    @field_validator("capture_status_phases")
    @classmethod
    def _validate_capture_status_phases(cls, value: dict[str, str]) -> dict[str, str]:
        """Refuse an unparseable phase table at boot, not at the first
        capture: a typo here would otherwise silently classify every
        observation as UNRECOGNIZED until someone reads the log."""
        valid = {member.value for member in CapturePhase if member is not CapturePhase.UNRECOGNIZED}
        bad = {literal: phase for literal, phase in value.items() if phase not in valid}
        if bad:
            msg = (
                f"capture_status_phases has values outside CapturePhase {sorted(valid)}: "
                f"{bad}. UNRECOGNIZED is not a valid mapping target; a literal "
                "absent from this table already classifies as UNRECOGNIZED."
            )
            raise ValueError(msg)
        return value

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

    @field_validator("run_supervisor_envelope_hold_settle_ticks")
    @classmethod
    def _validate_run_supervisor_envelope_hold_settle_ticks(cls, value: int) -> int:
        """Floor of 1: a hold needs at least one confirmed-bad envelope read."""
        if value < 1:
            msg = (
                f"run_supervisor_envelope_hold_settle_ticks must be >= 1, got {value}; "
                "an autonomous envelope hold requires at least one confirmed-failed read"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_initiator_tick_seconds")
    @classmethod
    def _validate_run_initiator_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight initiation loop."""
        if value < 0.1:
            msg = (
                f"run_initiator_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the initiator"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_initiator_max_in_flight")
    @classmethod
    def _validate_run_initiator_max_in_flight(cls, value: int) -> int:
        """Floor of 1: the initiator must be able to start at least one Run per tick."""
        if value < 1:
            msg = (
                f"run_initiator_max_in_flight must be >= 1, got {value}; "
                "the initiator must be able to start at least one Run per tick"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_supervisor_truncate_settle_ticks")
    @classmethod
    def _validate_run_supervisor_truncate_settle_ticks(cls, value: int) -> int:
        """Floor of 1: a terminal truncate needs at least one stale read first."""
        if value < 1:
            msg = (
                f"run_supervisor_truncate_settle_ticks must be >= 1, got {value}; "
                "an autonomous truncate requires at least one liveness-stale read"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_supervisor_quality_settle_ticks")
    @classmethod
    def _validate_run_supervisor_quality_settle_ticks(cls, value: int) -> int:
        """Floor of 1: an autonomous abort needs at least one below-limit read first."""
        if value < 1:
            msg = (
                f"run_supervisor_quality_settle_ticks must be >= 1, got {value}; "
                "an autonomous abort requires at least one below-limit read"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_supervisor_stall_settle_ticks")
    @classmethod
    def _validate_run_supervisor_stall_settle_ticks(cls, value: int) -> int:
        """Floor of 1: an autonomous stop needs at least one stalled read first."""
        if value < 1:
            msg = (
                f"run_supervisor_stall_settle_ticks must be >= 1, got {value}; "
                "an autonomous stop requires at least one stalled read"
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

    @field_validator("run_stall_window_factor")
    @classmethod
    def _validate_run_stall_window_factor(cls, value: float) -> float:
        """Window must be at least one expected interval (>= 1.0): a sub-interval
        window cannot resolve a gap, so a smaller factor would never be a valid
        stall measurement."""
        if value < 1.0:
            msg = (
                f"run_stall_window_factor must be >= 1.0, got {value}; "
                "the stall window must cover at least one expected interval"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_stall_hysteresis_ticks")
    @classmethod
    def _validate_run_stall_hysteresis_ticks(cls, value: int) -> int:
        """At least one tick; the anti-flap streak counts consecutive ticks."""
        if value < 1:
            msg = (
                f"run_stall_hysteresis_ticks must be >= 1, got {value}; "
                "a stall flag needs at least one stall-condition tick"
            )
            raise ValueError(msg)
        return value

    @field_validator("run_feed_heartbeat_ceiling_seconds")
    @classmethod
    def _validate_run_feed_heartbeat_ceiling_seconds(cls, value: float | None) -> float | None:
        """None disables the stall rule's dead-feeder anchor; a set ceiling must
        be positive (a non-positive ceiling would read every feeder as dead)."""
        if value is not None and value <= 0:
            msg = (
                f"run_feed_heartbeat_ceiling_seconds must be > 0 when set, got {value}; "
                "None leaves the stall rule's feeder-health anchor unset (rule defers)"
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

    @field_validator("calibration_watcher_tick_seconds")
    @classmethod
    def _validate_calibration_watcher_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight watch-sweep loop."""
        if value < 0.1:
            msg = (
                f"calibration_watcher_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the watcher"
            )
            raise ValueError(msg)
        return value

    @field_validator("calibration_watcher_stale_after_seconds")
    @classmethod
    def _validate_calibration_watcher_stale_after_seconds(cls, value: float) -> float:
        """Must be positive: a non-positive window would flag every Provisional
        calibration."""
        if value <= 0:
            msg = (
                f"calibration_watcher_stale_after_seconds must be > 0, got {value}; "
                "a non-positive window would flag every Provisional calibration"
            )
            raise ValueError(msg)
        return value

    @field_validator("procedure_watcher_tick_seconds")
    @classmethod
    def _validate_procedure_watcher_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight watch-sweep loop."""
        if value < 0.1:
            msg = (
                f"procedure_watcher_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the watcher"
            )
            raise ValueError(msg)
        return value

    @field_validator("procedure_watcher_stale_after_seconds")
    @classmethod
    def _validate_procedure_watcher_stale_after_seconds(cls, value: float) -> float:
        """Must be positive: a non-positive window would flag every in-conduct
        procedure."""
        if value <= 0:
            msg = (
                f"procedure_watcher_stale_after_seconds must be > 0, got {value}; "
                "a non-positive window would flag every in-conduct procedure"
            )
            raise ValueError(msg)
        return value

    @field_validator("campaign_watcher_tick_seconds")
    @classmethod
    def _validate_campaign_watcher_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight watch-sweep loop."""
        if value < 0.1:
            msg = (
                f"campaign_watcher_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the watcher"
            )
            raise ValueError(msg)
        return value

    @field_validator("campaign_watcher_stale_after_seconds")
    @classmethod
    def _validate_campaign_watcher_stale_after_seconds(cls, value: float) -> float:
        """Must be positive: a non-positive window would flag every Held campaign."""
        if value <= 0:
            msg = (
                f"campaign_watcher_stale_after_seconds must be > 0, got {value}; "
                "a non-positive window would flag every Held campaign"
            )
            raise ValueError(msg)
        return value

    @field_validator("capture_progress_flush_tick_seconds")
    @classmethod
    def _validate_capture_progress_flush_tick_seconds(cls, value: float) -> float:
        """Floor of 0.1s prevents a tight flush loop that also defeats
        the decimation the feeder's buffering design rests on."""
        if value < 0.1:
            msg = (
                f"capture_progress_flush_tick_seconds must be >= 0.1, got {value}; "
                "values below 100ms would tight-loop the flush and turn the "
                "buffer's decimation back into a PV-rate write firehose"
            )
            raise ValueError(msg)
        return value
