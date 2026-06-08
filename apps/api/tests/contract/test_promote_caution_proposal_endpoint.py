"""Contract tests for `POST /agents/caution-drafter/decisions/{id}/promote`.

Drives the route end-to-end through TestClient: seeds a
CautionProposal Decision via the app's wired kernel, then
exercises the promote endpoint. Covers status-code surface:
201 happy paths (register + supersede dispatch), 404 unknown id,
400 wrong context / non-actionable / malformed, 422 malformed path
param, plus Idempotency-Key header propagation.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.agent.features.promote_caution_proposal.route import _get_handler
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    seed_caution_drafter_agent,
)
from cora.api.main import create_app
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DECISION_CONTEXT_RUN_DEBRIEF,
    DecisionConfidenceSource,
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_ASSET_ID = UUID("01900000-0000-7000-8000-000000000aaa")
_SYS_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
_TEST_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000099aaa")

_PROPOSED_CAUTION_NOTICE: dict[str, Any] = {
    "target_kind": "Asset",
    "target_id": str(_ASSET_ID),
    "category": "Wear",
    "severity": "Notice",
    "title": "Encoder drift after extended rotation",
    "body": (
        "Re-home the rotary stage encoder every 10 minutes of continuous "
        "rotation; drift accumulates and triggers interlock at ~12 minutes."
    ),
    "tags": ["encoder", "rotary-stage"],
}


async def _seed_caution_proposal_decision(
    app: FastAPI,
    *,
    decision_id: UUID,
    choice: str = "ProposeNotice",
    context: str = DECISION_CONTEXT_CAUTION_PROPOSAL,
    inputs: dict[str, Any] | None = None,
) -> None:
    """Append a CautionProposal Decision directly via the app's kernel.

    The Decision's `actor_id` is `CAUTION_DRAFTER_AGENT_ID` and the
    CautionDrafter Agent is seeded first, so the provenance gate
    in `promote_caution_proposal.handler` passes.
    """
    deps = app.state.deps
    await seed_caution_drafter_agent(deps)
    actor_id = CAUTION_DRAFTER_AGENT_ID
    event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(actor_id),
        context=context,
        choice=choice,
        parent_id=None,
        override_kind=None,
        rule="agent:CautionDrafter:v1",
        reasoning="contract-test rationale narrative spanning enough words for the validator",
        confidence=0.7,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=inputs if inputs is not None else {"proposed_caution": _PROPOSED_CAUTION_NOTICE},
        reasoning_signature=None,
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_T0,
        event_id=uuid4(),
        command_name="CautionDrafterSubscriber",
        correlation_id=_TEST_CORRELATION_ID,
        causation_id=None,
        principal_id=actor_id,
    )
    await deps.event_store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_existing_caution_for_supersede(app: FastAPI) -> UUID:
    """Register a Caution against `_ASSET_ID` via Caution BC's slice;
    returns the new caution_id (operator-facing input to supersede)."""
    deps = app.state.deps
    register = bind_register_caution(deps)
    return await register(
        RegisterCaution(
            target=AssetTarget(asset_id=_ASSET_ID),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.NOTICE,
            text="prior contract-test",
            workaround="prior workaround narrative for the contract test",
            tags=frozenset(),
        ),
        principal_id=_SYS_PRINCIPAL_ID,
        correlation_id=_TEST_CORRELATION_ID,
    )


# ---------------------------------------------------------------------------
# Status-code surface
# ---------------------------------------------------------------------------


@pytest.mark.contract
async def test_post_promote_happy_path_register_dispatch_returns_201() -> None:
    """Happy path: ProposeNotice → register_caution → 201 with caution_id."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(cast("FastAPI", client.app), decision_id=decision_id)
        response = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
        )
    assert response.status_code == 201, response.text
    body = response.json()
    # caution_id is a UUID string in the response.
    UUID(body["caution_id"])  # raises ValueError if not a valid UUID


@pytest.mark.contract
async def test_post_promote_happy_path_supersede_dispatch_returns_201() -> None:
    """Happy path: ProposeSupersede → supersede_caution → 201 with NEW caution_id."""
    with TestClient(create_app()) as client:
        prior_caution_id = await _seed_existing_caution_for_supersede(cast("FastAPI", client.app))
        decision_id = uuid4()
        proposed = dict(_PROPOSED_CAUTION_NOTICE)
        proposed["severity"] = "Caution"
        proposed["title"] = "Refined: encoder drift mitigation"
        proposed["supersedes_caution_id"] = str(prior_caution_id)
        await _seed_caution_proposal_decision(
            cast("FastAPI", client.app),
            decision_id=decision_id,
            choice="ProposeSupersede",
            inputs={"proposed_caution": proposed},
        )
        response = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
        )
    assert response.status_code == 201, response.text
    body = response.json()
    new_caution_id = UUID(body["caution_id"])
    # New Caution is a fresh aggregate (supersede creates a child).
    assert new_caution_id != prior_caution_id


@pytest.mark.contract
def test_post_promote_returns_404_on_unknown_decision_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/agents/caution-drafter/decisions/{uuid4()}/promote",
        )
    assert response.status_code == 404, response.text


@pytest.mark.contract
async def test_post_promote_returns_400_on_wrong_context() -> None:
    """Promoting a RunDebrief Decision (not a CautionProposal) is a 400."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(
            cast("FastAPI", client.app),
            decision_id=decision_id,
            context=DECISION_CONTEXT_RUN_DEBRIEF,
            choice="NominalCompletion",
            inputs={"run_id": str(uuid4())},
        )
        response = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
        )
    assert response.status_code == 400, response.text
    assert "CautionProposal" in response.json()["detail"]


@pytest.mark.contract
async def test_post_promote_returns_400_on_no_action_choice() -> None:
    """`NoAction` is the agent's refusal verdict; not promotable."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(
            cast("FastAPI", client.app),
            decision_id=decision_id,
            choice="NoAction",
            inputs={"reason": "no signal worth a caution"},
        )
        response = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
        )
    assert response.status_code == 400, response.text
    assert "NoAction" in response.json()["detail"]


@pytest.mark.contract
async def test_post_promote_returns_400_on_malformed_proposed_caution() -> None:
    """A Propose* choice with no `proposed_caution` payload is malformed."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(
            cast("FastAPI", client.app),
            decision_id=decision_id,
            choice="ProposeNotice",
            inputs={},  # no proposed_caution
        )
        response = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
        )
    assert response.status_code == 400, response.text
    assert "malformed" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_promote_returns_422_on_malformed_uuid_path_param() -> None:
    """Pydantic path validation: malformed UUID in URL -> 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/agents/caution-drafter/decisions/not-a-uuid/promote",
        )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Idempotency-Key header propagation
# ---------------------------------------------------------------------------


@pytest.mark.contract
async def test_post_promote_same_idempotency_key_replays_cached_caution_id() -> None:
    """Same Idempotency-Key on retry returns the same caution_id (Brandur envelope)."""
    with TestClient(create_app()) as client:
        decision_id = uuid4()
        await _seed_caution_proposal_decision(cast("FastAPI", client.app), decision_id=decision_id)
        first = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
            headers={"Idempotency-Key": "test-key-001"},
        )
        # NOTE: a second call with the same Idempotency-Key against the
        # SAME decision_id would normally also re-trigger the decider
        # (which is fine — re-loading the same Decision is idempotent at
        # the read side). The Brandur cache should short-circuit and
        # return the cached caution_id from the first call.
        second = client.post(
            f"/agents/caution-drafter/decisions/{decision_id}/promote",
            headers={"Idempotency-Key": "test-key-001"},
        )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["caution_id"] == second.json()["caution_id"]


# ---------------------------------------------------------------------------
# Authorize-denial path
# ---------------------------------------------------------------------------


@pytest.mark.contract
async def test_post_promote_returns_403_when_authorize_denies() -> None:
    """Override the route's handler dependency with one that raises
    UnauthorizedError to verify the route maps it to 403 via the
    Agent BC's app-scoped exception handler."""
    from cora.agent.errors import UnauthorizedError

    app = create_app()

    async def _denying_handler(*args: Any, **kwargs: Any) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for contract test")

    app.dependency_overrides[_get_handler] = lambda: _denying_handler

    with TestClient(app) as client:
        response = client.post(
            f"/agents/caution-drafter/decisions/{uuid4()}/promote",
        )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "denied for contract test"
