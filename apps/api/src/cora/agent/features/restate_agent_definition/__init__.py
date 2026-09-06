"""Vertical slice for the `RestateAgentDefinition` command.

Restates an existing Agent's name and/or brain by APPENDING a correction to
its own stream. Events are INSERT-only, so a stream written before `brain`
existed cannot be rewritten to carry one; this is the forward-only way to say
what such an Agent thinks with.

Eighteen seeded agents named their brain in a sentinel `model_ref` because
that was the only slot the schema then had. Restating them is what lets
`brain_from_legacy_model_ref` and `Agent.model_ref` be removed rather than
kept forever as a compatibility layer.

An omitted field means UNCHANGED, not cleared: neither a name nor a brain has
a meaningful empty value. At least one must be supplied, so a restatement
that says nothing is refused rather than emitting an empty governance write.

Idempotent on the SUPPLIED fields: if every field named already holds the
value asked for, no event is emitted.

Source set is `{Defined, Versioned, Suspended}`; Deprecated is the only
blocking state, mirroring update_agent_budget and update_agent_target_plan.

`agent_id` is unchanged by design, so historical Decisions attributed to this
agent stay attributed to it.
"""

from cora.agent.features.restate_agent_definition import tool
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.decider import decide
from cora.agent.features.restate_agent_definition.handler import Handler, bind
from cora.agent.features.restate_agent_definition.route import router

__all__ = [
    "Handler",
    "RestateAgentDefinition",
    "bind",
    "decide",
    "router",
    "tool",
]
