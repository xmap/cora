"""Evolver: replay events to reconstruct Agent state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AgentEvent` without a matching match arm here.

Status mapping per event type:

  - `AgentDefined`       -> DEFINED    (genesis)
  - `AgentVersioned`     -> VERSIONED  (single-source: Defined only)
  - `AgentDeprecated`    -> DEPRECATED (source: Defined | Versioned |
                                        Suspended)
  - `AgentSuspended`     -> SUSPENDED  (single-source: Versioned only)
  - `AgentResumed`       -> VERSIONED  (single-source: Suspended only)
  - `AgentToolGranted`   -> status unchanged (additive set mutation)
  - `AgentToolRevoked`   -> status unchanged (subtractive set mutation)
  - `AgentBudgetUpdated` -> status unchanged (budget field replace)
  - `AgentTargetPlanUpdated` -> status unchanged (target_plan_id field replace)
  - `AgentDefinitionRestated` -> status unchanged (name / brain field replace,
                                None meaning unchanged rather than cleared)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.

Every arm explicitly carries forward EVERY field of the prior Agent
to guard against the silent-wipe bug class (for example,
`DecisionLogbookOpened` / `Closed` arms once silently wiped
`Decision.ratings`).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.agent.aggregates.agent.events import (
    AgentBudgetUpdated,
    AgentDefined,
    AgentDefinitionRestated,
    AgentDeprecated,
    AgentEvent,
    AgentResumed,
    AgentSuspended,
    AgentTargetPlanUpdated,
    AgentToolGranted,
    AgentToolRevoked,
    AgentVersioned,
)
from cora.agent.aggregates.agent.state import (
    Agent,
    AgentBudget,
    AgentCanonicalUri,
    AgentCapability,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentStatus,
    AgentSuspensionReason,
    AgentVersion,
    BrainRef,
    ModelRef,
    ToolName,
    brain_from_legacy_model_ref,
)
from cora.infrastructure.evolver import require_state
from cora.shared.deprecation import DeprecationReason


def _effective_brain(brain: BrainRef | None, model_ref: ModelRef | None) -> BrainRef:
    """The brain an `AgentDefined` names, whichever era wrote it.

    A stream written before `brain` existed named its brain the only way it
    could, in `model_ref`. Eighteen seeded agents were deterministic and
    carried a sentinel there; folding those to a LanguageModel brain would
    claim they think with a model that does not exist, so
    `brain_from_legacy_model_ref` reads the sentinel as the Rule it always
    was.

    An event carrying neither is not an era, it is corruption: no writer has
    ever been able to produce one, since `brain` became writable only once
    `model_ref` was already required. Raising keeps that true rather than
    inventing a brain to fold with.
    """
    if brain is not None:
        return brain
    if model_ref is not None:
        return brain_from_legacy_model_ref(model_ref)
    raise ValueError("Malformed AgentDefined: carries neither brain nor model_ref")


def evolve(state: Agent | None, event: AgentEvent) -> Agent:
    """Apply one event to the current state."""
    match event:
        case AgentDefined(
            agent_id=agent_id,
            kind=kind,
            name=name,
            version=version,
            model_ref=model_ref,
            description=description,
            canonical_uri=canonical_uri,
            prompt_template_id=prompt_template_id,
            capabilities=capabilities,
            occurred_at=_,
            tools=tools,
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
            brain=brain,
        ):
            _ = state  # AgentDefined is the genesis event; prior state ignored
            # Path C: `defined_at` no longer on state — folded into
            # `proj_agent_summary.created_at` by AgentSummaryProjection.
            return Agent(
                id=agent_id,
                kind=AgentKind(kind),
                name=AgentName(name),
                version=AgentVersion(version),
                model_ref=model_ref,
                brain=_effective_brain(brain, model_ref),
                description=AgentDescription(description) if description is not None else None,
                canonical_uri=(
                    AgentCanonicalUri(canonical_uri) if canonical_uri is not None else None
                ),
                prompt_template_id=prompt_template_id,
                capabilities=frozenset(AgentCapability(c) for c in capabilities),
                status=AgentStatus.DEFINED,
                tools=frozenset(ToolName(t) for t in tools),
                budget=_decode_budget(monthly_usd_cap, daily_token_cap),
            )
        case AgentVersioned(occurred_at=_):
            prior = require_state(state, "AgentVersioned")
            # Path C: `versioned_at` no longer on state — folded into
            # `proj_agent_summary.versioned_at` by AgentSummaryProjection.
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.VERSIONED,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentDeprecated(reason=reason, occurred_at=_):
            prior = require_state(state, "AgentDeprecated")
            # Path C: `deprecated_at` no longer on state — folded into
            # `proj_agent_summary.deprecated_at` by AgentSummaryProjection.
            # `deprecation_reason` STAYS on state (decider-relevant for any
            # future "cannot un-deprecate without rationale" rules).
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.DEPRECATED,
                deprecation_reason=DeprecationReason(reason),
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentSuspended(reason=reason, suspended_by=suspended_by, occurred_at=occurred_at):
            prior = require_state(state, "AgentSuspended")
            # `suspended_at` + `suspension_reason` STAY on state:
            # suspension_reason is invariant-bearing (decider-relevant),
            # so its paired timestamp does too. `suspended_by` is the
            # fold-symmetry attribution half paired with `suspended_at`
            # per [[project_fold_symmetry_design]].
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.SUSPENDED,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=occurred_at,
                resumed_at=prior.resumed_at,
                suspension_reason=AgentSuspensionReason(reason),
                suspended_by=suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentResumed(resumed_by=resumed_by, occurred_at=occurred_at):
            prior = require_state(state, "AgentResumed")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.VERSIONED,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                # `suspended_at` is preserved as historical audit trail
                # (the agent WAS suspended at that time); `resumed_at`
                # marks the return-to-Versioned moment. `resumed_by` is
                # the fold-symmetry attribution half paired with
                # `resumed_at` per [[project_fold_symmetry_design]].
                suspended_at=prior.suspended_at,
                resumed_at=occurred_at,
                # `suspension_reason` is preserved as historical context
                # for the same audit-trail reason. A future re-suspension
                # overwrites it with the fresh reason.
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentToolGranted(tool_name=tool_name, occurred_at=_):
            prior = require_state(state, "AgentToolGranted")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools | {ToolName(tool_name)},
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentToolRevoked(tool_name=tool_name, occurred_at=_):
            prior = require_state(state, "AgentToolRevoked")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools - {ToolName(tool_name)},
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentBudgetUpdated(
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
            occurred_at=_,
        ):
            prior = require_state(state, "AgentBudgetUpdated")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=_decode_budget(monthly_usd_cap, daily_token_cap),
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentDefinitionRestated(name=restated_name, brain=restated_brain, occurred_at=_):
            prior = require_state(state, "AgentDefinitionRestated")
            # None means UNCHANGED, not cleared: neither a name nor a brain
            # has a meaningful empty value, so there is nothing a clear could
            # mean. The decider refuses an event that restates neither.
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=AgentName(restated_name) if restated_name is not None else prior.name,
                version=prior.version,
                # The legacy slot is left exactly as the genesis wrote it. This
                # event is how an Agent stops DEPENDING on it, not a rewrite of
                # what that Agent originally said.
                model_ref=prior.model_ref,
                brain=restated_brain if restated_brain is not None else prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=prior.target_plan_id,
            )
        case AgentTargetPlanUpdated(target_plan_id=target_plan_id, occurred_at=_):
            prior = require_state(state, "AgentTargetPlanUpdated")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                brain=prior.brain,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
                suspended_by=prior.suspended_by,
                resumed_by=prior.resumed_by,
                target_plan_id=target_plan_id,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _decode_budget(
    monthly_usd_cap: float | None,
    daily_token_cap: int | None,
) -> AgentBudget | None:
    """Build `AgentBudget` from two nullable scalars or return None.

    Both None -> None (cleared budget). At least one non-None ->
    `AgentBudget(monthly_usd_cap, daily_token_cap)`. The VO's
    `__post_init__` validates invariants (no-negatives); a malformed
    payload here would raise `InvalidAgentBudgetError` at replay,
    failing loud rather than silently coercing.
    """
    if monthly_usd_cap is None and daily_token_cap is None:
        return None
    return AgentBudget(monthly_usd_cap=monthly_usd_cap, daily_token_cap=daily_token_cap)


def fold(events: Sequence[AgentEvent]) -> Agent | None:
    """Replay a stream of events from the empty initial state."""
    state: Agent | None = None
    for event in events:
        state = evolve(state, event)
    return state
