"""Why something stopped being recommended.

Kept in `cora.shared` (neutral) because the eleven commands that carry it
span four BCs (Agent, Equipment, Recipe, Safety) and all answer the same
question with the same closed vocabulary. Ten are the versionable
templates; the eleventh is `LanguageModel`, a catalog entry the facility
withdraws approval for without ever being able to version it. Mirrors how
bounded-text limits live in `cora.shared.text_bounds` and the consequence
gate in `cora.shared.consequence`.

## Why closed, not operator free text

`<X>Deprecated` is the one terminal whose reason changes how a reader must
treat DATA THAT ALREADY EXISTS. A Method deprecated because a better one
landed leaves every prior Run standing; a Method deprecated because it was
subtly wrong makes every prior Run suspect. That distinction is a single bit,
it is the bit a scientist actually asks for months later, and free text
cannot be queried for it: "show me every Run whose Method was later found
defective" is a question a prose field can never answer.

Free text also decays. A required prose field gets "old" / "n/a" /
"deprecated" by the third use, which leaves a column that looks like signal
and is not. The closed set costs one token at the call site and cannot rot.

Same reasoning, same shape as `CautionRetireReason` (Caution BC), whose
docstring records the identical rejection: "Free-form `reason: str`
rejected: operators already pick from a small mental list."

## The three values

The axis is WHAT HAPPENED to the thing. Each value also states what that
means for data already produced under it, because that is what a reader
needs, but the consequence is the payload of the answer rather than the
question the set partitions on:

  - `Superseded`: a newer version of the same thing replaces it. Prior use
    stands. The routine case and the expected default.
  - `Defective`: it was wrong. Prior use is suspect and may need review.
    The value the whole enum exists to make findable.
  - `Obsolete`: what it targeted no longer exists (the device class was
    retired, the facility stopped offering the technique). Prior use stands;
    there is simply nothing left to bind to.

`Superseded` and `Obsolete` agree on the consequence and differ on the act,
which is exactly why the axis is the act. An earlier draft of this docstring
claimed the set partitioned on consequence and then listed two members with
the same one; the 2026-08-01 gate review caught the contradiction. If the
partition really were consequence, this would be a two-value enum and a
retired device class would have to be reported as `Superseded`, which is a
lie the operator would have to tell.

Narrative detail beyond this belongs on a Caution or a Decision, both of
which are built to carry prose and neither of which is load-bearing for
replay. Extending this enum needs a new ACT that a reader would treat
differently, stated together with its consequence; a new shade of narrative
on an existing act is not a new value.
"""

from enum import StrEnum


class DeprecationReason(StrEnum):
    """Closed reason for deprecating a versionable template."""

    SUPERSEDED = "Superseded"
    DEFECTIVE = "Defective"
    OBSOLETE = "Obsolete"


__all__ = ["DeprecationReason"]
