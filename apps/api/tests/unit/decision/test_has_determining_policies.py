"""Unit tests for the `has_determining_policies` predicate."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_POLICY_GRANT,
    DECISION_CONTEXT_RECIPE_APPROVAL,
    DECISION_CONTEXT_RUN_ABORT,
    Decision,
    DecisionChoice,
    DecisionContext,
    has_determining_policies,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _decision(
    context: str = DECISION_CONTEXT_POLICY_GRANT,
    alternatives: tuple[str, ...] = (),
) -> Decision:
    return Decision(
        id=uuid4(),
        decided_by=ActorId(uuid4()),
        decided_at=_NOW,
        context=DecisionContext(context),
        choice=DecisionChoice("Allow"),
        alternatives=alternatives,
    )


@pytest.mark.unit
def test_has_determining_policies_true_for_policy_grant_with_alternatives() -> None:
    """Cedar/OPA convention: PolicyGrant with at least one
    determining policy in alternatives is the audit-ready shape."""
    decision = _decision(
        context=DECISION_CONTEXT_POLICY_GRANT,
        alternatives=("policy:grant_read", "policy:grant_write"),
    )
    assert has_determining_policies(decision) is True


@pytest.mark.unit
def test_has_determining_policies_false_for_policy_grant_without_alternatives() -> None:
    """A PolicyGrant Decision missing its determining policies is
    the audit-incomplete shape; auditors flag these."""
    decision = _decision(context=DECISION_CONTEXT_POLICY_GRANT, alternatives=())
    assert has_determining_policies(decision) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "context",
    [DECISION_CONTEXT_RECIPE_APPROVAL, DECISION_CONTEXT_RUN_ABORT, "FacilityCustom"],
)
def test_has_determining_policies_false_for_non_policy_grant_contexts(context: str) -> None:
    """The Cedar-style determining-policies convention only
    applies to PolicyGrant context. Non-PolicyGrant Decisions may
    have alternatives for OTHER reasons (top-k considered options),
    but those aren't 'determining policies' in Cedar's sense."""
    decision = _decision(context=context, alternatives=("a", "b"))
    assert has_determining_policies(decision) is False


@pytest.mark.unit
def test_has_determining_policies_false_for_non_policy_grant_without_alternatives() -> None:
    """Trivial case: non-PolicyGrant + empty alternatives is
    structurally not the determining-policies shape."""
    decision = _decision(context=DECISION_CONTEXT_RECIPE_APPROVAL, alternatives=())
    assert has_determining_policies(decision) is False


@pytest.mark.unit
def test_has_determining_policies_inverse_pattern_for_auditor_use_case() -> None:
    """Document the auditor's call-site shape: 'PolicyGrant
    decisions missing their determining policies' composes as
    NOT has_determining_policies AND context==PolicyGrant.
    """
    # PolicyGrant missing determining policies (auditor flags)
    incomplete = _decision(context=DECISION_CONTEXT_POLICY_GRANT, alternatives=())
    # PolicyGrant with determining policies (auditor passes)
    complete = _decision(
        context=DECISION_CONTEXT_POLICY_GRANT,
        alternatives=("policy:role_admin",),
    )
    # Non-PolicyGrant (auditor doesn't apply rule)
    non_pg = _decision(context=DECISION_CONTEXT_RUN_ABORT, alternatives=("a",))

    def auditor_flags_incomplete_policy_grant(d: Decision) -> bool:
        return d.context.value == DECISION_CONTEXT_POLICY_GRANT and not has_determining_policies(d)

    assert auditor_flags_incomplete_policy_grant(incomplete) is True
    assert auditor_flags_incomplete_policy_grant(complete) is False
    assert auditor_flags_incomplete_policy_grant(non_pg) is False
