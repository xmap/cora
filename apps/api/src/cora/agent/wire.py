"""Compose the Agent BC's handlers from `Kernel`.

`wire_agent(deps)` is invoked once from the FastAPI lifespan and
the returned `AgentHandlers` bundle is stored on
`app.state.agent`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `AgentHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Supply / Safety / Caution:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers

  - `define_agent`            (cross-BC atomic; create-style;
                               idempotency-wrapped)
  - `version_agent`           (transition; no idempotency wrap)
  - `deprecate_agent`         (transition; no idempotency wrap)
  - `suspend_agent`           (transition; no idempotency wrap)
  - `resume_agent`            (transition; no idempotency wrap)
  - `grant_tool_to_agent`     (transition; idempotent; no wrap)
  - `revoke_tool_from_agent`  (transition; idempotent; no wrap)
  - `update_agent_budget`     (transition; idempotent; no wrap)
  - `get_agent`               (query)
  - `regenerate_run_debrief`  (operator-triggered; idempotency-wrapped)
  - `dismiss_event_in_reaction` (operator-triggered atomic bookmark
                                 advance + Decision audit; no
                                 idempotency wrap because the slice
                                 is operator-rare and the
                                 EventAlreadyDismissedError guard
                                 catches duplicate dismissals
                                 strict-not-idempotently)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.agent.features import (
    define_agent,
    deprecate_agent,
    dismiss_event_in_reaction,
    get_agent,
    grant_tool_to_agent,
    promote_caution_proposal,
    regenerate_run_debrief,
    resume_agent,
    revoke_tool_from_agent,
    suspend_agent,
    update_agent_budget,
    version_agent,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "agent"


@dataclass(frozen=True)
class AgentHandlers:
    """The Agent BC's handler bundle, each closed over Kernel."""

    define_agent: define_agent.IdempotentHandler
    version_agent: version_agent.Handler
    deprecate_agent: deprecate_agent.Handler
    suspend_agent: suspend_agent.Handler
    resume_agent: resume_agent.Handler
    grant_tool_to_agent: grant_tool_to_agent.Handler
    revoke_tool_from_agent: revoke_tool_from_agent.Handler
    update_agent_budget: update_agent_budget.Handler
    get_agent: get_agent.Handler
    regenerate_run_debrief: regenerate_run_debrief.IdempotentHandler | None
    promote_caution_proposal: promote_caution_proposal.IdempotentHandler
    dismiss_event_in_reaction: dismiss_event_in_reaction.Handler


def wire_agent(deps: Kernel) -> AgentHandlers:
    """Build the Agent BC handlers from shared dependencies.

    `regenerate_run_debrief` requires `kernel.llm` to be set (production
    `AnthropicLLM` or test `FakeLLM`). When the LLM
    is unwired (eg. dev startup without ANTHROPIC_API_KEY), the
    handler bundle carries `regenerate_run_debrief=None`; the REST route
    + MCP tool guard on the None to return HTTP 503.

    `define_agent` reads the PII vault from `deps.profile_store`
    (the shared singleton Access BC also uses) so the in-memory
    test adapter is the SAME dict across both BCs.
    """
    regenerate_run_debrief_handler: regenerate_run_debrief.IdempotentHandler | None
    if deps.llm is None:
        regenerate_run_debrief_handler = None
    else:
        regenerate_run_debrief_handler = with_tracing(
            with_idempotency(
                regenerate_run_debrief.bind(deps),
                deps.idempotency_store,
                command_name="RegenerateRunDebrief",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegenerateRunDebrief",
            bc=_BC,
        )
    return AgentHandlers(
        define_agent=with_tracing(
            with_idempotency(
                define_agent.bind(deps, profile_store=deps.profile_store),
                deps.idempotency_store,
                command_name="DefineAgent",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineAgent",
            bc=_BC,
        ),
        version_agent=with_tracing(
            version_agent.bind(deps),
            command_name="VersionAgent",
            bc=_BC,
        ),
        deprecate_agent=with_tracing(
            deprecate_agent.bind(deps),
            command_name="DeprecateAgent",
            bc=_BC,
        ),
        suspend_agent=with_tracing(
            suspend_agent.bind(deps),
            command_name="SuspendAgent",
            bc=_BC,
        ),
        resume_agent=with_tracing(
            resume_agent.bind(deps),
            command_name="ResumeAgent",
            bc=_BC,
        ),
        grant_tool_to_agent=with_tracing(
            grant_tool_to_agent.bind(deps),
            command_name="GrantToolToAgent",
            bc=_BC,
        ),
        revoke_tool_from_agent=with_tracing(
            revoke_tool_from_agent.bind(deps),
            command_name="RevokeToolFromAgent",
            bc=_BC,
        ),
        update_agent_budget=with_tracing(
            update_agent_budget.bind(deps),
            command_name="UpdateAgentBudget",
            bc=_BC,
        ),
        get_agent=with_tracing(
            get_agent.bind(deps),
            command_name="GetAgent",
            bc=_BC,
        ),
        regenerate_run_debrief=regenerate_run_debrief_handler,
        promote_caution_proposal=with_tracing(
            with_idempotency(
                promote_caution_proposal.bind(deps),
                deps.idempotency_store,
                command_name="PromoteCautionProposal",
                # Handler returns UUID; cache as str (jsonb-friendly).
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="PromoteCautionProposal",
            bc=_BC,
        ),
        dismiss_event_in_reaction=with_tracing(
            dismiss_event_in_reaction.bind(deps),
            command_name="DismissEventInReaction",
            bc=_BC,
        ),
    )
