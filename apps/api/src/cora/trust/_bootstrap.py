"""Trust BC re-exports, system-policy / system-surface UUIDs, and the
boot-time seed-verification helper.

See `cora/trust/authorize.py` for the bootstrap workflow,
`memory/project_bootstrap_policy_design.md` for the bootstrap rationale,
and `memory/project_conduit_injection_design.md` for the Surface
decomposition and the bootstrap-policy surface binding.
"""

from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import (
    NIL_SENTINEL_ID,
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    SYSTEM_PRINCIPAL_ID,
)
from cora.trust.aggregates.conduit import LOGBOOK_KIND_VERDICT, load_conduit
from cora.trust.aggregates.policy import load_policy
from cora.trust.aggregates.surface import load_surface

_log = get_logger(__name__)

# Bootstrap Policy id. Bound to (conduit=nil, surface=HTTP). Production
# deployments set `TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002`
# to point at it; the seed permits SYSTEM_PRINCIPAL_ID to call
# {DefinePolicy, RegisterActor} so operators can register a real admin
# Actor and promote a real admin Policy. Seeded by
# 20260519200000_seed_default_surfaces_and_v2_policy.sql.
#
# The earlier nil-surface bootstrap policy (...0001) is retired: its
# evaluate-time nil-as-wildcard fold was removed, so it now strict-denies
# every real-surface call. Deployments must use the surface-bound id
# below.
SYSTEM_BOOTSTRAP_POLICY_ID = UUID("00000000-0000-0000-0000-000000000002")

# Default Surfaces seeded by
# `20260519200000_seed_default_surfaces_and_v2_policy.sql`.
#
# Re-exported above from `cora.infrastructure.routing` so historical
# `from cora.trust._bootstrap import SYSTEM_HTTP_SURFACE_ID` callers
# keep working. Canonical home is infrastructure so every BC's
# route/tool can import the per-request resolvers without violating
# tach BC-isolation.


async def verify_bootstrap_seed_present(deps: Kernel) -> None:
    """Fail-fast at lifespan start when the configured bootstrap seed
    stream — or its dependencies — is missing.

    When `trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_ID`, verify the
    bootstrap policy stream and the 3 seeded Surface streams exist, and
    that the policy folded to the HTTP Surface. The policy references the
    HTTP Surface; without the Surface streams, evaluate would deny on a
    phantom surface_id and the verdict audit log would silently skip
    entries (partial-fail mitigation). Otherwise no-op: custom operator
    policies are the operator's responsibility to verify.

    The retired nil-surface bootstrap policy (...0001) is not handled
    here. Its evaluate-time wildcard fold was removed, so it strict-denies
    every real-surface call; a deployment still pointed at it would be
    locked out. Point TRUST_POLICY_ID at the surface-bound id.
    """
    settings = deps.settings

    if settings.trust_policy_id != SYSTEM_BOOTSTRAP_POLICY_ID:
        return

    policy = await load_policy(deps.event_store, SYSTEM_BOOTSTRAP_POLICY_ID)
    if policy is None:
        msg = (
            f"Configured trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_ID} "
            "(bootstrap policy) but the seed stream is missing from the "
            "event store. Re-run `make migrate-apply` — the seed migration "
            "20260519200000_seed_default_surfaces_and_v2_policy.sql is "
            "idempotent (ON CONFLICT DO NOTHING) and safe to re-apply. "
            "See memory/project_conduit_injection_design.md."
        )
        raise RuntimeError(msg)

    # The bootstrap policy binds to SYSTEM_HTTP_SURFACE_ID; without all 3
    # seeded Surfaces present, the audit / authz substrate is broken
    # (partial-fail).
    for surface_id in (
        SYSTEM_HTTP_SURFACE_ID,
        SYSTEM_MCP_STDIO_SURFACE_ID,
        SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    ):
        surface = await load_surface(deps.event_store, surface_id)
        if surface is None:
            msg = (
                f"trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_ID} is configured "
                f"but seeded Surface {surface_id} is missing from the event "
                "store — the policy references the HTTP Surface and the audit "
                "path expects all 3. Re-run `make migrate-apply`; the seed "
                "migration is idempotent."
            )
            raise RuntimeError(msg)

    # Assert the bootstrap policy's surface_id binding is correct. A
    # typo'd / mis-wired seed (folded surface_id != HTTP) would silently
    # deny every request, since evaluate strict-matches the surface.
    if policy.surface_id != SYSTEM_HTTP_SURFACE_ID:
        msg = (
            f"trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_ID} was loaded but "
            f"folded with surface_id={policy.surface_id} instead of the "
            f"expected SYSTEM_HTTP_SURFACE_ID ({SYSTEM_HTTP_SURFACE_ID}). The "
            "seed migration may have been mutated post-seed, or a non-seed "
            "PolicyDefined event was appended to this stream. Investigate the "
            "event log."
        )
        raise RuntimeError(msg)


async def warn_if_verdict_log_dormant(deps: Kernel) -> None:
    """Warn (loudly, once at boot) when authz is ENFORCED but the
    per-Conduit Verdict audit log cannot populate.

    `TrustAuthorize` writes a Verdict row per decision only when the
    conduit a command flows through has an open verdict logbook. Handlers
    currently route every command through the nil-sentinel conduit
    (surface / conduit injection is not wired yet), and no verdict
    logbook is seeded there, so the audit log silently stays empty even
    with enforcement on. Surfacing it here turns a silent gap into a
    boot-time heads-up rather than a discovery during a compliance audit.
    Authz decisions are still captured in structured logs
    (`trust_authorize.allow` / `trust_authorize.deny`) and OTel spans.

    Non-fatal by design: a known-limitation notice, not a misconfig. When
    `trust_policy_id` is unset (AllowAll) there are no decisions to record
    and no warning is emitted.
    """
    settings = deps.settings
    if settings.trust_policy_id is None:
        return

    conduit = await load_conduit(deps.event_store, NIL_SENTINEL_ID)
    if conduit is not None and conduit.logbooks.get(LOGBOOK_KIND_VERDICT) is not None:
        return

    _log.warning(
        "trust_authorize.verdict_log_dormant",
        trust_policy_id=str(settings.trust_policy_id),
        conduit_id=str(NIL_SENTINEL_ID),
        detail=(
            "Authorization is ENFORCED but the per-Conduit Verdict audit log "
            "will NOT populate: handlers route through the nil-sentinel "
            "conduit, which has no open verdict logbook (conduit injection is "
            "not wired yet). Authz decisions are still recorded in structured "
            "logs (trust_authorize.allow / trust_authorize.deny) and OTel "
            "spans. See memory project_authorization_envelope_design (watch "
            "item 6) + project_conduit_injection_design."
        ),
    )


__all__ = [
    "SYSTEM_BOOTSTRAP_POLICY_ID",
    "SYSTEM_HTTP_SURFACE_ID",
    "SYSTEM_MCP_STDIO_SURFACE_ID",
    "SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID",
    "SYSTEM_PRINCIPAL_ID",
    "verify_bootstrap_seed_present",
    "warn_if_verdict_log_dormant",
]
