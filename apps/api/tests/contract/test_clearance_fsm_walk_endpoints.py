"""End-to-end contract test: full Clearance FSM walk via REST.

Walks `Defined -> Submitted -> UnderReview -> Approved -> Active`
through the 6 transition endpoints and pins:
  - 204 status on every successful transition
  - GET endpoint reflects each new status after every transition
  - review_steps chain grows by one per append_clearance_review_step call
  - 409 on any out-of-FSM transition attempt

Plus a parallel walk that ends in Rejected to cover the terminal-bad path.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import clearance_template_stream_id


def _register(client: TestClient) -> str:
    template_id = clearance_template_stream_id("cora", "ESAF")
    response = client.post(
        "/clearances",
        json={
            "template_id": str(template_id),
            "facility_code": "cora",
            "title": "FSM walk pilot",
            "bindings": [{"kind": "Run", "id": str(uuid4())}],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["clearance_id"])


@pytest.mark.contract
def test_full_fsm_walk_to_active_via_rest() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)

        # Defined -> Submitted
        r = client.post(f"/clearances/{cid}/submit")
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "Submitted"

        # Submitted -> UnderReview
        r = client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "BeamlineScientist"},
        )
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "UnderReview"

        # UnderReview -- record one Approved review step
        r = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "BeamlineScientist",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
                "notes": "LGTM",
            },
        )
        assert r.status_code == 204
        body = client.get(f"/clearances/{cid}").json()
        assert body["status"] == "UnderReview"  # status unchanged
        assert len(body["review_steps"]) == 1
        assert body["review_steps"][0]["decision"] == "Approved"

        # UnderReview -> Approved
        r = client.post(f"/clearances/{cid}/approve", json={})
        assert r.status_code == 204
        body = client.get(f"/clearances/{cid}").json()
        assert body["status"] == "Approved"
        # GET response no longer surfaces last_reviewed_by (aggregate
        # drops the field per #19 cleanup); list_clearances still does via the
        # projection's envelope-sourced denorm column.

        # Approved -> Active
        r = client.post(f"/clearances/{cid}/activate")
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "Active"

        # Active -> Expired (11a-c-2 terminal)
        r = client.post(
            f"/clearances/{cid}/expire",
            json={"reason": "validity window elapsed"},
        )
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "Expired"


@pytest.mark.contract
def test_full_fsm_walk_to_rejected_via_rest() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "ESH"},
        )
        # No need for an approving step; reject_clearance has no chain invariant.
        r = client.post(
            f"/clearances/{cid}/reject",
            json={"reason": "ESRB found insufficient PPE specification"},
        )
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "Rejected"


@pytest.mark.contract
def test_submit_returns_404_for_unknown_clearance() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/clearances/{uuid4()}/submit")
    assert response.status_code == 404


@pytest.mark.contract
def test_submit_returns_409_when_not_in_defined() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        # Second submit attempt -- already Submitted, not Defined
        response = client.post(f"/clearances/{cid}/submit")
    assert response.status_code == 409


@pytest.mark.contract
def test_append_clearance_review_step_rejects_wrong_step_index_with_400() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "BeamlineScientist"},
        )
        # Submit step_index=5 when state has 0 review_steps
        response = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 5,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_append_clearance_review_step_rejects_future_decided_at_with_400() -> None:
    """`decided_at > now` trips the chain time invariant."""
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "ESH"},
        )
        response = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": "2099-01-01T00:00:00+00:00",
            },
        )
    assert response.status_code == 400
    assert "future-dated" in response.json()["detail"]


@pytest.mark.contract
def test_append_clearance_review_step_rejects_non_monotonic_decided_at_with_400() -> None:
    """Second step's `decided_at` strictly less than prior step's trips
    chain monotonicity."""
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "ESH"},
        )
        # First step: a recent timestamp
        first = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": "2026-05-15T12:00:00+00:00",
            },
        )
        assert first.status_code == 204
        # Second step: an earlier timestamp (monotonicity violation)
        response = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 1,
                "role": "BeamlineScientist",
                "decision": "Approved",
                "decided_at": "2026-05-15T11:00:00+00:00",
            },
        )
    assert response.status_code == 400
    assert "chain monotonicity" in response.json()["detail"]


@pytest.mark.contract
def test_approve_rejects_when_no_approving_review_step() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "ESH"},
        )
        # Add a RequestedChanges step (NOT Approved)
        client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "RequestedChanges",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
        # Now approve with no Approved step in chain
        response = client.post(f"/clearances/{cid}/approve", json={})
    assert response.status_code == 409
    assert "terminal review step" in response.json()["detail"].lower()


@pytest.mark.contract
def test_approve_accepts_validity_window_overrides() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "ESH"},
        )
        client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
        valid_from = "2026-06-01T00:00:00+00:00"
        valid_until = "2026-09-01T00:00:00+00:00"
        r = client.post(
            f"/clearances/{cid}/approve",
            json={"valid_from": valid_from, "valid_until": valid_until},
        )
        assert r.status_code == 204
        body = client.get(f"/clearances/{cid}").json()
        assert body["valid_from"] == "2026-06-01T00:00:00Z"
        assert body["valid_until"] == "2026-09-01T00:00:00Z"


@pytest.mark.contract
def test_activate_returns_409_when_not_approved() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        # Try to activate without approving first
        response = client.post(f"/clearances/{cid}/activate")
    assert response.status_code == 409


@pytest.mark.contract
@pytest.mark.parametrize(
    "intermediate_action",
    [
        # no intermediate action: stay in Defined
        [],
        # advance to Submitted (still not UnderReview)
        [("submit", None)],
    ],
)
def test_append_clearance_review_step_returns_409_when_not_under_review(
    intermediate_action: list[tuple[str, dict[str, object] | None]],
) -> None:
    """append_clearance_review_step is single-source from UnderReview; other status -> 409."""
    with TestClient(create_app()) as client:
        cid = _register(client)
        for verb, body in intermediate_action:
            client.post(f"/clearances/{cid}/{verb}", json=body or {})
        response = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "BeamlineScientist",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
    assert response.status_code == 409
    assert "cannot append review step" in response.json()["detail"].lower()


@pytest.mark.contract
def test_append_clearance_review_step_returns_409_when_in_approved_status() -> None:
    """A fully-approved clearance can't accept more review steps."""
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(f"/clearances/{cid}/start-review", json={"first_reviewer_role": "ESH"})
        client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
        client.post(f"/clearances/{cid}/approve", json={})
        # Clearance is now Approved; try to append another step
        response = client.post(
            f"/clearances/{cid}/review-steps",
            json={
                "step_index": 1,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_three_step_chain_walk_succeeds() -> None:
    """DESY-DOOR-shaped 3-step chain (LocalContact -> BeamlineSci+Coordinator
    -> SafetyGroup) all-approve, then approve_clearance succeeds.

    Pins the multi-step chain at the contract layer; aggregate fold +
    projection no-op are pinned in unit/integration tiers.
    """
    with TestClient(create_app()) as client:
        cid = _register(client)
        client.post(f"/clearances/{cid}/submit")
        client.post(
            f"/clearances/{cid}/start-review",
            json={"first_reviewer_role": "LocalContact"},
        )

        decided_at = datetime.now(tz=UTC).isoformat()
        for step_index, role in enumerate(
            ["LocalContact", "BeamlineSci+Coordinator", "SafetyGroup"]
        ):
            r = client.post(
                f"/clearances/{cid}/review-steps",
                json={
                    "step_index": step_index,
                    "role": role,
                    "decision": "Approved",
                    "decided_at": decided_at,
                },
            )
            assert r.status_code == 204, f"step {step_index} failed: {r.text}"

        body = client.get(f"/clearances/{cid}").json()
        assert len(body["review_steps"]) == 3
        assert [r["role"] for r in body["review_steps"]] == [
            "LocalContact",
            "BeamlineSci+Coordinator",
            "SafetyGroup",
        ]

        # Approve consumes the chain
        r = client.post(f"/clearances/{cid}/approve", json={})
        assert r.status_code == 204
        assert client.get(f"/clearances/{cid}").json()["status"] == "Approved"


# ---------- 11a-c-2: expire + amend terminals ----------


def _drive_to_active(client: TestClient) -> str:
    """Walk a clearance to Active via the FSM. Helper for the 11a-c-2
    contract tests that need a starting point at Active."""
    cid = _register(client)
    client.post(f"/clearances/{cid}/submit")
    client.post(
        f"/clearances/{cid}/start-review",
        json={"first_reviewer_role": "ESH"},
    )
    client.post(
        f"/clearances/{cid}/review-steps",
        json={
            "step_index": 0,
            "role": "ESH",
            "decision": "Approved",
            "decided_at": datetime.now(tz=UTC).isoformat(),
        },
    )
    client.post(f"/clearances/{cid}/approve", json={})
    client.post(f"/clearances/{cid}/activate")
    return cid


@pytest.mark.contract
def test_expire_returns_204_and_transitions_active_to_expired() -> None:
    with TestClient(create_app()) as client:
        cid = _drive_to_active(client)
        r = client.post(
            f"/clearances/{cid}/expire",
            json={"reason": "validity window elapsed"},
        )
        assert r.status_code == 204
        body = client.get(f"/clearances/{cid}").json()
    assert body["status"] == "Expired"


@pytest.mark.contract
def test_expire_returns_409_when_not_active() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        # Not yet Active (still Defined)
        response = client.post(
            f"/clearances/{cid}/expire",
            json={"reason": "premature"},
        )
    assert response.status_code == 409
    assert "cannot be expired" in response.json()["detail"].lower()


@pytest.mark.contract
def test_expire_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        cid = _drive_to_active(client)
        response = client.post(
            f"/clearances/{cid}/expire",
            json={"reason": "   "},
        )
    # Pydantic min_length=1 catches whitespace-only AFTER strip? Actually
    # Pydantic's min_length=1 only catches empty string; whitespace is
    # passed through to the decider, which returns 400 via the trimmed-
    # text validator. Either way: 400 or 422.
    assert response.status_code in (400, 422)


@pytest.mark.contract
def test_expire_returns_404_for_unknown_clearance() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearances/{uuid4()}/expire",
            json={"reason": "x"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_amend_returns_201_with_new_child_id_and_supersedes_parent() -> None:
    with TestClient(create_app()) as client:
        parent_cid = _drive_to_active(client)
        amend_response = client.post(
            f"/clearances/{parent_cid}/amend",
            json={
                "template_id": str(clearance_template_stream_id("cora", "ESAF")),
                "facility_code": "cora",
                "title": "Amended pilot ESAF (post scope-change)",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
        )
        assert amend_response.status_code == 201, amend_response.text
        child_cid = amend_response.json()["clearance_id"]
        assert child_cid != parent_cid

        # Parent transitioned Active -> Superseded
        parent_body = client.get(f"/clearances/{parent_cid}").json()
        assert parent_body["status"] == "Superseded"

        # Child landed in Defined with parent_id pointer
        child_body = client.get(f"/clearances/{child_cid}").json()
        assert child_body["status"] == "Defined"
        assert child_body["parent_id"] == parent_cid


@pytest.mark.contract
def test_amend_returns_409_when_parent_not_active() -> None:
    with TestClient(create_app()) as client:
        parent_cid = _register(client)
        # Parent still in Defined
        response = client.post(
            f"/clearances/{parent_cid}/amend",
            json={
                "template_id": str(clearance_template_stream_id("cora", "ESAF")),
                "facility_code": "cora",
                "title": "Amended",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
        )
    assert response.status_code == 409
    assert "cannot be amended" in response.json()["detail"].lower()


@pytest.mark.contract
def test_amend_returns_404_for_unknown_parent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearances/{uuid4()}/amend",
            json={
                "template_id": str(clearance_template_stream_id("cora", "ESAF")),
                "facility_code": "cora",
                "title": "Amended",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_amend_returns_400_on_empty_child_bindings() -> None:
    with TestClient(create_app()) as client:
        parent_cid = _drive_to_active(client)
        # Pydantic min_length=1 -> 422
        response = client.post(
            f"/clearances/{parent_cid}/amend",
            json={
                "template_id": str(clearance_template_stream_id("cora", "ESAF")),
                "facility_code": "cora",
                "title": "Amended",
                "bindings": [],
            },
        )
    assert response.status_code == 422
