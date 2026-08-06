"""Production Authorize-port factory.

Builds the Authorize port adapter for the Kernel. Lives inside
`cora.trust` (not `cora.infrastructure`) so the BC that owns the
authz domain owns the construction wiring: `cora.infrastructure`
stays BC-free at the namespace level (no lazy import workarounds,
no tach `deprecated=true` exceptions).

`build_authorize` is what the composition root (`cora.api.main`)
passes to `build_kernel(...)` as the authorize factory, completing
the dependency direction: infrastructure does not know about BCs;
the composition root wires BCs into the kernel.

## Adapter selection

  - `Settings.trust_policy_id is None` -> `AllowAllAuthorize`
    (permissive default; matches dev/test posture). Only reachable
    when `liveness_posture` is "off": asking for liveness while no
    real gate exists raises instead, because AllowAll consults no
    conjunct and would report zero would-be denials.
  - `Settings.trust_policy_id` set -> `TrustAuthorize` gates every
    command through that single Policy aggregate. See
    `cora/trust/authorize.py` for the bootstrap workflow when
    first enabling real auth in a deployment.

## VerdictStore wiring

When `TrustAuthorize` is constructed, it receives the Trust BC's
`VerdictStore` so it can emit one `Verdict` row per Allow / Deny
decision. The store is built inline (Postgres if the pool is
set, in-memory otherwise) and passed in alongside clock +
id_generator. `AllowAllAuthorize` stays bare (no entries from
the permissive default).
"""

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    Clock,
    EventStore,
    IdGenerator,
    PrincipalLivenessLookup,
)
from cora.trust.aggregates.conduit.entries import (
    InMemoryVerdictStore,
    PostgresVerdictStore,
    VerdictStore,
)
from cora.trust.authorize import TrustAuthorize


def build_authorize(
    settings: Settings,
    event_store: EventStore,
    *,
    pool: asyncpg.Pool | None,
    clock: Clock,
    id_generator: IdGenerator,
    liveness_lookup: PrincipalLivenessLookup | None = None,
) -> Authorize:
    """Construct the production Authorize port for the Kernel."""
    posture = settings.liveness_posture

    # Both guards run BEFORE the AllowAll early return, and that ordering is
    # the whole point. An earlier version checked the lookup after it, so a
    # deployment setting liveness_posture=enforce with no trust_policy_id
    # booted permitting every command, with no liveness and no error: the
    # exact "asked for a control and silently got none" degradation the
    # guard exists to prevent, reachable by the one misconfiguration most
    # likely to occur while enabling authz for the first time.
    if posture != "off" and liveness_lookup is None:
        # Unwired plumbing rather than operator error: the composition root
        # owns the adapter because this module cannot import the Access BC.
        msg = (
            f"liveness_posture={posture!r} requires a PrincipalLivenessLookup, "
            "but the composition root supplied none"
        )
        raise ValueError(msg)
    if posture != "off" and settings.trust_policy_id is None:
        msg = (
            f"liveness_posture={posture!r} has no effect without trust_policy_id: "
            "AllowAllAuthorize permits every command and consults no conjunct. "
            "Set trust_policy_id, or set liveness_posture=off to say so deliberately."
        )
        raise ValueError(msg)

    if settings.trust_policy_id is None:
        return AllowAllAuthorize()

    verdict_store: VerdictStore = (
        PostgresVerdictStore(pool) if pool is not None else InMemoryVerdictStore()
    )
    return TrustAuthorize(
        event_store,
        policy_id=settings.trust_policy_id,
        verdict_store=verdict_store,
        clock=clock,
        id_generator=id_generator,
        liveness_lookup=liveness_lookup if posture != "off" else None,
        liveness_enforced=posture == "enforce",
    )


__all__ = ["build_authorize"]
