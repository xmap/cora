"""Tests for the AuthorityRevocation Decision vocabulary.

Covers the DECISION_CONTEXT_AUTHORITY_REVOCATION context constant used by
the authority-revocation-holder Reaction when it records why an in-flight
run was held after a principal's grant was revoked. The holder reuses the
existing `Hold` DecisionChoice (a reversible hold is its only
disposition), so there is no new closed choice set to pin here; the
context constant itself is the vocabulary this slice adds. Mirrors
test_run_supervision_vocab.py.
"""

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_AUTHORITY_REVOCATION,
    DecisionChoice,
)


@pytest.mark.unit
def test_decision_context_authority_revocation_constant() -> None:
    assert DECISION_CONTEXT_AUTHORITY_REVOCATION == "AuthorityRevocation"


@pytest.mark.unit
def test_hold_is_a_valid_decision_choice() -> None:
    """The holder records choice='Hold'; confirm it is an accepted
    DecisionChoice value (the holder reuses it rather than minting a new
    AuthorityRevocation-specific choice)."""
    assert DecisionChoice("Hold").value == "Hold"
