"""Unit tests for the `TrustAuthorize` adapter.

Exercises the adapter against `InMemoryEventStore` with a seeded
PolicyDefined event. The adapter is the production path that gates
every cross-BC command through a single configured Policy.

Verdict emission: when the adapter is constructed with
a `VerdictStore`, every Allow / Deny decision writes one
Verdict observation row scoped to the target Conduit's
verdict logbook.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    Allow,
    Conjunct,
    Deny,
    FakeClock,
    FixedIdGenerator,
    PrincipalLiveness,
)
from cora.shared.liveness import LIVENESS_EXEMPT_COMMANDS
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_VERDICT,
    ConduitDefined,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
)
from cora.trust.aggregates.conduit import (
    event_type_name as conduit_event_type_name,
)
from cora.trust.aggregates.conduit import (
    to_payload as conduit_to_payload,
)
from cora.trust.aggregates.conduit.entries import InMemoryVerdictStore
from cora.trust.authorize import TrustAuthorize
from tests._authz import seed_policy

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000601")
# Post-3h: handlers pass `UUID(int=0)` (nil sentinel) as conduit_id by
# default; the gating policy must use the same conduit_id to match.
_CONDUIT_ID = UUID(int=0)
_OTHER_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
) -> None:
    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=principals,
        permitted_commands=commands,
        conduit_id=conduit_id,
        occurred_at=_NOW,
    )


@pytest.mark.unit
async def test_returns_allow_when_subject_matches_configured_policy() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "DropDatabase", UUID(int=0))
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_configured_policy_does_not_exist() -> None:
    """Fail-closed: configured policy missing from event store → Deny.
    Pinned because a future change to permissive-on-missing would be a
    significant security regression and must be deliberate."""
    store = InMemoryEventStore()  # nothing seeded
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "not found" in result.reason.lower()
    assert str(_POLICY_ID) in result.reason


@pytest.mark.unit
async def test_denies_when_caller_conduit_id_does_not_match_policy() -> None:
    """TrustAuthorize forwards the caller's conduit_id to `evaluate`.

    A policy bound to one conduit denies calls on another. Pinned
    because this is the whole point of 3h — without it the
    conduit_id parameter on the port shape would be cosmetic.
    (3g had it ignored; 3g's no-op test was replaced by this one.)
    """
    store = InMemoryEventStore()
    # Policy governs `_OTHER_CONDUIT_ID`, NOT the nil conduit handlers
    # currently pass.
    await _seed_policy(store, conduit_id=_OTHER_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    # Caller passes the nil conduit_id → mismatch → Deny even though
    # principal + command are permitted.
    denied_nil = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(denied_nil, Deny)
    assert "conduit" in denied_nil.reason.lower()

    # Caller passes a third, unrelated conduit_id → also Deny.
    third_conduit = UUID("01900000-0000-7000-8000-00000000bbbb")
    denied_other = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", third_conduit)
    assert isinstance(denied_other, Deny)
    assert "conduit" in denied_other.reason.lower()

    # Caller passes the policy's own conduit_id → Allow (sanity check
    # that conduit-matching is what gates, not some other invariant).
    allowed = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _OTHER_CONDUIT_ID)
    assert isinstance(allowed, Allow)


@pytest.mark.unit
async def test_loads_policy_on_each_call_no_caching() -> None:
    """Pin the no-caching contract for TrustAuthorize policy loads.

    Changing the policy in the store between calls is reflected on
    the very next call. (Future caching + LISTEN/NOTIFY invalidation
    would change this; should be a deliberate change.)

    Reseeding is awkward here (PolicyDefined is genesis-only); instead
    we verify the load happens by deleting the seeded event and
    showing the next call returns Deny rather than the previously-
    loaded Allow.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    first = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(first, Allow)

    # Drop the policy (white-box: InMemoryEventStore exposes its dict).
    store._streams.pop(("Policy", _POLICY_ID))  # type: ignore[attr-defined]  # pyright: ignore[reportUnknownMemberType]

    second = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(second, Deny)
    assert "not found" in second.reason.lower()


# ---------- Verdict emission ----------


_OBS_EVENT_ID = UUID("01900000-0000-7000-8000-000000000711")
_OBS_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_TARGET_CONDUIT_ID = UUID("01900000-0000-7000-8000-000000000c01")
_TRAVERSALS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000000c02")


async def _seed_conduit_with_open_verdict_logbook(
    store: InMemoryEventStore,
    *,
    conduit_id: UUID = _TARGET_CONDUIT_ID,
    logbook_id: UUID = _TRAVERSALS_LOGBOOK_ID,
) -> None:
    """Seed a Conduit + an open verdict logbook directly into the store."""
    defined = ConduitDefined(
        conduit_id=conduit_id,
        name="Test conduit",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_OBS_NOW,
    )
    opened = ConduitLogbookOpened(
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_VERDICT,
        schema=LogbookSchema(fields={"x": LogbookFieldSpec(type="string")}),
        occurred_at=_OBS_NOW,
    )
    new_events = [
        to_new_event(
            event_type=conduit_event_type_name(e),
            payload=conduit_to_payload(e),
            occurred_at=e.occurred_at,
            event_id=uuid4(),
            command_name="DefineConduit",
            correlation_id=uuid4(),
            principal_id=uuid4(),
        )
        for e in (defined, opened)
    ]
    await store.append("Conduit", conduit_id, expected_version=0, events=new_events)


@pytest.mark.unit
async def test_init_rejects_verdict_store_without_clock_and_id_generator() -> None:
    """Wiring guard: missing clock or id_generator surfaces at startup."""
    store = InMemoryEventStore()
    with pytest.raises(ValueError, match="requires both clock and id_generator"):
        TrustAuthorize(
            store,
            policy_id=_POLICY_ID,
            verdict_store=InMemoryVerdictStore(),
            # clock + id_generator deliberately omitted
        )


@pytest.mark.unit
async def test_skips_traversal_emission_when_verdict_store_is_unset() -> None:
    """Backward-compat: TrustAuthorize with no verdict_store works
    exactly like it did before the verdict store landed: pure authz, no side effects."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)
    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_emits_traversal_on_allow_when_conduit_has_open_logbook() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Allow)

    rows = verdicts.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_id == _OBS_EVENT_ID
    assert row.conduit_id == _TARGET_CONDUIT_ID
    assert row.logbook_id == _TRAVERSALS_LOGBOOK_ID
    assert row.actor_id == _ALLOWED_PRINCIPAL
    assert row.command_name == "RegisterActor"
    assert row.decision == "Allow"
    assert row.reason is None
    assert row.occurred_at == _OBS_NOW


@pytest.mark.unit
async def test_emits_traversal_on_deny_with_reason_attached() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Deny)

    rows = verdicts.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.decision == "Deny"
    assert row.reason is not None
    assert "principal" in row.reason.lower()


@pytest.mark.unit
async def test_skips_traversal_emission_when_conduit_does_not_exist() -> None:
    """Best-effort: missing Conduit logs a warning but doesn't fail
    the authz call. Today's handlers pass UUID(int=0) sentinel which
    has no Conduit aggregate behind it, so until conduit-routing
    lands, most commands won't have verdicts emitted."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    # No Conduit seeded.

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)
    # No verdict recorded because the target Conduit doesn't exist.
    assert verdicts.all() == []


@pytest.mark.unit
async def test_skips_traversal_when_verdict_logbook_was_closed() -> None:
    """If the verdict logbook has been closed, the logbook-id
    resolver returns None and emission is skipped."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    # Append a ConduitLogbookClosed for the same logbook.
    closed = ConduitLogbookClosed(
        conduit_id=_TARGET_CONDUIT_ID,
        logbook_id=_TRAVERSALS_LOGBOOK_ID,
        occurred_at=_OBS_NOW,
    )
    closed_envelope = to_new_event(
        event_type=conduit_event_type_name(closed),
        payload=conduit_to_payload(closed),
        occurred_at=closed.occurred_at,
        event_id=uuid4(),
        command_name="CloseConduitChannel",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    await store.append(
        "Conduit",
        _TARGET_CONDUIT_ID,
        expected_version=2,
        events=[closed_envelope],
    )

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Allow)
    assert verdicts.all() == []


class _FixedLivenessLookup:
    """Returns one liveness value for every principal."""

    def __init__(self, liveness: PrincipalLiveness) -> None:
        self._liveness = liveness

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        _ = principal_id
        return self._liveness


class _FailingLivenessLookup:
    """Raises, standing in for an event-store hiccup mid-beamtime."""

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        _ = principal_id
        msg = "event store unreachable"
        raise RuntimeError(msg)


@pytest.mark.unit
async def test_unwired_liveness_lookup_leaves_the_gate_unchanged() -> None:
    """The default wiring must not start refusing anything.

    Enforcement is opt-in, so every deployment and every test that does
    not wire a lookup keeps exactly the behaviour it had before liveness
    existed.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY})


@pytest.mark.unit
async def test_deactivated_principal_is_refused_though_the_policy_permits_it() -> None:
    """The whole point of the slice, in one test.

    The Policy still names this principal and still permits the command.
    Deactivation alone turns the Allow into a Deny, which is what it
    already does for an agent and has never done for a person.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        liveness_lookup=_FixedLivenessLookup(PrincipalLiveness.DEACTIVATED),
        liveness_enforced=True,
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Deny)
    assert "reactivate_actor" in result.reason


@pytest.mark.unit
async def test_active_principal_still_permitted_with_liveness_wired() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        liveness_lookup=_FixedLivenessLookup(PrincipalLiveness.ACTIVE),
        liveness_enforced=True,
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY, Conjunct.LIVENESS})


@pytest.mark.unit
async def test_liveness_read_failure_fails_open_without_naming_the_conjunct() -> None:
    """A broken lookup must not lock out a live beamline.

    Fail-closed here would turn a transient event-store fault into a
    site-wide outage, which is worse than briefly not enforcing a switch
    an operator flips by hand. The verdict still tells the truth: the
    conjunct is absent from `evaluated`, so nothing claims a check ran.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        liveness_lookup=_FailingLivenessLookup(),
        liveness_enforced=True,
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY})


class _RecordingLivenessLookup:
    """Records which principal it was asked about."""

    def __init__(self, liveness: PrincipalLiveness = PrincipalLiveness.ACTIVE) -> None:
        self._liveness = liveness
        self.asked: list[UUID] = []

    async def liveness_of(self, principal_id: UUID) -> PrincipalLiveness:
        self.asked.append(principal_id)
        return self._liveness


@pytest.mark.unit
async def test_liveness_is_resolved_for_the_caller_not_another_id() -> None:
    """Pins WHICH id reaches the lookup.

    The gate has four UUIDs in scope at this point (principal, conduit,
    surface, policy). Passing the wrong one would authorize against a
    different principal's switch and every other liveness test would
    stay green, because the fakes ignore their argument. This one does
    not ignore it.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    lookup = _RecordingLivenessLookup()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        liveness_lookup=lookup,
        liveness_enforced=True,
    )

    await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _CONDUIT_ID)

    assert lookup.asked == [_ALLOWED_PRINCIPAL]


@pytest.mark.unit
async def test_shadow_posture_logs_without_denying() -> None:
    """Wired but not enforced: the measurement runs, nobody is refused.

    This is the state a deployment sits in for a full beamtime cycle, so
    it needs its own test rather than being inferred from the enforced
    one.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    lookup = _RecordingLivenessLookup(PrincipalLiveness.DEACTIVATED)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, liveness_lookup=lookup)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _CONDUIT_ID)

    assert isinstance(result, Allow)
    assert result.evaluated == frozenset({Conjunct.POLICY})
    assert lookup.asked == [_ALLOWED_PRINCIPAL]


@pytest.mark.unit
async def test_enforcement_without_a_lookup_is_refused_at_construction() -> None:
    """A deployment that asked for enforcement must not silently get none."""
    store = InMemoryEventStore()

    with pytest.raises(ValueError, match="liveness_enforced requires"):
        TrustAuthorize(store, policy_id=_POLICY_ID, liveness_enforced=True)


@pytest.mark.unit
@pytest.mark.parametrize("command_name", sorted(LIVENESS_EXEMPT_COMMANDS))
async def test_exempt_command_is_never_refused_on_liveness(command_name: str) -> None:
    """A switched-off principal can still stop, finish, and record.

    Denying these is the stranded-Procedure and silenced-brake pair the
    human-envelope design fitness-tests against: a scan whose operator was
    deactivated mid-run must still be completable and abortable, and
    switching someone off must never be the reason a stop does not land.
    Parametrized over the whole set so adding a member cannot skip it.
    """
    store = InMemoryEventStore()
    await _seed_policy(store, commands=frozenset({command_name}))
    lookup = _RecordingLivenessLookup(PrincipalLiveness.DEACTIVATED)
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        liveness_lookup=lookup,
        liveness_enforced=True,
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, command_name, _CONDUIT_ID)

    assert isinstance(result, Allow)
    assert lookup.asked == []


# --- policy_posture: observe a refusal without applying it -------------------
#
# The rollout problem these cover. Liveness ships three postures and Policy
# shipped one, so the only way to learn what a first policy is missing was to
# enforce it and watch something break. On a beamline the something could be a
# brake command, since `_BRAKE` is exempt from LIVENESS and nothing exempts it
# from Policy.


@pytest.mark.unit
async def test_shadow_downgrades_a_refusal_it_would_otherwise_apply() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_enforce_is_the_default_so_the_knob_cannot_weaken_a_deployment() -> None:
    """A config that sets trust_policy_id and nothing else keeps enforcing.

    The one regression this whole feature could plausibly introduce is a
    deployment that was gating yesterday and is not today because a new
    setting defaulted the permissive way.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)  # no posture argument

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Deny)


@pytest.mark.unit
async def test_shadow_leaves_a_permitted_call_untouched() -> None:
    """Shadow downgrades refusals and nothing else."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_shadow_keeps_the_conjuncts_it_consulted() -> None:
    """Posture governs what is done with the answer, never whether asked."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    enforced = TrustAuthorize(store, policy_id=_POLICY_ID)
    shadowed = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    refused = await enforced.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))
    observed = await shadowed.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert refused.evaluated == observed.evaluated


@pytest.mark.unit
async def test_a_shadowed_refusal_is_recorded_as_what_actually_happened() -> None:
    """The Verdict row says Allow, and carries the refusal that did not happen.

    This is the shape the whole posture turns on. A row reading `Deny` beside
    a command that went on to succeed would make the record false in the one
    place a reader looks to find out whether something was refused. Recording
    `Allow` with no reason would be true and useless: the shadow period exists
    to produce an inventory, and the inventory has to be retrievable from the
    record rather than from stdout.
    """
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
        policy_enforced=False,
    )

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Allow)

    rows = verdicts.all()
    assert len(rows) == 1
    assert rows[0].decision == "Allow"
    assert rows[0].reason is not None
    assert rows[0].reason.startswith("shadow, not enforced: ")
    # The counterfactual survives intact, not just its marker: an operator
    # reading the logbook has to see WHY enforcement would have refused.
    assert "permitted set" in rows[0].reason
    assert rows[0].actor_id == _OTHER_PRINCIPAL
    assert rows[0].command_name == "RegisterActor"


@pytest.mark.unit
async def test_an_allow_carries_no_shadow_reason() -> None:
    """Only a downgraded refusal is annotated, so the prefix stays a filter."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
        policy_enforced=False,
    )

    await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)

    assert verdicts.all()[0].reason is None


# --- what the log says a shadowed call did -----------------------------------
#
# The first live shadow window on the 2-BM deployment logged BOTH
# `trust_authorize.deny` and `policy_shadow_near_miss` for every near-miss,
# because the decision was logged before the posture was applied. Counting
# refusals out of the log therefore counted refusals that never happened, which
# is the one number a shadow period exists to produce. These pin the ordering
# rather than the wording.


def _log_events(captured: Sequence[Mapping[str, object]]) -> list[object]:
    return [entry.get("event") for entry in captured]


def _entry(captured: Sequence[Mapping[str, object]], event: str) -> Mapping[str, object]:
    return next(e for e in captured if e.get("event") == event)


@pytest.mark.unit
async def test_a_shadowed_refusal_is_never_logged_as_a_deny() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    with structlog.testing.capture_logs() as captured:
        result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)

    assert isinstance(result, Allow)
    events = _log_events(captured)
    assert "trust_authorize.deny" not in events
    assert "trust_authorize.allow" in events
    assert "trust_authorize.policy_shadow_near_miss" in events


@pytest.mark.unit
async def test_the_allow_line_for_a_shadowed_refusal_carries_the_counterfactual() -> None:
    """Moving the line must not cost the reason it was carrying.

    An operator reading only the allow stream still has to be able to tell a
    genuine permit from a refusal that was observed and dropped.
    """
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    with structlog.testing.capture_logs() as captured:
        await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)

    allow = _entry(captured, "trust_authorize.allow")
    reason = allow["shadowed_reason"]
    assert isinstance(reason, str)
    assert reason.startswith("shadow, not enforced: ")
    assert "permitted set" in reason


@pytest.mark.unit
async def test_a_genuine_allow_is_not_annotated_as_shadowed() -> None:
    """The discriminator has to separate the two, not mark everything."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, policy_enforced=False)

    with structlog.testing.capture_logs() as captured:
        await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)

    allow = _entry(captured, "trust_authorize.allow")
    assert allow["shadowed_reason"] is None
    assert "trust_authorize.policy_shadow_near_miss" not in _log_events(captured)


@pytest.mark.unit
async def test_an_enforced_refusal_is_still_logged_as_a_deny() -> None:
    """The move must not silence the posture that does refuse."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    with structlog.testing.capture_logs() as captured:
        result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)

    assert isinstance(result, Deny)
    events = _log_events(captured)
    assert "trust_authorize.deny" in events
    assert "trust_authorize.allow" not in events
    assert "trust_authorize.policy_shadow_near_miss" not in events


# --- resolving an unspecified conduit_id --------------------------------
#
# `trust_conduit_id` lets a deployment name its one real Conduit once, in
# configuration, instead of at every one of the ~180 call sites that
# currently pass the nil sentinel. The property under test: the SAME
# resolved value must feed both the Policy evaluation and the Verdict
# write, so the row that gets written can never describe a conduit the
# command was not actually evaluated against.


@pytest.mark.unit
async def test_an_unspecified_conduit_resolves_to_the_configured_one() -> None:
    """The caller passes nil; the policy is bound to the configured conduit."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, conduit_id=_TARGET_CONDUIT_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_an_unspecified_conduit_still_denies_a_mismatched_policy() -> None:
    """Configuring a conduit does not bypass the conduit-mismatch check."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_OTHER_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, conduit_id=_TARGET_CONDUIT_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Deny)
    assert "conduit" in result.reason.lower()


@pytest.mark.unit
async def test_a_callers_own_non_nil_conduit_is_never_overridden() -> None:
    """Configuration is a default for UNSPECIFIED, never an override."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_OTHER_CONDUIT_ID)
    # Configured conduit is _TARGET_CONDUIT_ID, but the caller passes a
    # real conduit_id of its own -- the policy bound to _OTHER_CONDUIT_ID
    # must still be the one evaluated.
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID, conduit_id=_TARGET_CONDUIT_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _OTHER_CONDUIT_ID)

    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_no_configured_conduit_leaves_nil_untouched() -> None:
    """Default (conduit_id=None): today's behaviour, unchanged."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=UUID(int=0))
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_the_verdict_row_names_the_same_conduit_the_policy_was_evaluated_against() -> None:
    """The row and the decision can never disagree about which conduit.

    Resolution happens once, in `_effective_conduit_id`, and the SAME
    value is threaded to both `decide_authorization` and `_emit_verdict`.
    A resolver called twice (or a stale unresolved value reaching the
    verdict write) could in principle diverge from what was evaluated;
    this pins that they cannot.
    """
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_verdict_logbook(store)

    verdicts = InMemoryVerdictStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        verdict_store=verdicts,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
        conduit_id=_TARGET_CONDUIT_ID,
    )

    # Caller passes nil; only the resolved conduit_id has an open logbook.
    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))

    assert isinstance(result, Allow)
    rows = verdicts.all()
    assert len(rows) == 1
    assert rows[0].conduit_id == _TARGET_CONDUIT_ID
