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
    # The 2026-05-18 bootstrap migration seeded the System Bootstrap Policy at a
    # fixed UUID so production deployments can enable real authz with
    # a single env var instead of the old 3-step dance:
    #
    #   TRUST_POLICY_ID=00000000-0000-0000-0000-000000000001
    #
    # The seed permits SYSTEM_PRINCIPAL_ID to call DefinePolicy +
    # RegisterActor on the nil conduit — the minimum needed to
    # register a real admin Actor and promote a real admin Policy.
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
    # `app_env in {"prod", "production"}` and this is False, so a
    # production deployment cannot accidentally launch with the
    # permissive default.
    require_authenticated_principal: bool = False

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
