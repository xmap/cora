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
    SYSTEM_IN_PROCESS_SURFACE_ID,
    SYSTEM_LOCAL_CONDUIT_ID,
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

# Default Surfaces. The first three are seeded by
# `20260519200000_seed_default_surfaces_and_v2_policy.sql`;
# `SYSTEM_IN_PROCESS_SURFACE_ID` by a later migration (see
# `cora.infrastructure.schema_version.EXPECTED_SCHEMA_VERSION` for the
# current newest one).
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
    conduit a command flows through has an open verdict logbook. Checks
    the EFFECTIVE conduit — `settings.trust_conduit_id` when an operator
    has opted in, the nil sentinel otherwise (every handler still passes
    nil; `TrustAuthorize` resolves it to the configured conduit only when
    the caller passed nil, per `authorize.py`'s `_effective_conduit_id`).
    An operator who has run `verify_local_conduit_seed_present` and
    pointed `trust_conduit_id` at a seeded, logbook-open Conduit sees no
    warning here, because there is nothing dormant to report.

    Non-fatal by design: a known-limitation notice, not a misconfig. When
    `trust_policy_id` is unset (AllowAll) there are no decisions to record
    and no warning is emitted.
    """
    settings = deps.settings
    if settings.trust_policy_id is None:
        return

    effective_conduit_id = settings.trust_conduit_id or NIL_SENTINEL_ID
    conduit = await load_conduit(deps.event_store, effective_conduit_id)
    if conduit is not None and conduit.logbooks.get(LOGBOOK_KIND_VERDICT) is not None:
        return

    _log.warning(
        "trust_authorize.verdict_log_dormant",
        trust_policy_id=str(settings.trust_policy_id),
        conduit_id=str(effective_conduit_id),
        detail=(
            "Authorization is ENFORCED but the per-Conduit Verdict audit log "
            "will NOT populate: commands traverse the nil-sentinel conduit, "
            "which has no open verdict logbook. Set `trust_conduit_id` to "
            "SYSTEM_LOCAL_CONDUIT_ID (seeded by "
            "20260831140000_seed_local_zone_conduit_verdict_logbook.sql) to "
            "populate entries_conduit_verdicts. Authz decisions are still "
            "recorded in structured logs (trust_authorize.allow / "
            "trust_authorize.deny) and OTel spans. See memory "
            "project_authorization_envelope_design (watch item 6) + "
            "project_conduit_injection_design."
        ),
    )


async def verify_local_conduit_seed_present(deps: Kernel) -> None:
    """Fail-fast at lifespan start when `trust_conduit_id` is configured
    but the Conduit it names cannot actually populate the verdict log.

    Same failure this whole area keeps re-learning: asking for an audit
    control and silently not getting one. Two ways that happens here —
    the Conduit stream is missing, or it exists with no open `verdict`
    logbook — and both are checked. No-op when `trust_conduit_id` is
    unset (today's default; every deployment behaves exactly as before).
    """
    settings = deps.settings
    if settings.trust_conduit_id is None:
        return

    conduit = await load_conduit(deps.event_store, settings.trust_conduit_id)
    if conduit is None:
        hint = (
            "Re-run `make migrate-apply` — "
            "20260831140000_seed_local_zone_conduit_verdict_logbook.sql is "
            "idempotent (ON CONFLICT DO NOTHING) and safe to re-apply."
            if settings.trust_conduit_id == SYSTEM_LOCAL_CONDUIT_ID
            else "A custom Conduit must be defined via `POST /conduits` first."
        )
        msg = (
            f"trust_conduit_id={settings.trust_conduit_id} is configured but "
            f"no Conduit stream exists at that id. {hint}"
        )
        raise RuntimeError(msg)

    if conduit.logbooks.get(LOGBOOK_KIND_VERDICT) is None:
        msg = (
            f"trust_conduit_id={settings.trust_conduit_id} is configured and "
            "the Conduit exists, but it has no open verdict logbook, so "
            "TrustAuthorize would resolve to this conduit and still write "
            "nothing to entries_conduit_verdicts. `define_conduit` opens one "
            "automatically for a Conduit created through the API; a hand-"
            "seeded Conduit must include a ConduitLogbookOpened(kind="
            f"{LOGBOOK_KIND_VERDICT!r}) event."
        )
        raise RuntimeError(msg)


async def verify_local_conduit_matches_policy(deps: Kernel) -> None:
    """Fail-fast when `trust_conduit_id` and `trust_policy_id` are both
    set but the configured Policy governs a different Conduit.

    `Policy.evaluate` checks conduit before surface or principal
    (`aggregates/policy/state.py`), so a mismatch here denies EVERY
    command the instant `trust_conduit_id` starts being resolved — not a
    narrowing of what the policy permits, a silent lockout of the whole
    deployment. Existing nil-bound bootstrap/operator policies keep
    working unmigrated as long as this stays unset; this guard is what
    makes leaving them unmigrated safe rather than an oversight.
    """
    settings = deps.settings
    if settings.trust_conduit_id is None or settings.trust_policy_id is None:
        return

    policy = await load_policy(deps.event_store, settings.trust_policy_id)
    if policy is None:
        # verify_bootstrap_seed_present (or an operator's own responsibility
        # for a custom policy) already covers a missing policy stream.
        return

    if policy.conduit_id != settings.trust_conduit_id:
        msg = (
            f"trust_conduit_id={settings.trust_conduit_id} is configured but "
            f"trust_policy_id={settings.trust_policy_id} governs conduit "
            f"{policy.conduit_id}, a different one. Every command would be "
            "denied at the conduit check, before principal or command are "
            "even consulted. Re-define the policy bound to "
            f"{settings.trust_conduit_id}, or point trust_conduit_id at "
            f"{policy.conduit_id} instead."
        )
        raise RuntimeError(msg)


async def verify_in_process_policy_matches_surface(deps: Kernel) -> None:
    """Fail-fast when `trust_in_process_policy_id` is configured but the
    Policy it names does not actually govern the in-process door.

    A policy configured for the backdoor but bound to the wrong Surface —
    or, once `trust_conduit_id` is also set, the wrong Conduit — would
    still be reachable from `_effective_policy_id` at every in-process
    call, but `evaluate` would strict-deny every one of them at the
    surface (or conduit) check, indistinguishable from having no backdoor
    policy configured at all. This is the same "looks wired, governs
    nothing" failure `verify_local_conduit_matches_policy` closes for the
    conduit knob, applied to the second policy slot.
    """
    settings = deps.settings
    if settings.trust_in_process_policy_id is None:
        return

    policy = await load_policy(deps.event_store, settings.trust_in_process_policy_id)
    if policy is None:
        # A missing policy stream is the operator's responsibility to
        # define (this policy has no bootstrap seed); not this guard's
        # concern, same reasoning as verify_local_conduit_matches_policy.
        return

    if policy.surface_id != SYSTEM_IN_PROCESS_SURFACE_ID:
        msg = (
            f"trust_in_process_policy_id={settings.trust_in_process_policy_id} "
            f"is configured but governs surface {policy.surface_id}, not "
            f"SYSTEM_IN_PROCESS_SURFACE_ID ({SYSTEM_IN_PROCESS_SURFACE_ID}). "
            "Every in-process call would be denied at the surface check "
            "instead of reaching this policy's principal/command rules. "
            "Re-define the policy bound to the in-process Surface, or point "
            "trust_in_process_policy_id at one that is."
        )
        raise RuntimeError(msg)

    if settings.trust_conduit_id is not None and policy.conduit_id != settings.trust_conduit_id:
        msg = (
            f"trust_conduit_id={settings.trust_conduit_id} is configured but "
            f"trust_in_process_policy_id={settings.trust_in_process_policy_id} "
            f"governs conduit {policy.conduit_id}, a different one. Every "
            "in-process command would be denied at the conduit check. "
            "Re-define the backdoor policy bound to "
            f"{settings.trust_conduit_id}, or point trust_conduit_id at "
            f"{policy.conduit_id} instead."
        )
        raise RuntimeError(msg)


__all__ = [
    "SYSTEM_BOOTSTRAP_POLICY_ID",
    "SYSTEM_HTTP_SURFACE_ID",
    "SYSTEM_IN_PROCESS_SURFACE_ID",
    "SYSTEM_LOCAL_CONDUIT_ID",
    "SYSTEM_MCP_STDIO_SURFACE_ID",
    "SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID",
    "SYSTEM_PRINCIPAL_ID",
    "verify_bootstrap_seed_present",
    "verify_in_process_policy_matches_surface",
    "verify_local_conduit_matches_policy",
    "verify_local_conduit_seed_present",
    "warn_if_verdict_log_dormant",
]
