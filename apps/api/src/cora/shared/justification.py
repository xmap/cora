"""BC-agnostic obligation-gate primitive: a justification required at admission.

The obligation gate answers "has this principal justified this action?" for a
declared class of commands. It is the deontic dual of authorization: where the
Authorize port answers "may you?", this answers "have you accounted for
yourself?", and it fails closed. This module is the shared, BC-agnostic core:
the bound, the validation, the declared-class membership check, and the decider
helper any command's decider can call.

Where this sits
---------------
This is a decider primitive, not a value object with its own aggregate. It
mirrors the way operator `reason` text is a bare validated string checked in the
decider (`cora.shared.text_bounds` + `validate_bounded_text`, the "bare-string
validation embedded in deciders" bucket documented in `cora.shared.bounded_text`)
rather than a per-aggregate VO. A justification is the same shape as a reason:
free text, bounded, trimmed, validated at the decider and at the API boundary.

Kind-blindness (obligation-gate invariant)
------------------------------------------
`require_justification` reads the command name and the supplied justification
text. It never reads actor kind: an autonomous agent must supply a justification
for a declared-class command exactly as a human operator must. There is no
actor-kind argument in this module's surface, so a caller cannot branch on kind
even by mistake.

Declaration-only at this layer
------------------------------
`COMMANDS_REQUIRING_JUSTIFICATION` is the declared class: the set of command
names for which a justification is a precondition of admission. A command opts in
by adding its name to the set AND calling `require_justification` at the top of
its decider; this module only supplies the mechanism. v1 declares `AbortRun`
(aborting a running experiment). Commands not in the set are unaffected: an empty
or non-membership case leaves the gate inert for them.

Not persisted at this layer (v1 deferral)
-----------------------------------------
`require_justification` VALIDATES the justification and returns the trimmed text,
but v1 does NOT persist it: the gated command's event (e.g. RunAborted) does not
carry the justification, so it is an admission precondition only, not part of the
log. This is a deliberate scope cut (the `JustificationSupplied` event / the EG5
"who justified what" replay story is the deferred richer half). A command that
wants the justification on its event captures the returned value; abort_run does
not, by design.
"""

JUSTIFICATION_MAX_LENGTH = 500
"""Max length of an admission justification, after trim.

Same envelope as `REASON_MAX_LENGTH`: a justification is operator/agent free
text of the same weight as a `reason`. Kept as its own constant (not an alias)
because the two answer different questions, a reason explains a completed
state change after the fact, a justification is a precondition checked before
admission, and either bound may be retuned without moving the other.
"""


COMMANDS_REQUIRING_JUSTIFICATION: frozenset[str] = frozenset({"AbortRun"})
"""The declared class: command names that require a justification at admission.

A command opts into the obligation gate by (1) adding its command name here and
(2) calling `require_justification` at the top of its decider. Kept as a frozenset
of canonical command-name strings, mirroring how other cross-cutting command-name
sets are declared, so membership is a pure fold with no per-aggregate coupling.

v1 membership: `AbortRun` (aborting a running experiment destroys in-progress
data, the archetypal "account for yourself before a consequential act"). A
justification is the admission precondition; the abort's post-hoc `reason` is a
separate field on the RunAborted event.
"""


class JustificationRequiredError(Exception):
    """A declared-class command was issued without a valid justification.

    Raised by `require_justification` when a command whose name is in
    `COMMANDS_REQUIRING_JUSTIFICATION` carries an absent, blank, or over-length
    justification. Fail-closed: the action is refused, not accompanied by a
    deferred duty. Carries the command name so the API boundary can map it to a
    422 (missing/invalid required input) and quote which command was refused.
    """

    def __init__(self, command_name: str) -> None:
        self.command_name = command_name
        super().__init__(
            f"command {command_name!r} requires a justification: "
            f"supply non-empty text of at most {JUSTIFICATION_MAX_LENGTH} chars"
        )


def require_justification(command_name: str, justification: str | None) -> str | None:
    """Obligation gate: enforce a justification for a declared-class command.

    Call at the top of a command's decider. Behavior:

      - If `command_name` is NOT in `COMMANDS_REQUIRING_JUSTIFICATION`, the gate
        does not apply: return the justification unchanged (trimmed if present,
        else None). A non-declared command may still carry an optional
        justification, but it is not required.
      - If `command_name` IS in the declared class, a justification is a
        precondition: raise `JustificationRequiredError` when it is None,
        blank-after-trim, or over-length; otherwise return the trimmed text.

    Reads only the command name and the text. Never reads actor kind: a human
    and an agent are held to the identical precondition (the obligation-gate
    kind-blindness invariant).
    """
    required = command_name in COMMANDS_REQUIRING_JUSTIFICATION

    if justification is None:
        if required:
            raise JustificationRequiredError(command_name)
        return None

    trimmed = justification.strip()

    if not required:
        return trimmed or None

    if not trimmed or len(trimmed) > JUSTIFICATION_MAX_LENGTH:
        raise JustificationRequiredError(command_name)
    return trimmed


__all__ = [
    "COMMANDS_REQUIRING_JUSTIFICATION",
    "JUSTIFICATION_MAX_LENGTH",
    "JustificationRequiredError",
    "require_justification",
]
