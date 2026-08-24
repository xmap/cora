"""Unit tests for the two named quality floors.

The functions are one comparison each, so the value of testing them is
not arithmetic. It is pinning the DIFFERENCE, in the one case where the
two floors disagree, and pinning the direction of that disagreement
against the mistake that shipped three times: answering "can I believe
this" with the test for "can I act on it".
"""

import pytest

from cora.shared.quality import actionable, believable

pytestmark = pytest.mark.unit


def test_only_bad_is_unbelievable() -> None:
    assert believable("Good") is True
    assert believable("Uncertain") is True
    assert believable("Bad") is False


def test_only_good_is_actionable() -> None:
    assert actionable("Good") is True
    assert actionable("Uncertain") is False
    assert actionable("Bad") is False


def test_the_two_floors_differ_on_uncertain_alone() -> None:
    """The whole reason both exist, stated as an assertion.

    `Good` and `Bad` are agreed by both floors, so a consumer that picks
    the wrong one behaves correctly on two thirds of the enum and wrongly
    on the third. That is what made the same defect ship three times
    without a test catching it: nothing goes visibly wrong until a
    facility annotates the exact signal being read, and a facility
    annotates precisely the signals worth an operator's attention.
    """
    agreed = [q for q in ("Good", "Uncertain", "Bad") if believable(q) == actionable(q)]
    assert agreed == ["Good", "Bad"]
    assert believable("Uncertain") and not actionable("Uncertain")


def test_an_alarming_reading_is_believable_but_not_actionable() -> None:
    """The live shape behind all three bugs, in the vocabulary CORA sees.

    EPICS MINOR and MAJOR both collapse to `Uncertain` at the adapter
    (only INVALID becomes `Bad`), so this single value is what a hutch
    permit, a tripped BLEPS flag and an open beam shutter all arrive as.
    Recording any of them is right; driving a procedure step off one is
    not.
    """
    assert believable("Uncertain")
    assert not actionable("Uncertain")


def test_bad_is_refused_by_both_floors() -> None:
    """Loosening the record floor did not loosen it to everything.

    `Bad` is the one value saying the number itself is untrustworthy
    rather than the world being interesting, so it stays disqualifying
    even for a consumer that only wants to write down what it saw.
    """
    assert not believable("Bad")
    assert not actionable("Bad")
