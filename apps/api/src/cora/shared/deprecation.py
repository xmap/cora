"""Why a versionable template stopped being recommended.

Kept in `cora.shared` (neutral) because the ten versionable templates span
five BCs (Agent, Equipment, Recipe, Safety) and all answer the same question
with the same closed vocabulary. Mirrors how bounded-text limits live in
`cora.shared.text_bounds` and the consequence gate in
`cora.shared.consequence`.

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

The set is deliberately small and partitions on the consequence for prior
data, not on the operator's narrative:

  - `Superseded`: a newer version of the same thing replaces it. Prior use
    stands. This is the routine case and the expected default.
  - `Defective`: it was wrong. Prior use is suspect and may need review.
    This is the value the whole enum exists to make findable.
  - `Obsolete`: what it targeted no longer exists (the device class was
    retired, the facility stopped offering the technique). Prior use stands;
    the template simply has nothing left to bind to.

Narrative detail beyond this belongs on a Caution or a Decision, both of
which are built to carry prose and neither of which is load-bearing for
replay. Extending this enum needs a new consequence-for-prior-data case, not
a new shade of narrative; if two candidate values would leave a reader
treating old data identically, they are one value.
"""

from enum import StrEnum


class DeprecationReason(StrEnum):
    """Closed reason for deprecating a versionable template."""

    SUPERSEDED = "Superseded"
    DEFECTIVE = "Defective"
    OBSOLETE = "Obsolete"


__all__ = ["DeprecationReason"]
