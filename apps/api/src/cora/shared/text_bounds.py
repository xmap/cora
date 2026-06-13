"""Shared length bound for operator free-text reasons.

A `reason` is the free-text justification an operator or agent attaches
to a state-changing or terminal command: aborting a Run, deprecating a
Model, decommissioning an Enclosure, rejecting a Clearance, and so on.
Every such reason is capped at the same length, and this module is the
one home for that bound.

This is deliberately separate from the per-value-object `MAX_LENGTH`
constants described in `cora.shared.bounded_text`. Those bound named
value objects (`ActorName`, `MethodName`, and the rest) and stay local
to each aggregate so a value object can be retuned on its own. A reason
is not a value object: it is a bare validated string, checked in the
decider and at the API boundary, and the same bound applies across every
aggregate, so it is shared rather than per-aggregate.
"""

REASON_MAX_LENGTH = 500


__all__ = ["REASON_MAX_LENGTH"]
