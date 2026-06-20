"""Agent bounded context.

One aggregate, `Agent`. Genesis plus a lifecycle FSM
(`Defined -> Versioned -> Suspended? -> Deprecated`) with tool
grants and budget envelopes.

Production `AnthropicLLM` ships at
`cora.agent.adapters.AnthropicLLM` and is wired into the
Kernel via `build_llm` (composition-root binding lives in
`cora.api.main`). Subscribers (RunDebriefer, CautionDrafter) consume
it to write Decisions and Caution proposals.

`Agent.id` is SHARED with Access BC's `Actor.id` for the same agent.
`define_agent` writes both `ActorRegistered(kind="agent")` (Access
stream) and `AgentDefined` (Agent stream) atomically via
`EventStore.append_streams`. Mirrors the cross-aggregate atomic-write
pattern used by Safety BC's `amend_clearance` and Caution BC's
`supersede_caution`.

Public surface re-exported here:
  - `AgentHandlers`            (handler bundle)
  - `register_agent_routes`    (FastAPI route + exception handler registration)
  - `register_agent_tools`     (MCP tool registration)
  - `wire_agent`               (Kernel -> AgentHandlers factory)
  - `build_llm`                (LLMFactory for `build_kernel`)
"""

from cora.agent._projections import register_agent_projections
from cora.agent._subscribers import register_agent_subscribers
from cora.agent.build_llm import build_llm
from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
    DecisionNotEmittedByCautionDrafterError,
    UnauthorizedError,
)
from cora.agent.routes import register_agent_routes
from cora.agent.seed import seed_run_debriefer_agent
from cora.agent.seed_caution_drafter import seed_caution_drafter_agent
from cora.agent.seed_caution_promoter import (
    CAUTION_PROMOTER_AGENT_ID,
    seed_caution_promoter_agent,
)
from cora.agent.seed_run_supervisor import (
    RUN_SUPERVISOR_AGENT_ID,
    seed_run_supervisor_agent,
)
from cora.agent.tools import register_agent_tools
from cora.agent.wire import AgentHandlers, wire_agent

__all__ = [
    "CAUTION_PROMOTER_AGENT_ID",
    "RUN_SUPERVISOR_AGENT_ID",
    "AgentHandlers",
    "CautionProposalMalformedError",
    "CautionProposalNotActionableError",
    "DecisionNotCautionProposalError",
    "DecisionNotEmittedByCautionDrafterError",
    "UnauthorizedError",
    "build_llm",
    "register_agent_projections",
    "register_agent_routes",
    "register_agent_subscribers",
    "register_agent_tools",
    "seed_caution_drafter_agent",
    "seed_caution_promoter_agent",
    "seed_run_debriefer_agent",
    "seed_run_supervisor_agent",
    "wire_agent",
]
