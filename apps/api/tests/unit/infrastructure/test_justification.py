"""Unit tests for `cora.shared.justification` (the obligation-gate primitive).

Coverage:
  - Declared set contains AbortRun (the first opt-in); a non-declared command is
    unaffected (the gate is inert for it).
  - Non-declared command: justification is optional; None stays None, text is
    trimmed, blank-after-trim collapses to None.
  - Declared command: justification is a fail-closed precondition (None, blank,
    and over-length all raise; valid text is returned trimmed).
  - Kind-blindness: the surface takes no actor-kind argument, so the same
    (command, justification) yields the same result regardless of who calls it.
  - The error carries the command name and maps cleanly to an API 422.
"""

import pytest

from cora.shared import justification as j
from cora.shared.justification import (
    COMMANDS_REQUIRING_JUSTIFICATION,
    JUSTIFICATION_MAX_LENGTH,
    JustificationRequiredError,
    require_justification,
)

# ---------- declared set membership (obligation gate opt-ins) ----------


@pytest.mark.unit
def test_declared_set_contains_abort_run() -> None:
    """AbortRun is the first command to opt into the obligation gate (Gate III):
    aborting a running experiment requires an admission justification."""
    assert "AbortRun" in COMMANDS_REQUIRING_JUSTIFICATION


# ---------- non-declared command: justification is optional ----------


@pytest.mark.unit
def test_non_declared_command_none_justification_returns_none() -> None:
    assert require_justification("some_command", None) is None


@pytest.mark.unit
def test_non_declared_command_trims_supplied_text() -> None:
    assert require_justification("some_command", "  because  ") == "because"


@pytest.mark.unit
def test_non_declared_command_blank_text_collapses_to_none() -> None:
    assert require_justification("some_command", "   ") is None


@pytest.mark.unit
def test_non_declared_command_overlength_is_allowed_and_trimmed() -> None:
    # Pins BOTH behaviors on the optional branch in one assertion: over-length is
    # allowed (not required, so no ceiling) AND surrounding whitespace is trimmed.
    long = "x" * (JUSTIFICATION_MAX_LENGTH + 50)
    assert require_justification("some_command", f"  {long}  ") == long


# ---------- declared command: fail-closed precondition ----------


@pytest.fixture
def declared(monkeypatch: pytest.MonkeyPatch) -> str:
    """Add one command to the declared class for the duration of a test."""
    name = "gated_command"
    monkeypatch.setattr(j, "COMMANDS_REQUIRING_JUSTIFICATION", frozenset({name}))
    return name


@pytest.mark.unit
def test_declared_command_missing_justification_raises(declared: str) -> None:
    with pytest.raises(JustificationRequiredError):
        require_justification(declared, None)


@pytest.mark.unit
def test_declared_command_blank_justification_raises(declared: str) -> None:
    with pytest.raises(JustificationRequiredError):
        require_justification(declared, "   ")


@pytest.mark.unit
def test_declared_command_overlength_justification_raises(declared: str) -> None:
    with pytest.raises(JustificationRequiredError):
        require_justification(declared, "x" * (JUSTIFICATION_MAX_LENGTH + 1))


@pytest.mark.unit
def test_declared_command_valid_justification_returns_trimmed(declared: str) -> None:
    assert require_justification(declared, "  aligning the sample  ") == "aligning the sample"


@pytest.mark.unit
def test_declared_command_justification_at_max_length_ok(declared: str) -> None:
    text = "y" * JUSTIFICATION_MAX_LENGTH
    assert require_justification(declared, text) == text


# ---------- the error carries the command name (for the API 422 mapping) ----------


@pytest.mark.unit
def test_error_carries_command_name(declared: str) -> None:
    try:
        require_justification(declared, None)
    except JustificationRequiredError as exc:
        assert exc.command_name == declared
        assert declared in str(exc)
    else:  # pragma: no cover - the call above must raise
        pytest.fail("expected JustificationRequiredError")


# ---------- kind-blindness: no actor-kind argument exists in the surface ----------


@pytest.mark.unit
def test_require_justification_takes_no_actor_kind_argument() -> None:
    import inspect

    params = set(inspect.signature(require_justification).parameters)
    assert params == {"command_name", "justification"}
    # The obligation-gate kind-blindness invariant, enforced structurally: there
    # is no parameter through which a caller could pass or branch on actor kind.


@pytest.mark.unit
def test_same_inputs_same_result_regardless_of_caller(declared: str) -> None:
    # No caller identity is threaded in, so two "different principals" issuing
    # the identical (command, justification) get byte-identical results.
    a = require_justification(declared, "  same reason  ")
    b = require_justification(declared, "  same reason  ")
    assert a == b == "same reason"
