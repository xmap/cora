"""BC-agnostic decision-signal vocabulary shared by the Decision aggregate
and the Operation Steering port.

`DecisionConfidenceSource` and `REASONING_MAX_LENGTH` describe how any CORA
decider reports the confidence and the free-text reasoning behind a choice:
an AI agent recording a `Decision`, or a steering brain advising the
`Conductor` through `DecidePort`. They live here, not in the Decision
aggregate, because the Operation BC's `DecidePort` reuses the same
vocabulary and tach forbids `cora.operation` from importing
`cora.decision.aggregates`. The Decision state module re-exports both names
so existing importers stay stable, the same shape as `REASON_MAX_LENGTH`
living in `cora.shared.text_bounds` rather than per-aggregate.

This is deliberately narrow: only the value types two BCs genuinely share
move here. The Decision aggregate keeps owning its `validate_reasoning` /
`validate_confidence` deciders and their `InvalidDecision*` error families
(those raise Decision-named errors a hundred callers depend on); the
Steering port validates its own `SteeringAdvice` against the shared
`REASONING_MAX_LENGTH` and raises its own `DecideAdviceMalformedError`.
"""

from enum import StrEnum

REASONING_MAX_LENGTH = 5000
"""Max length of a decider's free-text reasoning, after trim.

Single-sourced so the Decision aggregate's `validate_reasoning` and the
Operation Steering port's `SteeringAdvice` rationale bound cannot drift: a
steering advice rationale must fit the same envelope it maps onto at the
Decision aggregate, because the across-Run L3 steerer maps
`advice.rationale` -> `DecisionRegistered.reasoning`.
"""


class DecisionConfidenceSource(StrEnum):
    """How the `confidence` value was computed.

    ISO 42001 audit asks 'how was this confidence derived?'; this
    enum is the answer. Stored alongside the float so consumers can
    distinguish calibrated probabilistic estimates from
    self-reported model claims.

    Values:
      - `self_reported`: AI decider's own confidence claim, as a
        learned linguistic pattern. NOT a posterior probability.
        Lowest audit weight.
      - `logprob`: derived from token log-probabilities. Closer to
        a calibrated estimate but still model-internal.
      - `ensemble`: aggregated over multiple deciders / runs /
        models. Higher audit weight; carries the implicit promise
        of uncertainty quantification.
      - `human`: subjective human confidence rating. Audit-weight
        is operator-dependent; treat as direction-of-confidence,
        not a probability.
    """

    SELF_REPORTED = "self_reported"
    LOGPROB = "logprob"
    ENSEMBLE = "ensemble"
    HUMAN = "human"


__all__ = ["REASONING_MAX_LENGTH", "DecisionConfidenceSource"]
