"""Agent BC prompt registry (Python module).

Per [[project-agent-bc-research]] the event-sourced
`PromptTemplate` aggregate is deferred to rule-of-three trigger
("second prompt revision ships"); pre-trigger the prompts live as
Python module constants keyed by `prompt_template_id` (UUID).

Each prompt module exposes a `build_chat_request(...)` builder that
returns an `LLMChatRequest` ready for `LLM.chat()`. The
builders are pure (no I/O), so subscribers can construct requests
in-memory and the LLM-cache layering stays a single design choice
per agent.

A SECOND entry covers the `CautionDrafter` agent. The registry
now has two entries; the PromptTemplate-aggregate trigger is
"3rd prompt-revision event ships" per
[[project-caution-drafter-design]] Watch item #7.
"""

from uuid import UUID

from cora.agent.prompts.caution_drafter import (
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
    CandidateTarget,
    CautionDrafterPayload,
    ExistingCaution,
    build_caution_drafter_chat_request,
)
from cora.agent.prompts.run_debrief import (
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
    RunDebriefPayload,
    build_run_debrief_chat_request,
)

# Resolve a prompt_template_id to a free-form one-liner description.
# Maps the registry slot to the implementation; future PromptTemplate
# aggregate replaces this dict with a projection.
KNOWN_PROMPT_TEMPLATES: dict[UUID, str] = {
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID: "RunDebrief v1: terminal-Run AAR narrative + advisory choice",
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID: (
        "CautionDrafter v1: terminal-Run Caution proposal with 5-choice verdict; "
        "payload now also carries the terminal snapshot's frame-tally capture_progress"
    ),
}


__all__ = [
    "CAUTION_DRAFTER_PROMPT_TEMPLATE_ID",
    "KNOWN_PROMPT_TEMPLATES",
    "RUN_DEBRIEF_PROMPT_TEMPLATE_ID",
    "CandidateTarget",
    "CautionDrafterPayload",
    "ExistingCaution",
    "RunDebriefPayload",
    "build_caution_drafter_chat_request",
    "build_run_debrief_chat_request",
]
