"""HTTP contract tests for the 3 Ratification endpoints.

Consolidated coverage file: covers `request_ratification`, `grant_ratification`,
and `deny_ratification` per the arch-fitness substring-match rule. Pins the REST
surface: status codes, body shapes, the four-eyes independence mapping, and the
404 / 409 / 400 error mappings.

Principal note: the pool-less TestClient runs in legacy posture, so a request
with no `X-Principal-Id` header runs as SYSTEM_PRINCIPAL_ID. Two requests both
sent without a header therefore share one principal, which is exactly the
self-sign (independence-breach) case; an independent co-signer is simulated by
sending a distinct `X-Principal-Id` header on the grant / deny call.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_COMMAND_NAME = "AbortRun"
_CONSEQUENCE_CLASS = "first_of_kind"
_OTHER_PRINCIPAL = "01910000-0000-7000-8000-0000000000c1"


def _request_ratification(client: TestClient) -> str:
    """Request a fresh Ratification, return its id. Status starts at Requested.

    Sent with no X-Principal-Id, so the requester is SYSTEM_PRINCIPAL_ID.
    """
    ratification_id = str(uuid4())
    response = client.post(
        "/ratifications",
        json={
            "ratification_id": ratification_id,
            "target_action_id": str(uuid4()),
            "command_name": _COMMAND_NAME,
            "consequence_class": _CONSEQUENCE_CLASS,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["ratification_id"] == ratification_id
    return ratification_id


# ---------------------------------------------------------------------------
# request_ratification (POST /ratifications)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_post_ratifications_returns_201_with_caller_supplied_id() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
    assert rid


@pytest.mark.contract
def test_post_ratifications_returns_409_when_ratification_id_collides() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        second = client.post(
            "/ratifications",
            json={
                "ratification_id": rid,
                "target_action_id": str(uuid4()),
                "command_name": _COMMAND_NAME,
                "consequence_class": _CONSEQUENCE_CLASS,
            },
        )
    assert second.status_code == 409


@pytest.mark.contract
def test_post_ratifications_returns_400_on_whitespace_only_consequence_class() -> None:
    """Whitespace-only consequence_class trips the domain guard -> 400."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/ratifications",
            json={
                "ratification_id": str(uuid4()),
                "target_action_id": str(uuid4()),
                "command_name": _COMMAND_NAME,
                "consequence_class": "   ",
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_ratifications_returns_422_when_consequence_class_missing() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/ratifications",
            json={
                "ratification_id": str(uuid4()),
                "target_action_id": str(uuid4()),
                "command_name": _COMMAND_NAME,
            },
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# grant_ratification (POST /ratifications/{id}/grant)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_grant_returns_204_for_independent_principal() -> None:
    """An independent co-signer (distinct X-Principal-Id) grants -> 204."""
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(
            f"/ratifications/{rid}/grant",
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_grant_returns_409_when_requester_self_signs() -> None:
    """Four-eyes: same principal (no header on either call) grants -> 409."""
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(f"/ratifications/{rid}/grant")
    assert response.status_code == 409


@pytest.mark.contract
def test_grant_returns_404_when_ratification_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/ratifications/{uuid4()}/grant",
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_grant_returns_409_when_already_granted() -> None:
    """Grant from a terminal (Granted) status -> 409."""
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        assert (
            client.post(
                f"/ratifications/{rid}/grant",
                headers={"X-Principal-Id": _OTHER_PRINCIPAL},
            ).status_code
            == 204
        )
        response = client.post(
            f"/ratifications/{rid}/grant",
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# deny_ratification (POST /ratifications/{id}/deny)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_deny_returns_204_for_independent_principal_with_reason() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(
            f"/ratifications/{rid}/deny",
            json={"reason": "unsafe first-of-kind action"},
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_deny_returns_409_when_requester_self_signs() -> None:
    """Four-eyes: same principal (no header) denies -> 409."""
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(f"/ratifications/{rid}/deny", json={"reason": "no"})
    assert response.status_code == 409


@pytest.mark.contract
def test_deny_returns_404_when_ratification_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/ratifications/{uuid4()}/deny",
            json={"reason": "no"},
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_deny_returns_409_when_already_granted() -> None:
    """Deny from a terminal (Granted) status -> 409."""
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        client.post(f"/ratifications/{rid}/grant", headers={"X-Principal-Id": _OTHER_PRINCIPAL})
        response = client.post(
            f"/ratifications/{rid}/deny",
            json={"reason": "too late"},
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_deny_returns_400_on_whitespace_only_reason() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(
            f"/ratifications/{rid}/deny",
            json={"reason": "   "},
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_deny_returns_422_when_reason_missing() -> None:
    with TestClient(create_app()) as client:
        rid = _request_ratification(client)
        response = client.post(
            f"/ratifications/{rid}/deny",
            json={},
            headers={"X-Principal-Id": _OTHER_PRINCIPAL},
        )
    assert response.status_code == 422
