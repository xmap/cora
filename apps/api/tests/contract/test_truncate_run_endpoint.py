"""Contract tests for `POST /runs/{run_id}/truncate`.

Multi-source partial-data terminal: `Running | Held -> Truncated`.
Body carries `reason` (1-500 chars) plus optional `interrupted_at`
(ISO-8601 tz-aware datetime; must not be in the future).
Re-truncating or truncating from any terminal raises 409.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    """Seed full upstream chain + start a Run. Returns the run_id."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods", json={"name": "M", "capability_id": _cap_id, "needed_family_ids": [cap_id]}
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_truncate_run_returns_204_from_running_state() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/truncate",
            json={
                "reason": "weekend power loss; abandoned mid-scan at projection 487",
                "interrupted_at": "2026-05-09T03:14:07+00:00",
            },
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_truncate_run_returns_204_from_held_state() -> None:
    """Multi-source: truncate accepts Held."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/hold")
        response = client.post(
            f"/runs/{run_id}/truncate",
            json={"reason": "interrupted while held", "interrupted_at": None},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_truncate_run_accepts_null_interrupted_at() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/truncate",
            json={"reason": "found dangling Run; interruption time unknown"},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_truncate_run_round_trips_into_get_run_response() -> None:
    """End-to-end: truncate + get → status=Truncated."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/truncate", json={"reason": "operator truncation"})
        response = client.get(f"/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "Truncated"


@pytest.mark.contract
def test_post_truncate_run_returns_404_when_run_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/runs/{missing_id}/truncate", json={"reason": "X"})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_truncate_run_returns_409_when_already_truncated() -> None:
    """Strict-not-idempotent: re-truncating raises 409."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        first = client.post(f"/runs/{run_id}/truncate", json={"reason": "first"})
        assert first.status_code == 204
        second = client.post(f"/runs/{run_id}/truncate", json={"reason": "second"})
    assert second.status_code == 409


@pytest.mark.contract
def test_post_truncate_run_returns_409_when_completed() -> None:
    """Cannot truncate a Completed Run."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        complete = client.post(f"/runs/{run_id}/complete")
        assert complete.status_code == 204
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": "X"})
    assert response.status_code == 409
    assert "Completed" in response.json()["detail"]


@pytest.mark.contract
def test_post_truncate_run_returns_409_when_aborted() -> None:
    """Cannot truncate an Aborted Run."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/abort", json={"reason": "emergency"})
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": "X"})
    assert response.status_code == 409
    assert "Aborted" in response.json()["detail"]


@pytest.mark.contract
def test_post_truncate_run_returns_409_when_stopped() -> None:
    """Cannot truncate a Stopped Run."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/stop", json={"reason": "controlled exit"})
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": "X"})
    assert response.status_code == 409
    assert "Stopped" in response.json()["detail"]


@pytest.mark.contract
def test_post_truncate_run_rejects_empty_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_truncate_run_rejects_whitespace_only_reason_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": "   "})
    assert response.status_code == 400
    assert "truncate reason" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_truncate_run_rejects_too_long_reason_with_422() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/truncate", json={"reason": "x" * 501})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_truncate_run_rejects_future_interrupted_at_with_400() -> None:
    """Decider rejects interrupted_at in the future relative to now."""
    future_iso = (datetime.now(tz=UTC) + timedelta(days=365)).isoformat()
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/truncate",
            json={"reason": "X", "interrupted_at": future_iso},
        )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_truncate_run_rejects_invalid_interrupted_at_format_with_422() -> None:
    """Pydantic rejects malformed datetime."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/truncate",
            json={"reason": "X", "interrupted_at": "not-a-datetime"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_truncate_run_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs/not-a-uuid/truncate", json={"reason": "X"})
    assert response.status_code == 422
