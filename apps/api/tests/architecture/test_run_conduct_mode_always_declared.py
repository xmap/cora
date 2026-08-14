"""ConductMode is a closed, never-Optional vocabulary declared at genesis.

`ConductMode` (cora.run.aggregates.run.state) reifies who drove a Run's
act: CORA's own Conductor, or an external tool CORA only observes. Two
properties make "declared, never inferred" a build-time guarantee rather
than a convention someone can forget:

  - The enum stays closed to exactly {CONDUCTED, RECORDED}. A third member
    added without a design decision (see docs/reference/modeling.md's
    "Conducted vs recorded" framing) would silently widen what the axis
    claims to mean.
  - `conduct_mode` is never `Optional`/nullable on `RunStarted`, `Run`, or
    `StartRun`. A Run's cause is always one of the two named values; there
    is no "unknown" state for the decider or evolver to paper over with a
    guessed default at fold time. (Defaulting to CONDUCTED at construction
    is a separate, intentional choice, see each field's own docstring,
    distinct from allowing the type itself to go absent.)
"""

from __future__ import annotations

from typing import get_args, get_type_hints

import pytest

from cora.run.aggregates.run.events import RunStarted
from cora.run.aggregates.run.state import ConductMode, Run
from cora.run.features.start_run.command import StartRun


@pytest.mark.architecture
def test_conduct_mode_has_exactly_two_members() -> None:
    names = {member.name for member in ConductMode}
    assert names == {"CONDUCTED", "RECORDED"}, (
        f"ConductMode grew a member beyond {{CONDUCTED, RECORDED}}: {names}. "
        "A third mode is a design decision (who else can drive a Run's act?), "
        "not a mechanical addition; see docs/reference/modeling.md's "
        "'Conducted vs recorded' framing before widening this enum."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("carrier", [RunStarted, Run, StartRun], ids=lambda c: c.__name__)
def test_conduct_mode_field_is_never_optional(carrier: type) -> None:
    hints = get_type_hints(carrier)
    assert "conduct_mode" in hints, f"{carrier.__name__} has no conduct_mode field"
    assert type(None) not in get_args(hints["conduct_mode"]), (
        f"{carrier.__name__}.conduct_mode must never be Optional: a Run's cause "
        "is always a declared ConductMode value, never silently absent. A default "
        "value is fine (see the field's own docstring); an absent/None type is not."
    )
