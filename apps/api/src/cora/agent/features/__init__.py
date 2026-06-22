"""Vertical slices for the Agent BC.

Foundation:
  - `define_agent`    (cross-BC atomic via EventStore.append_streams;
                       writes ActorRegistered(kind="agent") + AgentDefined;
                       create-style; idempotency-wrapped)
  - `version_agent`   (Defined -> Versioned; single-stream)
  - `deprecate_agent` (Defined | Versioned -> Deprecated; single-stream)
  - `get_agent`       (read; fold-on-read)

On-demand re-invocation:
  - `regenerate_run_debrief`  (operator-triggered on-demand RunDebriefer
                               re-invocation; cross-BC writes a Decision;
                               idempotency-wrapped; Pattern C from the
                               design memo)

Lifecycle + grants + budget:
  - `suspend_agent`         (Versioned -> Suspended; non-terminal)
  - `resume_agent`          (Suspended -> Versioned)
  - `grant_tool_to_agent`   (Defined | Versioned | Suspended;
                             idempotent re-grant)
  - `revoke_tool_from_agent`(Defined | Versioned | Suspended;
                             idempotent revoke-of-non-granted)
  - `update_agent_budget`   (Defined | Versioned | Suspended;
                             PUT-semantics; idempotent no-op)

Caution-proposal promotion:
  - `promote_caution_proposal` (operator-triggered cross-BC
                                promotion of a CautionDrafter-authored
                                Decision into a real Caution via
                                Caution BC's register_caution or
                                supersede_caution slice;
                                idempotency-wrapped; Pattern C)

Also: deprecate's source set widens to include Suspended.

Reaction recovery:
  - `dismiss_event_in_reaction` (operator-triggered atomic bookmark
                                 advance + DecisionRegistered audit
                                 via append_streams(conn=); recovers
                                 a wedged Reaction bookmark without
                                 SSH access to projection_bookmarks)
"""

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

__all__ = [
    "define_agent",
    "deprecate_agent",
    "dismiss_event_in_reaction",
    "get_agent",
    "grant_tool_to_agent",
    "promote_caution_proposal",
    "regenerate_run_debrief",
    "resume_agent",
    "revoke_tool_from_agent",
    "suspend_agent",
    "update_agent_budget",
    "version_agent",
]
