"""TrustAuthorize: production adapter for the cross-BC `Authorize` port.

Implements `cora.infrastructure.ports.Authorize` by loading a single
configured Policy aggregate and delegating to `decide_authorization`
in `cora.trust._authorization_decision`, the one place a decision is
reached. This is the structural moment where the Trust BC's pure domain
logic (Zone / Conduit / Policy + define + evaluate) gates real commands
across every BC.

This adapter supplies a `ResolvedContext`: it resolved every input the
decision consults, so the answer is the system's real one. The query
slices supply a `PolicyOnlyContext` for hypotheticals and get an answer
stamped as partial. Adding a conjunct means changing the decision
module, not this adapter, which is the point of routing through it.

## Shape: single configured policy

The constructor takes one `policy_id`. Every `authorize(...)` call
loads that policy via `load_policy` (fold-on-read; O(events-per-stream)
per request) and evaluates against it.

This deliberately ships the smallest useful gating wire-up:
- One policy per deployment (set via `Settings.trust_policy_id`)
- No projection / cross-stream resolution
- No caching (each request hits the event store)

Multi-policy resolution + caching + LISTEN/NOTIFY invalidation land
in later phases when projection-worker infrastructure exists.

## Conduit semantics

The port passes `conduit_id: UUID`. TrustAuthorize forwards the
caller's `conduit_id` to `evaluate`, which means a policy bound
to one conduit naturally denies calls on another via evaluate's
existing conduit-mismatch check.

Operational consequence: deployments wire `Settings.trust_policy_id`
to a Policy whose `conduit_id` matches what handlers pass. Today
every handler passes `UUID(int=0)` (nil sentinel; surface-level
conduit injection is the next step), so the gating policy must use
`conduit_id=UUID(int=0)`. Once HTTP / MCP / A2A surfaces start
injecting their own conduit_ids, deployments will define one Policy
per conduit (single-policy-per-deployment shape stays; the operator
picks which conduit to gate first, others fall through to deny).

## Bootstrap problem (closed)

Without a seed, the configured policy must already permit
`DefinePolicy` for someone to define new policies through the API —
chicken-and-egg. The Atlas migration
`20260519200000_seed_default_surfaces_and_v2_policy.sql` seeds the
System Bootstrap Policy at a fixed UUID
(`cora.trust._bootstrap.SYSTEM_BOOTSTRAP_POLICY_ID`) permitting
`SYSTEM_PRINCIPAL_ID` to call `{DefinePolicy, RegisterActor}` on the
nil conduit, bound to the seeded HTTP Surface. Production deployments
collapse the prior 3-step dance to a single env var:

    TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002

Operators then register a real admin Actor and promote a real admin
Policy via the API, and (optionally) re-point `TRUST_POLICY_ID` at
the new policy. Design lock + anti-hooks:
`memory/project_bootstrap_policy_design.md`. The Settings default
flip to non-None is deferred (WI8) pending a test-fixture audit;
~2400 tests rely on AllowAllAuthorize today.

## Caller authz vs evaluation result

`Authorize.authorize` returns `Allow` or `Deny`. From the caller's
perspective there's no distinction between "the policy permits you"
(Allow) and "no policy applies / always Allow" (Allow); both gate
through. Same for Deny — the reason string carries the diagnostic
("Principal X not in policy Y's permitted set" vs "Configured
TrustAuthorize policy Y not found in event store").

If the configured policy is missing from the event store, this
adapter returns Deny — fail-closed. A Settings-time check that the
policy exists at startup would surface this earlier; deferred.

## Optional verdict entry emission

When constructed with a `VerdictStore`, every Allow / Deny
decision additionally writes one `Verdict` entry row
to the per-Conduit verdict logbook. This is the per-Conduit
authz audit log — every command that traverses a Conduit is
captured with actor, command, decision, reason, and timestamps.

Wiring is opt-in (constructor param defaults to None) so existing
test paths and the AllowAllAuthorize fallback don't accumulate
entries. When `verdict_store` is provided, `clock` and
`id_generator` are required (for `occurred_at` and `event_id`); the
constructor enforces this so missed wiring fails loud at app
startup, not at the first authz call.

Logbook id resolution: TrustAuthorize loads the target Conduit
aggregate via `load_conduit` and reads `conduit.logbooks[
LOGBOOK_KIND_VERDICT]`. The Conduit stream is short (genesis +
logbook-open, ~handful of events) so per-call fold cost is small;
per-process caching keyed on `conduit_id` is the natural future
optimization. If the Conduit doesn't exist (typical for
`UUID(int=0)` sentinel until conduit-routing lands) or has no
verdict logbook open, the entry write is silently skipped with
a warn log — the authz decision itself is unaffected.

`correlation_id` for the entry row comes from
`current_correlation_id()` (the active OTel span's trace_id encoded
as a UUID); same source the calling handler uses for its event
envelope, so entry rows correlate naturally with the events that
triggered them.
"""

from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
    Clock,
    Deny,
    EventStore,
    IdGenerator,
    PrincipalLiveness,
    PrincipalLivenessLookup,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.liveness import is_liveness_exempt
from cora.trust._authorization_decision import (
    AuthorizationRequest,
    ResolvedContext,
    decide_authorization,
)
from cora.trust.aggregates.conduit import LOGBOOK_KIND_VERDICT, load_conduit
from cora.trust.aggregates.conduit.entries import (
    Verdict,
    VerdictDecision,
    VerdictStore,
)
from cora.trust.aggregates.policy import load_policy

_log = get_logger(__name__)


class TrustAuthorize:
    """Authorize port adapter that gates via a single configured Policy."""

    def __init__(
        self,
        event_store: EventStore,
        *,
        policy_id: UUID,
        verdict_store: VerdictStore | None = None,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
        liveness_lookup: PrincipalLivenessLookup | None = None,
        liveness_enforced: bool = False,
    ) -> None:
        if liveness_enforced and liveness_lookup is None:
            msg = "TrustAuthorize: liveness_enforced requires a liveness_lookup to be wired"
            raise ValueError(msg)
        if verdict_store is not None and (clock is None or id_generator is None):
            msg = "TrustAuthorize: verdict_store requires both clock and id_generator to be wired"
            raise ValueError(msg)
        self._event_store = event_store
        self._policy_id = policy_id
        self._verdict_store = verdict_store
        self._clock = clock
        self._id_generator = id_generator
        # Two knobs, not one, because measuring must be possible without
        # refusing. A wired lookup with `liveness_enforced=False` is SHADOW
        # mode: every non-active caller is logged and none is denied, which
        # is the adoption measurement the human-envelope design requires
        # before any conjunct depends on it. Enforcement without a lookup is
        # rejected at construction rather than silently degrading to "off",
        # because a deployment that asked for enforcement and got none is
        # exactly the failure this arrangement exists to prevent.
        self._liveness_lookup = liveness_lookup
        self._liveness_enforced = liveness_enforced

    async def _resolve_liveness(
        self, principal_id: UUID, command_name: str
    ) -> PrincipalLiveness | None:
        """Resolve the CALLER's liveness, or None when the conjunct cannot run.

        `principal_id` is the caller, never a command target. Passing the
        wrong id here would silently authorize against a different
        principal's switch, so `test_liveness_is_resolved_for_the_caller`
        pins the argument rather than trusting the call site.

        None means the conjunct is not evaluated, for any of FOUR
        reasons: no lookup wired, the command is exempt, the read
        failed, or the posture is "shadow" (resolved and logged, then
        deliberately withheld from the decision). All four must leave
        `Conjunct.LIVENESS` absent from `evaluated` so no verdict claims
        a check that did not run. Shadow is the easy one to forget when
        editing this, because it is the only case that DOES resolve a
        value and then discards it.

        A failed read FAILS OPEN, loudly. Fail-closed would turn a
        transient event-store fault into a site-wide lockout mid-beamtime,
        which is worse than briefly not enforcing a switch an operator
        flips by hand. The warning is the ONLY compensating control: the
        `Verdict` row carries no conjunct column, so a reader of the
        logbook cannot tell a fail-open request from an enforced one.
        """
        if self._liveness_lookup is None or is_liveness_exempt(command_name):
            return None
        try:
            liveness = await self._liveness_lookup.liveness_of(principal_id)
        except Exception:
            _log.warning(
                "trust_authorize.liveness_unresolved",
                principal_id=str(principal_id),
                command_name=command_name,
                correlation_id=str(current_correlation_id()),
                exc_info=True,
            )
            return None
        if liveness is not PrincipalLiveness.ACTIVE:
            # Emitted in BOTH postures. In shadow this is the entire
            # deliverable (how much would enforcement have refused, and
            # which remedy each case needed); under enforcement it is the
            # operator-facing record of a refusal that already happened.
            _log.info(
                "trust_authorize.liveness_not_active",
                principal_id=str(principal_id),
                command_name=command_name,
                liveness=liveness.value,
                enforced=self._liveness_enforced,
                correlation_id=str(current_correlation_id()),
            )
        return liveness if self._liveness_enforced else None

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult:
        liveness = await self._resolve_liveness(principal_id, command_name)
        policy = await load_policy(self._event_store, self._policy_id)
        if policy is None:
            _log.warning(
                "trust_authorize.policy_missing",
                policy_id=str(self._policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
                conduit_id=str(conduit_id),
                surface_id=str(surface_id),
                correlation_id=str(current_correlation_id()),
            )
            result: AuthzResult = Deny(
                reason=(
                    f"Configured TrustAuthorize policy {self._policy_id} not found in event store"
                )
            )
        else:
            # Forward caller's conduit_id (was policy.conduit_id previously).
            # evaluate's conduit-mismatch check now meaningfully
            # gates calls — a policy bound to one conduit denies calls on
            # another instead of being evaluated as if it were governing.
            # Forward surface_id; defaults to nil where the route
            # layer hasn't been swept to inject the real Surface ID.
            result = decide_authorization(
                AuthorizationRequest(
                    principal_id=principal_id,
                    command_name=command_name,
                    conduit_id=conduit_id,
                    surface_id=surface_id,
                ),
                ResolvedContext(policy=policy, liveness=liveness),
            )
            if isinstance(result, Allow):
                _log.info(
                    "trust_authorize.allow",
                    policy_id=str(self._policy_id),
                    principal_id=str(principal_id),
                    command_name=command_name,
                    surface_id=str(surface_id),
                    correlation_id=str(current_correlation_id()),
                )
            else:
                _log.info(
                    "trust_authorize.deny",
                    policy_id=str(self._policy_id),
                    principal_id=str(principal_id),
                    command_name=command_name,
                    surface_id=str(surface_id),
                    reason=result.reason,
                    correlation_id=str(current_correlation_id()),
                )

        if self._verdict_store is not None:
            await self._emit_verdict(
                principal_id=principal_id,
                command_name=command_name,
                conduit_id=conduit_id,
                result=result,
            )

        return result

    async def _emit_verdict(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        result: AuthzResult,
    ) -> None:
        """Best-effort write of one Verdict entry per call.

        Skipped silently with a warn log if the Conduit doesn't exist
        or has no currently-open verdict logbook. The authz
        decision itself is unaffected.
        """
        # Type-narrowed: __init__ enforces that these are non-None
        # whenever verdict_store is set.
        assert self._verdict_store is not None
        assert self._clock is not None
        assert self._id_generator is not None

        conduit = await load_conduit(self._event_store, conduit_id)
        if conduit is None:
            _log.warning(
                "trust_authorize.skip_traversal",
                conduit_id=str(conduit_id),
                reason="conduit_not_found",
                correlation_id=str(current_correlation_id()),
            )
            return
        logbook_id = conduit.logbooks.get(LOGBOOK_KIND_VERDICT)
        if logbook_id is None:
            _log.warning(
                "trust_authorize.skip_traversal",
                conduit_id=str(conduit_id),
                reason="no_open_verdict_logbook",
                correlation_id=str(current_correlation_id()),
            )
            return

        decision_str: VerdictDecision = "Allow" if isinstance(result, Allow) else "Deny"
        reason = result.reason if isinstance(result, Deny) else None

        await self._verdict_store.append(
            [
                Verdict(
                    event_id=self._id_generator.new_id(),
                    conduit_id=conduit_id,
                    logbook_id=logbook_id,
                    actor_id=principal_id,
                    command_name=command_name,
                    decision=decision_str,
                    reason=reason,
                    correlation_id=current_correlation_id(),
                    causation_id=None,
                    occurred_at=self._clock.now(),
                )
            ]
        )
