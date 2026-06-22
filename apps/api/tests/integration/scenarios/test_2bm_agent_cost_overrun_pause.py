"""Operator-paused RunDebriefer agent at APS 2-BM (cost overrun).

cluster: Seed
archetype: fsm
bc_primary: Agent
bc_touches: Agent

Scenario test for the operator-intervention pathway on an in-flight
Agent: an Agent that is running normally suddenly exceeds its
budget envelope (real-life Anthropic API spend spiking), the
operator suspends it without deprecating, tightens the budget, and
resumes when caps are re-established.

Agent operations chain.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into. See
[[project_agent_lifecycle_grants_design]] for the design lock on
the operator-pause + budget-update + resume cycle (the canonical
first-use case documented as "operator-pauses an agent without
retiring it; cost-overrun, output-spike, model-regression recovery
surface").

## Why this scenario exists

The Agent BC's FSM widened from a linear
3-state `Defined -> Versioned -> Deprecated` to a 4-state
`Defined -> Versioned <-> Suspended -> Deprecated`. The new
`Suspended` state + the bidirectional Versioned <-> Suspended
transition exist specifically for in-flight operator intervention
when an Agent's behaviour or cost goes off-rails but the operator
does NOT want to permanently retire it.

This scenario exercises that cycle end-to-end:

  - `version_agent` (the seeded RunDebriefer Agent lands in `Defined`
    per `seed_run_debriefer_agent`; the operator explicitly promotes
    it to `Versioned` so the subscriber will pick it up).
  - `update_agent_budget` (establishes the initial budget envelope
    BEFORE any cost issue surfaces; a future scenario could
    co-locate this with `define_agent` at registration time).
  - `suspend_agent` with a `reason` citing the cost overrun (the
    `reason` field is REQUIRED on suspend per the design lock; it
    lands as `AgentSuspended.reason` for the audit trail).
  - `update_agent_budget` AGAIN to tighten the caps before resume
    (PUT semantics: supplied caps ARE the post-update budget).
  - `resume_agent` (no `reason` field on resume by design —
    "act of resuming is its own signal; rationale lives in
    Decisions").

## Domain shape (operator narrative)

  1. 2-BM operator on shift observes the Anthropic API spend has
     crossed 80% of monthly cap with two weeks of beamtime
     remaining; runaway projected.
  2. Operator suspends the RunDebriefer agent (`suspend_agent`)
     citing the cost overrun. The agent's `actor_id` is now
     associated with an Actor that the subscriber's revocation
     gate (per [[project_run_debrief_design]] security gate-review)
     will treat as paused.
  3. Operator tightens the budget envelope
     (`update_agent_budget`): drops `monthly_usd_cap` to the
     remaining-budget amount and adds a per-day token cap to
     short-circuit any single-day spike.
  4. Operator resumes the agent (`resume_agent`) once the new
     budget is in place. The agent is back in `Versioned` state
     and the subscriber will pick up subsequent terminal Run
     events.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The agent-pause
narrative is separable from both (a) the agent's own runtime
behavior (covered by `test_2bm_run_debriefer.py` family) and
(b) the agent's definition / catalog registration (covered by
`test_aps_facility.py`'s install path and `seed_run_debriefer_agent`).
Bundling would conflate "agent emits a Decision" with "operator
pauses an agent" — different actor surfaces, different audit
trails, different motivating use cases.

## What this scenario surfaces (gap-finding intent)

  - **Budget caps are declaration-only.** The
    `AgentBudget` value object lands on the Agent's state via
    `AgentBudgetUpdated`, but no slice or projection reads it to
    enforce spending. Enforcement is deferred to the 8h Budget BC
    (per [[project_agent_lifecycle_grants_design]]). This scenario
    confirms the wire (the budget round-trips through the
    aggregate) without making any enforcement claim.
  - **Resume does NOT capture rationale.** Asymmetric with suspend:
    `AgentSuspended` carries a `reason` field, `AgentResumed` does
    not. If a future audit requires "why was this agent resumed?"
    it must be answered via a separate Decision aggregate
    (operator-authored, `context="AgentResume"` or similar). Watch
    item for [[project_run_debrief_design]] downstream consumers.
  - **The seeded agent enters `Defined`, not `Versioned`.** Per
    `seed.py`, `seed_run_debriefer_agent` writes only an
    `AgentDefined` event; this scenario explicitly drives the
    `Defined -> Versioned` promotion via `version_agent` before
    the suspend / resume cycle, mirroring the production
    bootstrap-then-promote pattern.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.aggregates.agent import (
    AgentStatus,
    load_agent,
)
from cora.agent.features.resume_agent import ResumeAgent
from cora.agent.features.resume_agent import bind as bind_resume_agent
from cora.agent.features.suspend_agent import SuspendAgent
from cora.agent.features.suspend_agent import bind as bind_suspend_agent
from cora.agent.features.update_agent_budget import UpdateAgentBudget
from cora.agent.features.update_agent_budget import bind as bind_update_budget
from cora.agent.features.version_agent import VersionAgent
from cora.agent.features.version_agent import bind as bind_version_agent
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, seed_run_debriefer_agent
from tests.integration._helpers import build_postgres_deps
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 5, 17, 22, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000430bb")

# Scenario tag: 430 (agent ops / cost-overrun pause). The agent ops
# family takes 43x; future operator-intervention scenarios on Agents
# (model-regression, output-spike, token-quota-reset) take 431..439.


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    The scenario does not register a facility hierarchy or beamtime
    intake: Agent BC operates standalone (no Subject/Run/Campaign
    dependencies). The seeded Agent + Actor land via
    `seed_run_debriefer_agent` which writes directly to the event
    store with its own pinned event ids (NOT consumed from this
    queue).
    """
    e = uuid4
    return [
        # version_agent: event_id
        e(),
        # update_agent_budget (initial envelope): event_id
        e(),
        # suspend_agent: event_id
        e(),
        # update_agent_budget (tightened caps): event_id
        e(),
        # resume_agent: event_id
        e(),
    ]


@pytest.mark.integration
async def test_agent_cost_overrun_pause_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed RunDebriefer Agent, promote Defined -> Versioned, set
    initial budget, suspend (with cost-overrun reason), tighten
    budget, resume. Assert FSM cycled Versioned -> Suspended ->
    Versioned and both budget updates landed on the aggregate."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Bootstrap: seed RunDebriefer Agent (lands in Defined) -----
    # Writes 2 events: ActorRegistered (Access BC) + AgentDefined
    # (Agent BC) via cross-BC atomic append_streams. Uses pinned ids
    # outside our scenario id queue.

    await seed_run_debriefer_agent(deps)

    seeded = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert seeded is not None
    assert seeded.status is AgentStatus.DEFINED

    # ----- Promote Defined -> Versioned (operator ready signal) -----

    await bind_version_agent(deps)(
        VersionAgent(agent_id=RUN_DEBRIEFER_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    versioned = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert versioned is not None
    assert versioned.status is AgentStatus.VERSIONED

    # ----- Initial budget envelope -----
    # Operator declares the initial spend ceiling. Declaration-only;
    # enforcement deferred to the Budget BC.

    await bind_update_budget(deps)(
        UpdateAgentBudget(
            agent_id=RUN_DEBRIEFER_AGENT_ID,
            monthly_usd_cap=500.0,
            daily_token_cap=2_000_000,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after_initial_budget = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert after_initial_budget is not None
    assert after_initial_budget.budget is not None
    assert after_initial_budget.budget.monthly_usd_cap == 500.0
    assert after_initial_budget.budget.daily_token_cap == 2_000_000

    # ----- Cost-overrun event: operator suspends the agent -----
    # 2-BM operator observes Anthropic API spend has crossed 80% of
    # monthly cap with two weeks of beamtime remaining; runaway
    # projected. Pause is preferable to deprecate-and-redefine since
    # the agent config is otherwise correct.

    await bind_suspend_agent(deps)(
        SuspendAgent(
            agent_id=RUN_DEBRIEFER_AGENT_ID,
            reason=(
                "Anthropic API spend crossed 80% of monthly $500 cap on day 14 "
                "of 30; two weeks of beamtime remain. Pausing to tighten caps "
                "before resuming."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    suspended = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert suspended is not None
    assert suspended.status is AgentStatus.SUSPENDED

    # ----- Tighten budget caps while paused -----
    # PUT semantics: the supplied caps ARE the post-update budget.
    # Drop monthly cap to remaining-amount + halve the daily token cap.

    await bind_update_budget(deps)(
        UpdateAgentBudget(
            agent_id=RUN_DEBRIEFER_AGENT_ID,
            monthly_usd_cap=120.0,
            daily_token_cap=1_000_000,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    after_tightened = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert after_tightened is not None
    assert after_tightened.budget is not None
    assert after_tightened.budget.monthly_usd_cap == 120.0
    assert after_tightened.budget.daily_token_cap == 1_000_000
    # Budget update is allowed in Suspended state (per design); status
    # is unchanged by the budget slice.
    assert after_tightened.status is AgentStatus.SUSPENDED

    # ----- Resume the agent (back to Versioned) -----
    # No reason field; "act of resuming is its own signal; rationale
    # lives in Decisions" per the design lock.

    await bind_resume_agent(deps)(
        ResumeAgent(agent_id=RUN_DEBRIEFER_AGENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    resumed = await load_agent(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
    assert resumed is not None
    assert resumed.status is AgentStatus.VERSIONED
    # Budget caps survive the resume transition.
    assert resumed.budget is not None
    assert resumed.budget.monthly_usd_cap == 120.0
    assert resumed.budget.daily_token_cap == 1_000_000

    # ----- Assert: Agent stream carries the full FSM cycle -----

    agent_events, _agent_version = await deps.event_store.load("Agent", RUN_DEBRIEFER_AGENT_ID)
    agent_event_types = [e.event_type for e in agent_events]
    # Seed + version + 2 budget updates + suspend + resume = 6 events.
    assert agent_event_types == [
        "AgentDefined",
        "AgentVersioned",
        "AgentBudgetUpdated",
        "AgentSuspended",
        "AgentBudgetUpdated",
        "AgentResumed",
    ]

    # ----- Assert: suspend reason captured verbatim for audit -----

    suspend_event = next(e for e in agent_events if e.event_type == "AgentSuspended")
    assert "cost" not in suspend_event.payload["reason"].lower() or (
        "80%" in suspend_event.payload["reason"] and "monthly" in suspend_event.payload["reason"]
    )

    # ----- Assert: resume event carries no reason field (by design) -----

    resume_event = next(e for e in agent_events if e.event_type == "AgentResumed")
    assert "reason" not in resume_event.payload
