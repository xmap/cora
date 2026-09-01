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

## A second, optional rulebook for the in-process door

`in_process_policy_id` adds exactly one exception to "one policy per
deployment": when set, a call whose `surface_id` is
`SYSTEM_IN_PROCESS_SURFACE_ID` (CORA's own background agents, never a
human, never an external caller) is evaluated against THAT policy
instead of `policy_id`. Every other surface, and an in-process call
when this is left unset, resolves to `policy_id` exactly as before --
`_effective_policy_id` is the single place this is decided, mirroring
`_effective_conduit_id`. This is deliberately not a general multi-
surface widening of `Policy` itself (`Policy.surface_id` stays a single
scalar); it is the smallest change that lets the front door and the
backdoor be governed by two different rulebooks on one deployment.

## Conduit semantics

The port passes `conduit_id: UUID`. TrustAuthorize forwards the
caller's `conduit_id` to `evaluate`, which means a policy bound
to one conduit naturally denies calls on another via evaluate's
existing conduit-mismatch check.

Operational consequence: deployments wire `Settings.trust_policy_id`
to a Policy whose `conduit_id` matches what handlers pass. Every
handler passes `UUID(int=0)` (nil sentinel; the ~180-call-site sweep
that would let a handler pass a real conduit_id of its own is
deferred, per `project_conduit_injection_design.md` WI10, until a
real multi-zone need exists), so the gating policy must use
`conduit_id=UUID(int=0)` unless a deployment configures
`Settings.trust_conduit_id`.

`trust_conduit_id` resolves the UNSPECIFIED case: when the caller
passes the nil sentinel AND a conduit is configured, that conduit is
used for both the Policy evaluation and the Verdict write, never one
without the other, so the row that gets written can never disagree
with the decision that produced it (`_effective_conduit_id` is the
single place this is decided). A caller that passes a real,
non-nil conduit_id of its own is never overridden — configuration is
a default for "unspecified", not an override for "specified". Once
HTTP / MCP / A2A surfaces start injecting their own conduit_ids,
deployments will define one Policy per conduit (single-policy-per-
deployment shape stays; the operator picks which conduit to gate
first, others fall through to deny).

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
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_IN_PROCESS_SURFACE_ID
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

# Marks a Verdict row whose refusal was observed rather than applied. A
# reader filtering the verdict logbook for what an enforcing gate would
# have stopped looks for this prefix.
_SHADOW_REASON_PREFIX = "shadow, not enforced: "


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
        policy_enforced: bool = True,
        conduit_id: UUID | None = None,
        in_process_policy_id: UUID | None = None,
    ) -> None:
        if liveness_enforced and liveness_lookup is None:
            msg = "TrustAuthorize: liveness_enforced requires a liveness_lookup to be wired"
            raise ValueError(msg)
        if verdict_store is not None and (clock is None or id_generator is None):
            msg = "TrustAuthorize: verdict_store requires both clock and id_generator to be wired"
            raise ValueError(msg)
        self._event_store = event_store
        self._policy_id = policy_id
        # The configured conduit a caller's UNSPECIFIED (nil) conduit_id
        # resolves to. None leaves every caller's conduit_id exactly as
        # passed, which for every handler today means nil — today's
        # behaviour, unchanged. See `_effective_conduit_id`.
        self._conduit_id = conduit_id
        # The second, optional rulebook: governs calls that arrive through
        # the in-process Surface (`SYSTEM_IN_PROCESS_SURFACE_ID`) when set,
        # leaving every other surface -- and an in-process call when this
        # is unset -- resolved to `policy_id` exactly as before. See
        # `_effective_policy_id`.
        self._in_process_policy_id = in_process_policy_id
        # Defaults to True so that adding this knob cannot weaken a
        # deployment that already gates: an existing config that sets
        # `trust_policy_id` and nothing else keeps enforcing exactly as it
        # did. Only an explicit `policy_posture=shadow` downgrades, and the
        # boot path refuses that combination without a policy id.
        #
        # There is no third "off" state here on purpose. Off is already
        # spelled `trust_policy_id is None`, which returns
        # `AllowAllAuthorize` from `build_authorize` before this class is
        # constructed at all, and two ways to say the same thing is how a
        # deployment ends up believing it is gated when it is not.
        self._policy_enforced = policy_enforced
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

    def _effective_conduit_id(self, conduit_id: UUID) -> UUID:
        """Resolve an UNSPECIFIED conduit_id to the configured one.

        Called exactly once per `authorize()` call, and the single result
        feeds BOTH the Policy evaluation and the Verdict write below, so
        the two can never disagree about which conduit a command
        traversed -- the row that gets written always describes the
        conduit the decision was actually evaluated against.

        `NIL_SENTINEL_ID` is documented (`infrastructure.routing`) as
        meaning "unspecified", not "none", so resolving it to the
        deployment's one configured conduit is a default for the
        unspecified case, not a fabrication. A caller that already
        passes a real, non-nil conduit_id is never overridden -- this
        only fills in what the caller left blank.
        """
        if self._conduit_id is not None and conduit_id == NIL_SENTINEL_ID:
            return self._conduit_id
        return conduit_id

    def _effective_policy_id(self, surface_id: UUID) -> UUID:
        """Resolve which configured Policy governs this call.

        The backdoor rulebook applies only when BOTH hold: the call
        arrived through the in-process Surface, and a backdoor policy is
        actually configured. Every other surface -- and an in-process
        call when no backdoor policy is set -- resolves to the one front
        policy, today's single-rulebook behaviour unchanged.
        """
        if self._in_process_policy_id is not None and surface_id == SYSTEM_IN_PROCESS_SURFACE_ID:
            return self._in_process_policy_id
        return self._policy_id

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult:
        conduit_id = self._effective_conduit_id(conduit_id)
        policy_id = self._effective_policy_id(surface_id)
        liveness = await self._resolve_liveness(principal_id, command_name)
        policy = await load_policy(self._event_store, policy_id)
        if policy is None:
            _log.warning(
                "trust_authorize.policy_missing",
                policy_id=str(policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
                conduit_id=str(conduit_id),
                surface_id=str(surface_id),
                correlation_id=str(current_correlation_id()),
            )
            result: AuthzResult = Deny(
                reason=(f"Configured TrustAuthorize policy {policy_id} not found in event store")
            )
        else:
            # Forward the EFFECTIVE conduit_id (was policy.conduit_id
            # previously). evaluate's conduit-mismatch check now
            # meaningfully gates calls — a policy bound to one conduit
            # denies calls on another instead of being evaluated as if
            # it were governing.
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

        result, shadow_reason = self._apply_policy_posture(
            result,
            policy_id=policy_id,
            principal_id=principal_id,
            command_name=command_name,
            surface_id=surface_id,
        )
        self._log_decision(
            result,
            policy_id=policy_id,
            principal_id=principal_id,
            command_name=command_name,
            surface_id=surface_id,
            shadow_reason=shadow_reason,
        )

        if self._verdict_store is not None:
            await self._emit_verdict(
                principal_id=principal_id,
                command_name=command_name,
                conduit_id=conduit_id,
                result=result,
                shadow_reason=shadow_reason,
            )

        return result

    def _log_decision(
        self,
        result: AuthzResult,
        *,
        policy_id: UUID,
        principal_id: UUID,
        command_name: str,
        surface_id: UUID,
        shadow_reason: str | None,
    ) -> None:
        """One line per call, naming what the gate DID.

        Runs AFTER `_apply_policy_posture`, for the same reason the verdict
        row is written after it. A `trust_authorize.deny` line beside a
        command that went on to succeed makes every refusal count taken from
        the log wrong, and taking a refusal count is the entire job of a
        shadow period. The first live shadow window emitted both lines for
        each near-miss and was exactly that misleading.

        The counterfactual is not lost by moving the line: it rides on the
        allow as `shadowed_reason`, beside the `policy_shadow_near_miss`
        warning the posture already emits. Both fields are chosen the same
        way `_emit_verdict` chooses the row's decision and reason, so a
        reader cannot find the log and the record disagreeing about a call.
        """
        if isinstance(result, Deny):
            _log.info(
                "trust_authorize.deny",
                policy_id=str(policy_id),
                principal_id=str(principal_id),
                command_name=command_name,
                surface_id=str(surface_id),
                reason=result.reason,
                correlation_id=str(current_correlation_id()),
            )
            return
        _log.info(
            "trust_authorize.allow",
            policy_id=str(policy_id),
            principal_id=str(principal_id),
            command_name=command_name,
            surface_id=str(surface_id),
            shadowed_reason=shadow_reason,
            correlation_id=str(current_correlation_id()),
        )

    def _apply_policy_posture(
        self,
        result: AuthzResult,
        *,
        policy_id: UUID,
        principal_id: UUID,
        command_name: str,
        surface_id: UUID,
    ) -> tuple[AuthzResult, str | None]:
        """In shadow, turn a refusal into a recorded near-miss.

        Runs BEFORE `_emit_verdict` deliberately, so the Verdict row says
        what the system actually did. A row reading `Deny` beside a command
        that went on to succeed would make the record false in the one place
        a reader goes to find out whether something was refused, and no
        amount of surrounding log context repairs that.

        The counterfactual is not thrown away: it rides in the row's own
        `reason`, prefixed, so the shadow log is queryable from the record
        rather than only from stdout. That is what makes a shadow period
        usable as the INVENTORY for the eventual policy: every principal and
        command an enforcing gate would have refused is retrievable
        afterwards, with its reason, from the verdict logbook.

        `evaluated` is carried across unchanged. The conjuncts really were
        consulted; posture governs what is done with the answer, never
        whether the question was asked.
        """
        if self._policy_enforced or not isinstance(result, Deny):
            return result, None
        _log.warning(
            "trust_authorize.policy_shadow_near_miss",
            policy_id=str(policy_id),
            principal_id=str(principal_id),
            command_name=command_name,
            surface_id=str(surface_id),
            would_deny_reason=result.reason,
            correlation_id=str(current_correlation_id()),
        )
        return Allow(evaluated=result.evaluated), f"{_SHADOW_REASON_PREFIX}{result.reason}"

    async def _emit_verdict(
        self,
        *,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        result: AuthzResult,
        shadow_reason: str | None = None,
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
        # `shadow_reason` is set only on an Allow that a shadow posture
        # downgraded from a Deny, so the two are never both present: the
        # row reports the decision that was ACTED ON, and carries the
        # refusal that did not happen as its reason.
        reason = result.reason if isinstance(result, Deny) else shadow_reason

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
