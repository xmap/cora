"""CORA FastAPI entrypoint.

`create_app()` is the factory: each call builds a fresh FastMCP server,
fresh FastAPI app, fresh middleware stack. The module-level `app` is
the production singleton (uvicorn imports it). Tests call `create_app()`
to get isolated instances — necessary because FastMCP's
StreamableHTTPSessionManager raises if the same instance's `.run()` is
called twice (once per lifespan), so reusing the module-level app
across multiple TestClient context managers fails.

Lifespan composition: the MCP session manager's lifespan must wrap our
shared-deps build so the manager initializes before any MCP request.
Without the wrap, mounted MCP requests silently fail
(modelcontextprotocol/python-sdk#1367).

Observability stack:
- OpenTelemetry tracing is configured at app construction; the global
  TracerProvider is installed iff `settings.otel_exporter != "none"`.
  Per-app FastAPI instrumentation is attached after app creation.
  The W3C `traceparent` header is the source of truth for "this
  request" identity; the prior `asgi-correlation-id` middleware was
  removed because OTel's TraceContextTextMapPropagator handles inbound
  / outbound trace propagation per the W3C spec.
- Prometheus metrics are exposed on `/metrics` (operational endpoint,
  excluded from OpenAPI schema).
- structlog is configured in `build_kernel()`; an OTel processor
  injects `trace_id` and `span_id` into every log line emitted inside
  an active span.
"""

import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator

from cora import __version__
from cora.access import (
    AccessHandlers,
    register_access_projections,
    register_access_routes,
    register_access_tools,
    wire_access,
)
from cora.agent import (
    AgentHandlers,
    build_llm,
    register_agent_projections,
    register_agent_routes,
    register_agent_subscribers,
    register_agent_tools,
    seed_caution_drafter_agent,
    seed_run_debriefer_agent,
    wire_agent,
)
from cora.api.middleware import BodySizeLimitMiddleware
from cora.api.protected_resource_metadata import register_protected_resource_metadata_route
from cora.calibration import (
    CalibrationHandlers,
    register_calibration_projections,
    register_calibration_routes,
    register_calibration_tools,
    wire_calibration,
)
from cora.campaign import (
    CampaignHandlers,
    register_campaign_projections,
    register_campaign_routes,
    register_campaign_tools,
    wire_campaign,
)
from cora.caution import (
    CautionHandlers,
    register_caution_projections,
    register_caution_routes,
    register_caution_tools,
    wire_caution,
)
from cora.caution.adapters import PostgresCautionLookup
from cora.data import (
    DataHandlers,
    register_data_projections,
    register_data_routes,
    register_data_tools,
    wire_data,
)
from cora.decision import (
    DecisionHandlers,
    register_decision_projections,
    register_decision_routes,
    register_decision_tools,
    wire_decision,
)
from cora.enclosure import (
    EnclosureHandlers,
    register_enclosure_projections,
    register_enclosure_routes,
    register_enclosure_tools,
    wire_enclosure,
)
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.equipment import (
    EquipmentHandlers,
    register_equipment_projections,
    register_equipment_routes,
    register_equipment_tools,
    wire_equipment,
)
from cora.equipment.adapters import PostgresAssetLookup
from cora.federation import (
    FederationHandlers,
    bootstrap_federation,
    register_federation_projections,
    register_federation_routes,
    register_federation_tools,
    wire_federation,
)
from cora.federation.adapters import PostgresCredentialLookup, PostgresFacilityLookup
from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup
from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort
from cora.infrastructure.auth.bearer_auth_middleware import BearerAuthMiddleware
from cora.infrastructure.auth.exception_handlers import register_auth_exception_handlers
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import build_kernel
from cora.infrastructure.idempotency_pruner import idempotency_pruner_lifespan
from cora.infrastructure.observability import configure_tracing, instrument_app
from cora.infrastructure.projection import (
    ProjectionRegistry,
    projection_worker_lifespan,
)
from cora.operation import (
    OperationHandlers,
    register_operation_projections,
    register_operation_routes,
    register_operation_tools,
    wire_operation,
)
from cora.recipe import (
    RecipeHandlers,
    register_recipe_projections,
    register_recipe_routes,
    register_recipe_tools,
    wire_recipe,
)
from cora.recipe.adapters import PostgresCapabilityLookup
from cora.run import (
    RunHandlers,
    register_run_projections,
    register_run_routes,
    register_run_tools,
    wire_run,
)
from cora.safety import (
    SafetyHandlers,
    register_safety_projections,
    register_safety_routes,
    register_safety_tools,
    wire_safety,
)
from cora.safety.adapters import PostgresClearanceLookup
from cora.subject import (
    SubjectHandlers,
    register_subject_projections,
    register_subject_routes,
    register_subject_tools,
    wire_subject,
)
from cora.supply import (
    SupplyHandlers,
    register_supply_projections,
    register_supply_routes,
    register_supply_tools,
    wire_supply,
)
from cora.supply.adapters import PostgresSupplyLookup
from cora.trust import (
    TrustHandlers,
    build_authorize,
    register_trust_projections,
    register_trust_routes,
    register_trust_tools,
    verify_bootstrap_seed_present,
    wire_trust,
)


def _settings_for_app() -> Settings:
    """Load Settings at app construction for one-shot wiring decisions.

    The lifespan also constructs Settings; both calls hit env vars / .env
    so they agree. Pulled into a helper purely for readability.
    """
    return Settings()  # type: ignore[call-arg]  # Pydantic loads from env


_PROD_APP_ENVS = frozenset({"prod", "production"})


def _enforce_production_principal_policy(settings: Settings) -> None:
    """Refuse to boot deployments where the principal-fallback would
    silently grant admin to header-less callers.

    TWO failure conditions, both producing the same fail-fast:

    1. `app_env in {prod, production}` without
       `require_authenticated_principal=True`. The legacy Phase-3e
       gate: header-less prod requests would otherwise run as
       SYSTEM_PRINCIPAL_ID under whichever Authorize port is wired.

    2. `trust_policy_id is not None` without
       `require_authenticated_principal=True`, when `app_env` is
       NOT `test`. Post-Phase-A: the seeded bootstrap policy permits
       SYSTEM_PRINCIPAL_ID to call DefinePolicy + RegisterActor.
       Without the principal-header check, ANY caller spoofing
       `X-Principal-Id: 00000000-0000-0000-0000-000000000000`
       becomes SYSTEM and gets standing admin. Staging/local
       deployments with only TRUST_POLICY_ID set (forgetting the
       second flag) would ship a wide-open API — gate-review F1.

       Test env (`app_env=test`) is exempt because legitimate test
       fixtures exercise "operator misconfigured" + "SYSTEM-fallback
       under real policy" scenarios that REQUIRE this combo to be
       constructible. The exemption is safe because `app_env=test`
       is never operator-set in deployment configs.

    Bootstrap workflow stays clean: a fresh deploy wanting AllowAll
    leaves `trust_policy_id` unset (today's default). A deploy
    wanting real authz sets BOTH env vars together — and operates
    behind an auth proxy that strips/sets `X-Principal-Id` per the
    routing.py contract.
    """
    if settings.app_env in _PROD_APP_ENVS and not settings.require_authenticated_principal:
        msg = (
            f"app_env={settings.app_env!r} requires "
            "require_authenticated_principal=True (set "
            "REQUIRE_AUTHENTICATED_PRINCIPAL=true). The permissive "
            "SYSTEM_PRINCIPAL_ID fallback is not safe for production."
        )
        raise RuntimeError(msg)
    if (
        settings.app_env != "test"
        and settings.trust_policy_id is not None
        and not settings.require_authenticated_principal
    ):
        msg = (
            f"trust_policy_id={settings.trust_policy_id!r} requires "
            "require_authenticated_principal=True (set "
            "REQUIRE_AUTHENTICATED_PRINCIPAL=true). Without the "
            "principal-header check, any caller can spoof "
            "X-Principal-Id and become SYSTEM under the configured "
            "Policy — bypassing the authz gate you just turned on. "
            "See memory/project_bootstrap_policy_design.md (F1)."
        )
        raise RuntimeError(msg)
    # gate-review HIGH F11: per-IdP allow_insecure_* opt-ins
    # exist for localhost test fixtures. Under prod posture an operator
    # (or an attacker with env-var-write access) could flip one IdP to
    # plaintext HTTP, silently bypassing the per-adapter HTTPS gate.
    # The per-adapter check in `JwtTokenVerifier` / `IntrospectionTokenVerifier`
    # CAN'T see `app_env`; this Settings-level check refuses boot when
    # any IdP entry opts in to insecure URLs under prod.
    if settings.app_env in _PROD_APP_ENVS:
        for idp in settings.identity_providers:
            if idp.allow_insecure_jwks_url or idp.allow_insecure_introspection_url:
                msg = (
                    f"app_env={settings.app_env!r}: IdP issuer={idp.issuer!r} "
                    "has allow_insecure_jwks_url or allow_insecure_introspection_url "
                    "set to True. These opt-ins exist for localhost test fixtures; "
                    "under prod posture, HTTP JWKS is MITM-exploitable and HTTP "
                    "introspection leaks CORA's client_secret over plain Basic "
                    "auth. Either remove the IdP entry, switch its URLs to "
                    "https://, or disable the opt-ins. See "
                    "memory/project_edge_auth_design.md gate-review F11."
                )
                raise RuntimeError(msg)


def create_app(*, settings: Settings | None = None) -> FastAPI:
    """Build a fresh FastAPI app with its own FastMCP server instance.

    Production calls this once at module import; tests call it per
    `TestClient` context to get isolation.

    `settings` is an optional injection point for tests that need
    to override env-var-loaded config (for example contract tests for
    edge-auth that need a specific `identity_providers` list).
    Production callers pass nothing; `_settings_for_app()` reads
    from env / .env as usual.
    """
    settings = settings if settings is not None else _settings_for_app()
    _enforce_production_principal_policy(settings)
    # configure_tracing is a no-op when otel_exporter == "none" (the
    # default in tests), so calling it per create_app() is safe. In
    # production it runs once and installs the global TracerProvider.
    tracing_teardown = configure_tracing(settings)

    # streamable_http_path="/" makes the inner MCP route the mount root,
    # so the full path under app.mount("/mcp", ...) is just "/mcp"
    # (otherwise the default "/mcp" inner path produces "/mcp/mcp").
    # transport_security: FastMCP's DNS-rebinding protection rejects
    # unknown Host headers. We're embedded in FastAPI behind the host
    # security FastAPI / the deployment proxy already enforces, so we
    # relax MCP's check here.
    mcp = FastMCP(
        "cora",
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    fastapi_app: FastAPI

    def _get_access_handlers() -> AccessHandlers:
        handlers: AccessHandlers = fastapi_app.state.access
        return handlers

    def _get_trust_handlers() -> TrustHandlers:
        handlers: TrustHandlers = fastapi_app.state.trust
        return handlers

    def _get_subject_handlers() -> SubjectHandlers:
        handlers: SubjectHandlers = fastapi_app.state.subject
        return handlers

    def _get_equipment_handlers() -> EquipmentHandlers:
        handlers: EquipmentHandlers = fastapi_app.state.equipment
        return handlers

    def _get_federation_handlers() -> FederationHandlers:
        handlers: FederationHandlers = fastapi_app.state.federation
        return handlers

    def _get_recipe_handlers() -> RecipeHandlers:
        handlers: RecipeHandlers = fastapi_app.state.recipe
        return handlers

    def _get_run_handlers() -> RunHandlers:
        handlers: RunHandlers = fastapi_app.state.run
        return handlers

    def _get_data_handlers() -> DataHandlers:
        handlers: DataHandlers = fastapi_app.state.data
        return handlers

    def _get_decision_handlers() -> DecisionHandlers:
        handlers: DecisionHandlers = fastapi_app.state.decision
        return handlers

    def _get_enclosure_handlers() -> EnclosureHandlers:
        handlers: EnclosureHandlers = fastapi_app.state.enclosure
        return handlers

    def _get_supply_handlers() -> SupplyHandlers:
        handlers: SupplyHandlers = fastapi_app.state.supply
        return handlers

    def _get_operation_handlers() -> OperationHandlers:
        handlers: OperationHandlers = fastapi_app.state.operation
        return handlers

    def _get_safety_handlers() -> SafetyHandlers:
        handlers: SafetyHandlers = fastapi_app.state.safety
        return handlers

    def _get_caution_handlers() -> CautionHandlers:
        handlers: CautionHandlers = fastapi_app.state.caution
        return handlers

    def _get_calibration_handlers() -> CalibrationHandlers:
        handlers: CalibrationHandlers = fastapi_app.state.calibration
        return handlers

    def _get_campaign_handlers() -> CampaignHandlers:
        handlers: CampaignHandlers = fastapi_app.state.campaign
        return handlers

    def _get_agent_handlers() -> AgentHandlers:
        handlers: AgentHandlers = fastapi_app.state.agent
        return handlers

    register_access_tools(mcp, get_handlers=_get_access_handlers)
    register_trust_tools(mcp, get_handlers=_get_trust_handlers)
    register_subject_tools(mcp, get_handlers=_get_subject_handlers)
    register_equipment_tools(mcp, get_handlers=_get_equipment_handlers)
    register_federation_tools(mcp, get_handlers=_get_federation_handlers)
    register_recipe_tools(mcp, get_handlers=_get_recipe_handlers)
    register_run_tools(mcp, get_handlers=_get_run_handlers)
    register_data_tools(mcp, get_handlers=_get_data_handlers)
    register_decision_tools(mcp, get_handlers=_get_decision_handlers)
    register_supply_tools(mcp, get_handlers=_get_supply_handlers)
    register_enclosure_tools(mcp, get_handlers=_get_enclosure_handlers)
    register_operation_tools(mcp, get_handlers=_get_operation_handlers)
    register_safety_tools(mcp, get_handlers=_get_safety_handlers)
    register_caution_tools(mcp, get_handlers=_get_caution_handlers)
    register_calibration_tools(mcp, get_handlers=_get_calibration_handlers)
    register_campaign_tools(mcp, get_handlers=_get_campaign_handlers)
    register_agent_tools(mcp, get_handlers=_get_agent_handlers)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # MCP session manager first (per python-sdk#1367), then our
        # shared deps inside it so both surfaces share one wiring.
        async with mcp_app.router.lifespan_context(app):
            deps, teardown = await build_kernel(
                authorize_factory=build_authorize,
                clearance_lookup_factory=PostgresClearanceLookup,
                caution_lookup_factory=PostgresCautionLookup,
                capability_lookup_factory=PostgresCapabilityLookup,
                supply_lookup_factory=PostgresSupplyLookup,
                credential_lookup_factory=PostgresCredentialLookup,
                facility_lookup_factory=PostgresFacilityLookup,
                asset_lookup_factory=PostgresAssetLookup,
                enclosure_lookup_factory=PostgresEnclosureLookup,
                # publish_revision slice deps: in-memory adapters
                # wired by default until the rule-of-two trigger
                # fires per project_federation_port_design.md.
                # Production deployments will override these with
                # the DSSE+Sigstore + COSE+SCITT wire-tier adapters
                # when the wire-tier work lands.
                publish_port_factory=InMemoryPublishPort,
                signature_port_factory=InMemorySignaturePort,
                permit_lookup_factory=InMemoryPermitLookup,
                llm_factory=build_llm,
                # Pass the create_app-time Settings through so tests
                # overriding identity_providers / require_auth / etc.
                # see them in the kernel.
                settings=settings,
            )
            app.state.deps = deps
            app.state.access = wire_access(deps)
            app.state.trust = wire_trust(deps)
            app.state.subject = wire_subject(deps)
            app.state.equipment = wire_equipment(deps)
            app.state.federation = wire_federation(deps)
            app.state.recipe = wire_recipe(deps)
            app.state.run = wire_run(deps)
            app.state.data = wire_data(deps)
            app.state.decision = wire_decision(deps)
            app.state.supply = wire_supply(deps)
            app.state.enclosure = wire_enclosure(deps)
            app.state.operation = wire_operation(deps)
            app.state.safety = wire_safety(deps)
            app.state.caution = wire_caution(deps)
            app.state.calibration = wire_calibration(deps)
            app.state.campaign = wire_campaign(deps)
            app.state.agent = wire_agent(deps)

            # Boot-time fail-fast when the deployment is pointed at the
            # bootstrap seed but the seed's stream is missing. Without
            # this check, a stale / unrestored DB silently 403s every
            # API call instead of failing visibly at startup.
            await verify_bootstrap_seed_present(deps)

            # Federation BC self-Facility seed per
            # project_facility_aggregate_design Sub-Slice D. Idempotent
            # (ConcurrencyError-as-already-seeded). LOAD-BEARING ORDER:
            # MUST run BEFORE any Federation OR cross-BC handler that
            # resolves a Facility slug (Slice 7+ register_supply via
            # FacilityLookup, future Asset / Safety binding). The
            # in-memory FacilityLookup is seeded here at bootstrap;
            # production PostgresFacilityLookup reads the projection
            # populated by the worker started below. Misconfigured
            # SELF_FACILITY_CODE fails the lifespan fast via
            # InvalidFacilityCodeError raised in FacilityCode(...).
            await bootstrap_federation(deps)

            # Phase-8e-1a: projection worker. Each BC that owns
            # projections exports a `register_<bc>_projections`
            # function called here to populate the registry. The
            # worker context manager handles spawn / cancel / drain.
            registry = ProjectionRegistry()
            register_access_projections(registry, deps)
            register_trust_projections(registry, deps)
            register_subject_projections(registry, deps)
            register_equipment_projections(registry, deps)
            register_federation_projections(registry, deps)
            register_recipe_projections(registry, deps)
            register_run_projections(registry, deps)
            register_data_projections(registry, deps)
            register_decision_projections(registry, deps)
            register_supply_projections(registry, deps)
            register_enclosure_projections(registry, deps)
            register_operation_projections(registry, deps)
            register_safety_projections(registry, deps)
            register_caution_projections(registry, deps)
            register_calibration_projections(registry, deps)
            register_campaign_projections(registry, deps)
            # Agent BC's projection (proj_agent_summary). Path C
            # lock — state-side lifecycle timestamps live on the
            # projection.
            register_agent_projections(registry, deps)
            # side-effecting Agent BC subscribers
            # (RunDebriefer). Conditional: only registered when
            # `kernel.llm` is wired (ANTHROPIC_API_KEY configured).
            register_agent_subscribers(registry, deps)
            app.state.projections = registry

            # seed the RunDebriefer Agent record so
            # the subscriber can resolve `actor_id` at apply()-time.
            # Idempotent across restarts; safe to re-run forever.
            await seed_run_debriefer_agent(deps)
            # same shape for CautionDrafter.
            await seed_caution_drafter_agent(deps)

            try:
                async with (
                    projection_worker_lifespan(deps, registry, settings),
                    idempotency_pruner_lifespan(deps),
                ):
                    yield
            finally:
                # Workers must stop before the pool closes, otherwise
                # the next worker iteration after `task.cancel()`
                # returns races against `pool.close()` and surfaces an
                # asyncpg `InterfaceError("pool is closing")`. Putting
                # `await teardown()` AFTER the workers' async-with
                # block guarantees the cancel-and-await dance has fully
                # unwound before any pool resource goes away.
                #
                # Independent try/finally pairs so an exception in pool
                # close (rare but observed under DB-side connection
                # drops at shutdown) doesn't skip the tracing flush.
                # Without this, any spans buffered by
                # BatchSpanProcessor would be lost.
                try:
                    # Release Operation BC ControlPort resources before
                    # the kernel pool closes. Registry-routed deployments
                    # hold aioca broadcaster + p4p Context state that
                    # must be released on shutdown; in-memory deployments
                    # see a no-op aclose. Suppressed so a flaky adapter
                    # cannot strand the rest of teardown. ControlPort
                    # Protocol does not declare aclose (it's adapter-
                    # optional); use getattr the same way the registry's
                    # own aclose fan-out does.
                    _port = app.state.operation.control_port
                    _aclose = getattr(_port, "aclose", None)
                    if _aclose is not None:
                        with contextlib.suppress(Exception):
                            await _aclose()
                    await teardown()
                finally:
                    # Flush pending OTel spans before the process exits
                    # so short-lived runs (CLI invocations, smoke
                    # tests) don't drop traces. No-op when tracing is
                    # off.
                    tracing_teardown()

    fastapi_app = FastAPI(
        title="CORA",
        version=__version__,
        description="Research facility operations platform",
        lifespan=lifespan,
    )
    fastapi_app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_request_body_size_bytes,
    )
    # Bearer-token verification at the HTTP edge. Reads
    # `Authorization: Bearer <token>`, verifies via
    # `kernel.token_verifier` (None when no IdPs configured ->
    # middleware no-ops and legacy X-Principal-Id path remains in
    # effect). Stores the VerifiedPrincipal on
    # request.state.principal; the route-layer `get_principal_id`
    # Depends reads from there. Added AFTER BodySizeLimit so the
    # size cap runs first (cheap reject before any token verification
    # work).
    fastapi_app.add_middleware(BearerAuthMiddleware)
    # Prometheus instrumentation:
    # - per-app CollectorRegistry so multiple create_app() calls in the
    #   test process don't double-register collectors against the global
    #   REGISTRY (which would crash the second TestClient).
    # - excluded_handlers=["/metrics"] keeps the scrape endpoint out of
    #   its own counters (otherwise each scrape pollutes its own metrics
    #   with monitoring traffic).
    # - include_in_schema=False hides /metrics from OpenAPI /docs (it's
    #   an operational endpoint, not part of the user-facing API).
    metrics_registry = CollectorRegistry()
    Instrumentator(
        registry=metrics_registry,
        excluded_handlers=["/metrics"],
    ).instrument(fastapi_app).expose(fastapi_app, include_in_schema=False)
    # OTel FastAPI instrumentation runs after app construction so the
    # FastAPIInstrumentor sees every route registered above plus the
    # ones registered below. No-op when tracing is off.
    instrument_app(fastapi_app, settings)
    register_access_routes(fastapi_app)
    register_trust_routes(fastapi_app)
    register_subject_routes(fastapi_app)
    register_equipment_routes(fastapi_app)
    register_federation_routes(fastapi_app)
    register_recipe_routes(fastapi_app)
    register_run_routes(fastapi_app)
    register_data_routes(fastapi_app)
    register_decision_routes(fastapi_app)
    register_supply_routes(fastapi_app)
    register_enclosure_routes(fastapi_app)
    register_operation_routes(fastapi_app)
    register_safety_routes(fastapi_app)
    register_caution_routes(fastapi_app)
    register_calibration_routes(fastapi_app)
    register_campaign_routes(fastapi_app)
    register_agent_routes(fastapi_app)
    # RFC 9728 Protected Resource Metadata. Discoverable
    # at /.well-known/oauth-protected-resource; clients dereference it
    # after a 401 + WWW-Authenticate response to learn which IdPs issue
    # tokens for which Surface.
    register_protected_resource_metadata_route(fastapi_app)
    # Install handlers that convert the bearer-auth typed errors
    # raised by BearerAuthMiddleware / TokenVerifier into RFC 6750
    # 401 (with WWW-Authenticate challenge) and RFC 7231 503 (with
    # Retry-After).
    register_auth_exception_handlers(fastapi_app)
    fastapi_app.mount("/mcp", mcp_app)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    return fastapi_app


app = create_app()
