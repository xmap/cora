"""The same command, issued by a person and by an agent, through one gate.

D5's exhibit. A human and a software agent each hold a Procedure, both
requests cross the SAME `TrustAuthorize` instance against the SAME Policy,
and the record that results differs in exactly one field.

## Why this runs against TrustAuthorize and not the usual stub

`build_postgres_deps` defaults to `AllowAllAuthorize`, which permits
everything and consults nothing. A paired-hold test on that default would
show two holds succeeding under a gate that never decided, pass on the day
it was written, pass forever, and be blind to the only thing it exists to
catch. Its two sides would derive from one source and agree by
construction, which `project_independent_check_principle.md` names as the
failure mode. So these tests wire the production adapter, with
`liveness_enforced=True` so the Liveness conjunct is actually available to
be consulted.

## What the gate consults varies by command, never by principal

Worth knowing before reading the assertions, and it corrected an earlier
draft of this file. `HoldProcedure` is a BRAKE
(`cora.shared.liveness._BRAKE`) and is deliberately exempt from the
liveness conjunct, so that a principal an operator has switched off can
still stop work already in progress. So a hold is decided on Policy alone,
for a person and for an agent alike, while a routine command like
`StartProcedure` is decided on Policy AND Liveness, again for both alike.

That is the sharper form of the claim than "both were allowed": the set of
questions the gate asks changes with the COMMAND and is identical across
the two principals in both cases.

## What this demonstrates, and what it does not establish

Kind-blindness is ESTABLISHED structurally, not here.
`Authorize.authorize` takes `(principal_id, command_name, conduit_id,
surface_id)`: a bare UUID and three more, no kind to branch on, and
`tests/architecture/test_actor_kind_blindness.py` pins that signature so a
future widening fails. These tests DEMONSTRATE the consequence in a record.
Do not read them as the proof; the proof is that the decision point cannot
receive what it would need in order to discriminate.

## The negative half is the load-bearing half

Two holds succeeding proves little on its own: a gate that says yes to
everything in range would do the same. What separates kind-blindness from
coincidence is that each principal can be refused INDIVIDUALLY, by
identity, using the same denial vocabulary, while neither can be refused
for what it is. That is `test_the_gate_refuses_by_identity_not_by_kind`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from cora.access.adapters.event_store_principal_liveness_lookup import (
    EventStorePrincipalLivenessLookup,
)
from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.agent.aggregates.agent import ModelRef
from cora.agent.features.define_agent import DefineAgent
from cora.agent.features.define_agent import bind as bind_define_agent
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow, Conjunct, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_HTTP_SURFACE_ID
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    event_type_name,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.features.hold_procedure import bind as bind_hold
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.trust.authorize import TrustAuthorize
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.define_policy import bind as bind_define_policy
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_BOOTSTRAP_PRINCIPAL = UUID("01900000-0000-7000-8000-0000020e0001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000020e0002")

# The two commands the exhibit's Policy permits. StartProcedure is here
# because a Procedure must be Running before it can be Held, so the setup
# leg has to cross the same gate the exhibit does.
_PERMITTED = frozenset({"StartProcedure", "HoldProcedure"})

# Normalizes policy ids out of a denial reason so two refusals can be
# compared as sentences rather than as strings.
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _ids(tag: int, count: int = 60) -> list[UUID]:
    """A distinct, generous id queue per Kernel.

    Two Kernels share one event store here, so their queues must not
    overlap or the second writer collides on `events_event_id_unique`.
    `tag` partitions them. Exhaustion raises loudly, so over-supplying
    hides nothing.
    """
    return [
        UUID(f"01900000-0000-7000-8000-{tag:04x}020e{n:04x}") for n in range(0x100, 0x100 + count)
    ]


async def _seed_defined_procedure(deps: Kernel, procedure_id: UUID, event_id: UUID) -> None:
    """Seed one ProcedureRegistered so the Procedure exists in `Defined`."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM governed hold exhibit",
        kind="commissioning",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(registered),
                payload=to_payload(registered),
                occurred_at=registered.occurred_at,
                event_id=event_id,
                command_name="RegisterProcedure",
                correlation_id=_CORRELATION_ID,
                principal_id=_BOOTSTRAP_PRINCIPAL,
            )
        ],
    )


async def _principals(deps: Kernel, db_pool: asyncpg.Pool) -> tuple[UUID, UUID]:
    """Register one human Actor and define one Agent; return both ids.

    `define_agent` co-registers an Actor with `kind=agent` at the SAME id
    it gives the Agent, which is why a single `principal_id` field can
    carry either and why the liveness lookup needs no mapping step.
    """
    profile_store = make_pg_profile_store(db_pool)
    human_id = await bind_register_actor(deps, profile_store=profile_store)(
        RegisterActor(name="2-BM Beamline Operator, governed-hold exhibit"),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )
    agent_id = await bind_define_agent(deps, profile_store=profile_store)(
        DefineAgent(
            kind="RunSupervisor",
            name="Run Supervisor, governed-hold exhibit",
            version="v1",
            model_ref=ModelRef(
                provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001"
            ),
            description="Holds a Procedure when it judges the conduct should pause.",
            capabilities=frozenset({"supervise"}),
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )
    return human_id, agent_id


async def _policy(deps: Kernel, permitted: frozenset[UUID]) -> UUID:
    """Define ONE Policy admitting `permitted` for the exhibit's commands.

    One policy, not the two the 2-BM fixture installs. That fixture splits
    an operations Policy from an agent Policy, which is a configuration
    convention rather than a property of the gate, and routing the two
    principals through separate Policies would leave "through one gate"
    true only by a generous reading.
    """
    return await bind_define_policy(deps)(
        DefinePolicy(
            name="Governed hold exhibit Policy",
            conduit_id=NIL_SENTINEL_ID,
            permitted_principal_ids=permitted,
            permitted_commands=_PERMITTED,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )


def _gate(deps: Kernel, policy_id: UUID) -> TrustAuthorize:
    """The production adapter, with liveness actually enforced."""
    return TrustAuthorize(
        deps.event_store,
        policy_id=policy_id,
        liveness_lookup=EventStorePrincipalLivenessLookup(deps.event_store),
        liveness_enforced=True,
    )


async def _held_envelopes(db_pool: asyncpg.Pool, ids: tuple[UUID, ...]) -> list[dict[str, Any]]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_id, event_type, schema_version, payload, metadata, principal_id
            FROM events
            WHERE stream_type = 'Procedure' AND event_type = 'ProcedureHeld'
              AND stream_id = ANY($1::uuid[])
            ORDER BY version
            """,
            list(ids),
        )
    return [dict(r) for r in rows]


@pytest.mark.integration
async def test_a_person_and_an_agent_hold_through_one_gate_and_the_record_agrees(
    db_pool: asyncpg.Pool,
) -> None:
    """Both principals are admitted, on the same conjuncts, into the same shape."""
    setup = build_postgres_deps(db_pool, now=_NOW, ids=_ids(0x10))
    human_id, agent_id = await _principals(setup, db_pool)
    policy_id = await _policy(setup, frozenset({human_id, agent_id}))
    gate = _gate(setup, policy_id)

    # The gate, asked directly. `evaluated` names the conjuncts the
    # decision consulted, so this compares what the gate DID rather than
    # only what it returned. Two Allows that consulted different things
    # would not be one gate treating two principals alike.
    async def verdicts_for(command: str) -> dict[str, Allow | Deny]:
        return {
            label: await gate.authorize(
                principal_id=pid,
                command_name=command,
                conduit_id=NIL_SENTINEL_ID,
                surface_id=SYSTEM_HTTP_SURFACE_ID,
            )
            for label, pid in (("human", human_id), ("agent", agent_id))
        }

    # Two commands, because what the gate consults varies by COMMAND and
    # the point is that it never varies by principal.
    #
    # `HoldProcedure` is a brake: `cora.shared.liveness._BRAKE` exempts it
    # from the liveness conjunct on purpose, so that a principal an
    # operator has switched off can still stop work already in progress.
    # `StartProcedure` is routine and gets both conjuncts. Asserting the
    # sets BY NAME rather than as non-empty is what makes this catch a
    # gate that quietly stopped consulting liveness.
    for command, expected in (
        ("HoldProcedure", frozenset({Conjunct.POLICY})),
        ("StartProcedure", frozenset({Conjunct.POLICY, Conjunct.LIVENESS})),
    ):
        verdicts = await verdicts_for(command)
        assert isinstance(verdicts["human"], Allow), (command, verdicts["human"])
        assert isinstance(verdicts["agent"], Allow), (command, verdicts["agent"])
        assert verdicts["human"].evaluated == verdicts["agent"].evaluated, command
        assert verdicts["human"].evaluated == expected, command

    gated = build_postgres_deps(
        db_pool, now=_NOW, ids=_ids(0x11), authz=gate, event_store=setup.event_store
    )
    human_proc = UUID("01900000-0000-7000-8000-0000020e0100")
    agent_proc = UUID("01900000-0000-7000-8000-0000020e0200")
    await _seed_defined_procedure(gated, human_proc, UUID("01900000-0000-7000-8000-0000020e0101"))
    await _seed_defined_procedure(gated, agent_proc, UUID("01900000-0000-7000-8000-0000020e0201"))

    for proc, principal in ((human_proc, human_id), (agent_proc, agent_id)):
        await bind_start(gated)(
            StartProcedure(procedure_id=proc),
            principal_id=principal,
            correlation_id=_CORRELATION_ID,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
        await bind_hold(gated)(
            HoldProcedure(procedure_id=proc, reason="paused pending an operator decision"),
            principal_id=principal,
            correlation_id=_CORRELATION_ID,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )

    held = await _held_envelopes(db_pool, (human_proc, agent_proc))
    assert len(held) == 2, held
    by_stream = {r["stream_id"]: r for r in held}

    # The claim, asserted as a DIFF rather than as two spot checks: strip
    # only the fields that MUST differ, and everything left has to be
    # equal. A future field written on one path and not the other fails
    # here without anyone remembering to add an assertion for it.
    #
    # Three fields are stripped and each for its own reason. `stream_id`
    # and the payload's `procedure_id` name the two different Procedures.
    # `principal_id` is the one the claim is about, and it is asserted
    # explicitly below rather than merely dropped.
    def comparable(row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row["payload"])
        payload.pop("procedure_id", None)
        return {
            **{k: v for k, v in row.items() if k not in ("stream_id", "principal_id", "payload")},
            "payload": payload,
        }

    human_row, agent_row = comparable(by_stream[human_proc]), comparable(by_stream[agent_proc])
    assert human_row == agent_row
    # The comparison is only worth something if there was something to
    # compare: an empty dict on both sides would satisfy it silently.
    assert human_row["payload"], human_row
    assert human_row["metadata"], human_row
    assert by_stream[human_proc]["principal_id"] == human_id
    assert by_stream[agent_proc]["principal_id"] == agent_id
    assert human_id != agent_id


@pytest.mark.integration
async def test_the_gate_refuses_by_identity_not_by_kind(
    db_pool: asyncpg.Pool,
) -> None:
    """Each principal can be refused alone, and neither is refused for what it is.

    The negative half, and the one that carries the claim. Two Allows only
    show a gate saying yes; these show the axis it actually decides on. The
    agent is admitted by one Policy and refused by another that differs
    ONLY in whether its id is listed, and the human is refused the same way
    by the same vocabulary.
    """
    setup = build_postgres_deps(db_pool, now=_NOW, ids=_ids(0x20))
    human_id, agent_id = await _principals(setup, db_pool)

    human_only = _gate(setup, await _policy(setup, frozenset({human_id})))
    agent_only = _gate(setup, await _policy(setup, frozenset({agent_id})))

    async def verdict(gate: TrustAuthorize, principal_id: UUID) -> Allow | Deny:
        return await gate.authorize(
            principal_id=principal_id,
            command_name="HoldProcedure",
            conduit_id=NIL_SENTINEL_ID,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )

    assert isinstance(await verdict(human_only, human_id), Allow)
    assert isinstance(await verdict(human_only, agent_id), Deny)
    assert isinstance(await verdict(agent_only, agent_id), Allow)
    assert isinstance(await verdict(agent_only, human_id), Deny)

    # Same denial vocabulary in both directions. The two reasons are not
    # equal strings and should not be: each names the principal it refused
    # and the policy that refused it, which is the useful part. What has to
    # match is the SENTENCE, so normalize the identities out and compare
    # what is left. An earlier version of this asserted raw equality and
    # failed for the right reason.
    agent_denied = await verdict(human_only, agent_id)
    human_denied = await verdict(agent_only, human_id)
    assert isinstance(agent_denied, Deny)
    assert isinstance(human_denied, Deny)

    def shape(reason: str) -> str:
        for value in (str(human_id), str(agent_id)):
            reason = reason.replace(value, "<principal>")
        return _UUID_RE.sub("<policy>", reason)

    assert shape(agent_denied.reason) == shape(human_denied.reason)
    assert "<principal>" in shape(agent_denied.reason)
    assert agent_denied.evaluated == human_denied.evaluated

    # And the refusal reaches a command handler as one error type, not two.
    gated = build_postgres_deps(
        db_pool, now=_NOW, ids=_ids(0x21), authz=human_only, event_store=setup.event_store
    )
    proc = UUID("01900000-0000-7000-8000-0000020e0300")
    await _seed_defined_procedure(gated, proc, UUID("01900000-0000-7000-8000-0000020e0301"))
    await bind_start(gated)(
        StartProcedure(procedure_id=proc),
        principal_id=human_id,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    with pytest.raises(UnauthorizedError):
        await bind_hold(gated)(
            HoldProcedure(procedure_id=proc, reason="the agent tries to pause it"),
            principal_id=agent_id,
            correlation_id=_CORRELATION_ID,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
