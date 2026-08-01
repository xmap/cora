"""Sibling Agent tool-grant / revoke / deprecation at APS 2-BM.

cluster: Seed
archetype: fsm
bc_primary: Agent
bc_touches: Agent

Scenario test for the Agent BC's config-time pathway: defining a
fresh sibling Agent (a `DatasetIntegrityAuditor`, a hypothetical
second AI agent that would audit raw Datasets post-acquisition),
promoting it to Versioned, granting MCP tools onto its allowlist,
revoking one when it misbehaves, and finally deprecating the whole
Agent when a successor lands. Stays within the Agent BC; no Run /
Decision side-effects.

Phase agent operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_agent_lifecycle_grants_design]] for the
design lock on `tools: frozenset[ToolName]` and the
`{Defined, Versioned, Suspended}` source set for grant / revoke /
budget revisions.

## Why this scenario exists

The sibling scenario `test_2bm_agent_cost_overrun_pause.py`
exercises the in-flight FSM cycle (Versioned <-> Suspended) on the
seeded RunDebriefer agent. This scenario covers the orthogonal axis:
the config-time slices (`define_agent`, `version_agent`,
`grant_tool_to_agent`, `revoke_tool_from_agent`, `deprecate_agent`)
on a fresh non-singleton Agent. Together the two scenarios cover
all 7 FSM-extension slices.

This scenario also exercises:

  - **`define_agent` cross-BC atomic write** (not the seeded
    short-circuit path): the `define_agent` handler writes
    `AgentDefined` + `ActorRegistered` in a single `append_streams`
    call, mirroring the `register_actor` <-> Agent.id shared
    convention. The seed path bypasses this for the singleton
    RunDebriefer; this scenario exercises the public-API path.
  - **`tools: frozenset[ToolName]` mutation cardinality**: grant
    is idempotent (re-granting an existing tool is a no-op);
    revoke is idempotent (revoking an absent tool is a no-op).
  - **`deprecate_agent` from `Versioned`** (the most common
    deprecation source state): widened from the
    original Versioned-only source set to `{Defined, Versioned,
    Suspended}`.

## Domain shape (operator narrative)

  1. 2-BM operations adds a second AI agent to the deployment: a
     `DatasetIntegrityAuditor` that will audit raw projection
     Datasets post-Run for integrity issues (file size, checksum,
     basic encoding sanity). The Auditor lives alongside the
     RunDebriefer agent; both are independent.
  2. Operator defines the Auditor via `define_agent` (kind =
     `DatasetIntegrityAuditor`, name + version + model_ref
     supplied). The slice atomically registers a new Actor
     (kind=agent) with the same id.
  3. Operator promotes the Auditor `Defined -> Versioned` via
     `version_agent`, signalling it is ready for invocation.
  4. Operator grants two MCP tools the Auditor needs:
     `validate_checksum` and `compare_size_to_expected`.
  5. Operator observes `validate_checksum` is producing false-
     positives on small Datasets (single-tile mosaic acquisitions
     specifically); revokes it via `revoke_tool_from_agent`.
     `compare_size_to_expected` stays in the allowlist.
  6. Weeks later, a successor agent (different kind, different
     identity) is ready. The operator deprecates the original
     Auditor via `deprecate_agent` with a reason citing the
     successor; the agent transitions to the terminal `Deprecated`
     state. Future Decisions authored by this Actor are not
     prevented at the aggregate level (per the design lock,
     revocation enforcement is the subscriber's job per
     [[project_run_debrief_design]] security gate-review).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. Tool-allowlist
mutation + agent-lifecycle terminal are config-time concerns
distinct from the in-flight pause cycle exercised by
`test_2bm_agent_cost_overrun_pause.py`. Bundling would conflate
"operator authors allowlist edits" with "operator pauses a
running agent over cost" — different audit trails, different
motivating use cases, different downstream consumers.

## What this scenario surfaces (gap-finding intent)

  - **No projection over `Agent.tools` today.** A future MCP
    invocation gateway might need a fast lookup ("does Agent X
    have tool Y in its allowlist?") but no scenario-tier consumer
    exists yet. Watch item for the first MCP invocation gateway
    that lands.
  - **Deprecation is terminal but does NOT cascade.** Existing
    `DecisionRegistered` events authored by this Actor are not
    retroactively annotated. The agent's id stays valid as an
    Actor.id for the operator-revocation gate (Decision authors
    are checked against the Actor's Deactivated status); the
    Agent.id's Deprecated status is independent. See
    [[project_run_debrief_design]] security gate-review.
  - **`define_agent` model_ref is required at definition time.**
    Per [[project_agent_bc_design]], the model identity must be
    known the moment the Agent exists so the LLM has an
    identity immediately. Changing model_ref later requires a
    new `define_agent` call with a new id (the rainbow-deploy
    pattern). This scenario does not exercise that re-definition
    flow (only one Auditor agent is registered).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.aggregates.agent import (
    AgentStatus,
    ModelRef,
    ToolName,
    load_agent,
)
from cora.agent.features.define_agent import DefineAgent
from cora.agent.features.define_agent import bind as bind_define_agent
from cora.agent.features.deprecate_agent import DeprecateAgent
from cora.agent.features.deprecate_agent import bind as bind_deprecate_agent
from cora.agent.features.grant_tool_to_agent import GrantToolToAgent
from cora.agent.features.grant_tool_to_agent import bind as bind_grant_tool
from cora.agent.features.revoke_tool_from_agent import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent import bind as bind_revoke_tool
from cora.agent.features.version_agent import VersionAgent
from cora.agent.features.version_agent import bind as bind_version_agent
from cora.shared.deprecation import DeprecationReason
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 5, 17, 23, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000431bb")

# Scenario tag: 431 (agent ops / tool lifecycle + deprecation).
_AUDITOR_AGENT_ID = UUID("01900000-0000-7000-8000-000000043101")


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    Standalone Agent BC scenario: no facility / beamtime / Run
    setup. `define_agent` is the only cross-BC slice (Agent +
    Actor); subsequent slices write Agent-only.
    """
    e = uuid4
    return [
        # define_agent: agent_id (server-allocated, shared with Actor.id)
        # + 2 event ids (one per stream: Actor + Agent)
        _AUDITOR_AGENT_ID,
        e(),  # ActorRegistered
        e(),  # AgentDefined
        # version_agent: event_id
        e(),
        # grant_tool_to_agent x 2: event_id each
        e(),
        e(),
        # revoke_tool_from_agent: event_id
        e(),
        # deprecate_agent: event_id
        e(),
    ]


@pytest.mark.integration
async def test_agent_tool_lifecycle_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Define a fresh DatasetIntegrityAuditor Agent (cross-BC
    Agent + Actor co-write), promote to Versioned, grant two
    tools, revoke one, deprecate. Assert Agent stream carries
    the full define -> version -> grant x2 -> revoke -> deprecate
    cycle and the tools frozenset reflects each mutation."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Define fresh sibling Agent (cross-BC atomic write) -----
    # define_agent writes ActorRegistered (Access BC) + AgentDefined
    # (Agent BC) in one append_streams call; the Agent.id == Actor.id.

    new_agent_id = await bind_define_agent(deps, profile_store=make_pg_profile_store(db_pool))(
        DefineAgent(
            kind="DatasetIntegrityAuditor",
            name="DatasetIntegrityAuditor",
            version="v1",
            model_ref=ModelRef(
                provider="anthropic",
                model="claude-haiku-4-5",
                snapshot_pin="20251001",
            ),
            description=(
                "Audits raw projection Datasets post-Run for integrity issues "
                "(file size sanity, checksum verification, basic encoding "
                "checks). Sibling to the RunDebriefer agent."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_agent_id == _AUDITOR_AGENT_ID

    defined = await load_agent(deps.event_store, _AUDITOR_AGENT_ID)
    assert defined is not None
    assert defined.status is AgentStatus.DEFINED
    assert defined.kind.value == "DatasetIntegrityAuditor"
    assert defined.tools == frozenset()

    # ----- Promote Defined -> Versioned -----

    await bind_version_agent(deps)(
        VersionAgent(agent_id=_AUDITOR_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    versioned = await load_agent(deps.event_store, _AUDITOR_AGENT_ID)
    assert versioned is not None
    assert versioned.status is AgentStatus.VERSIONED

    # ----- Grant two MCP tools the Auditor needs -----

    await bind_grant_tool(deps)(
        GrantToolToAgent(
            agent_id=_AUDITOR_AGENT_ID,
            tool_name="validate_checksum",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_grant_tool(deps)(
        GrantToolToAgent(
            agent_id=_AUDITOR_AGENT_ID,
            tool_name="compare_size_to_expected",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after_grants = await load_agent(deps.event_store, _AUDITOR_AGENT_ID)
    assert after_grants is not None
    assert after_grants.tools == frozenset(
        {ToolName("validate_checksum"), ToolName("compare_size_to_expected")}
    )

    # ----- Revoke one tool (validate_checksum produces false positives) -----

    await bind_revoke_tool(deps)(
        RevokeToolFromAgent(
            reason="tool no longer needed",
            agent_id=_AUDITOR_AGENT_ID,
            tool_name="validate_checksum",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after_revoke = await load_agent(deps.event_store, _AUDITOR_AGENT_ID)
    assert after_revoke is not None
    assert after_revoke.tools == frozenset({ToolName("compare_size_to_expected")})
    # FSM unchanged by tool mutation.
    assert after_revoke.status is AgentStatus.VERSIONED

    # ----- Deprecate the Auditor (successor agent landing) -----

    await bind_deprecate_agent(deps)(
        DeprecateAgent(
            agent_id=_AUDITOR_AGENT_ID,
            reason=DeprecationReason.SUPERSEDED,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deprecated = await load_agent(deps.event_store, _AUDITOR_AGENT_ID)
    assert deprecated is not None
    assert deprecated.status is AgentStatus.DEPRECATED
    # Tool allowlist survives deprecation (terminal state is a
    # status change, not a configuration wipe).
    assert deprecated.tools == frozenset({ToolName("compare_size_to_expected")})

    # ----- Assert: Agent stream carries the full lifecycle -----

    agent_events, _agent_version = await deps.event_store.load("Agent", _AUDITOR_AGENT_ID)
    agent_event_types = [e.event_type for e in agent_events]
    # define + version + grant x2 + revoke + deprecate = 6 events.
    assert agent_event_types == [
        "AgentDefined",
        "AgentVersioned",
        "AgentToolGranted",
        "AgentToolGranted",
        "AgentToolRevoked",
        "AgentDeprecated",
    ]

    # ----- Assert: Actor stream carries the cross-BC co-write -----
    # define_agent's atomic Agent+Actor write means the Actor exists at
    # the same id as soon as the Agent does.

    actor_events, _actor_version = await deps.event_store.load("Actor", _AUDITOR_AGENT_ID)
    actor_event_types = [e.event_type for e in actor_events]
    assert actor_event_types == ["ActorRegisteredV2"]
    actor_payload = actor_events[0].payload
    assert actor_payload["kind"] == "agent"

    # ----- Assert: deprecate reason is the closed vocabulary, not prose -----

    deprecate_event = next(e for e in agent_events if e.event_type == "AgentDeprecated")
    assert deprecate_event.payload["reason"] == "Superseded"

    # ----- Assert: grant event payload carries the tool name -----

    grant_events = [e for e in agent_events if e.event_type == "AgentToolGranted"]
    granted_tool_names = {e.payload["tool_name"] for e in grant_events}
    assert granted_tool_names == {"validate_checksum", "compare_size_to_expected"}

    # ----- Assert: revoke event payload carries the revoked tool name -----

    revoke_event = next(e for e in agent_events if e.event_type == "AgentToolRevoked")
    assert revoke_event.payload["tool_name"] == "validate_checksum"
