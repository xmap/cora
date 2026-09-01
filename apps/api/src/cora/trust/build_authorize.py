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
  - `Settings.trust_conduit_id`, when also set, is passed through so
    an UNSPECIFIED (nil) conduit_id resolves to it -- see
    `TrustAuthorize._effective_conduit_id`. Requires `trust_policy_id`
    for the same reason `policy_posture='shadow'` does: `AllowAllAuthorize`
    is never constructed with a conduit_id, so a configured conduit with
    no policy would be read by nothing.
  - `Settings.trust_in_process_policy_id`, when also set, is passed
    through so a call arriving through the in-process Surface is
    governed by that second policy instead -- see
    `TrustAuthorize._effective_policy_id`. Same requirement, same
    reason: `AllowAllAuthorize` is never constructed with a second
    policy id, so one configured with no `trust_policy_id` would be
    read by nothing.

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
    # Same shape, same reason, for the policy knob. Asking for a shadow
    # rollout with no policy to shadow is the misconfiguration that would
    # look most like success: the deployment boots, refuses nothing, records
    # nothing, and an operator waiting for a shadow inventory waits forever.
    if settings.policy_posture == "shadow" and settings.trust_policy_id is None:
        msg = (
            "policy_posture='shadow' has no effect without trust_policy_id: "
            "AllowAllAuthorize reaches no verdict, so nothing would be observed "
            "and the verdict logbook would stay empty. Set trust_policy_id to "
            "the policy you want to shadow."
        )
        raise ValueError(msg)
    # Same shape again for the conduit knob. AllowAllAuthorize is returned
    # below and never constructed with a conduit_id at all, so a configured
    # trust_conduit_id with no trust_policy_id would be read by nothing:
    # not one Verdict row would be written, and nothing would say so short
    # of reading this file.
    if settings.trust_conduit_id is not None and settings.trust_policy_id is None:
        msg = (
            "trust_conduit_id is configured but has no effect without "
            "trust_policy_id: AllowAllAuthorize is never constructed with a "
            "conduit_id, so nothing would resolve to it and the verdict "
            "logbook would stay empty. Set trust_policy_id, or unset "
            "trust_conduit_id to say so deliberately."
        )
        raise ValueError(msg)
    # Same shape again for the backdoor policy knob. AllowAllAuthorize is
    # returned below and never constructed with a second policy id at all,
    # so a configured trust_in_process_policy_id with no trust_policy_id
    # would be read by nothing: every in-process call would keep resolving
    # to no gate at all, not the backdoor rulebook an operator thinks they
    # just turned on.
    if settings.trust_in_process_policy_id is not None and settings.trust_policy_id is None:
        msg = (
            "trust_in_process_policy_id is configured but has no effect "
            "without trust_policy_id: AllowAllAuthorize is never constructed "
            "with a second policy id, so no in-process call would resolve to "
            "it. Set trust_policy_id, or unset trust_in_process_policy_id to "
            "say so deliberately."
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
        policy_enforced=settings.policy_posture == "enforce",
        conduit_id=settings.trust_conduit_id,
        in_process_policy_id=settings.trust_in_process_policy_id,
    )


__all__ = ["build_authorize"]
