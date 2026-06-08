"""The `RegisterDecision` command, intent dataclass for this slice.

Carries the caller-controlled inputs:

  - `decided_by`: WHO made the decision (Actor.Ref). Existence-
    checked at handler-load time. Same Actor aggregate handles
    human + AI deciders; the actor's role discriminator
    (operator / scientist / agent / admin / approver / reviewer)
    distinguishes them.
  - `context`: well-known string discriminator (RecipeApproval /
    RunAbort / etc.). Open-ended per gate-review Q5.
  - `choice`: free-form string capturing what was decided
    (1-500 chars after trim).
  - `parent_id`: optional ref to a prior Decision being overridden,
    corrected, appealed, or superseded. Existence-checked at
    handler-load time.
  - `override_kind`: when `parent_id` is set, says WHY (correction
    / exception / appeal / supersession). Required-with-parent
    invariant enforced at the decider.
  - `rule`: optional rule citation per ISO 17025 Clause
    7.1.3. Free-form string but convention encourages prefixed
    identifiers like `iso17025:7.1.3:simple_acceptance`.
  - `reasoning`: optional free-form prose explaining the
    decision. Token-by-token AI reasoning traces go to a
    `reasoning` logbook on the Decision aggregate (8c), NOT
    here; this field is the human-readable summary.
  - `confidence`: optional float in [0.0, 1.0]. By convention,
    pair with `confidence_source` so consumers can audit how the
    value was computed (see DecisionConfidenceSource docstring
    for the audit-weight gradient). The BC does NOT enforce the
    pairing; either field can be set independently. Projection-
    time auditors flag bare-confidence-without-source records as
    a quality concern.
  - `confidence_source`: where the confidence came from
    (self_reported / logprob / ensemble / human).
  - `alternatives`: tuple of options considered (ORDER PRESERVED;
    AI deciders need top-k ordering). For Cedar-style
    PolicyGrant decisions, this carries the determining policy
    IDs.
  - `inputs`: optional dict carrying the values the
    rule was applied to (per ILAC-G8:09/2019: a rule
    without its inputs is unauditable).
  - `reasoning_signature`: optional opaque blob (typically
    sha256 of the full reasoning trace, or vendor-supplied
    encrypted summary) for tamper-evidence beyond row-level
    INSERT-only.

The new Decision id is server-allocated by the handler from the
IdGenerator port (matches every other create-style slice).

"Register" rather than "define": the decision was made in the
world (by a human or by an AI inference) and we are recording it.
Same convention as `register_actor`, `register_subject`,
`register_dataset`.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cora.decision.aggregates.decision import (
    DecisionConfidenceSource,
    DecisionOverrideKind,
)
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class RegisterDecision:
    """Register a new Decision with the structured-audit metadata."""

    decided_by: ActorId
    context: str
    choice: str
    parent_id: UUID | None = None
    override_kind: DecisionOverrideKind | None = None
    rule: str | None = None
    reasoning: str | None = None
    confidence: float | None = None
    confidence_source: DecisionConfidenceSource | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple[str, ...])
    inputs: dict[str, Any] | None = None
    reasoning_signature: str | None = None
