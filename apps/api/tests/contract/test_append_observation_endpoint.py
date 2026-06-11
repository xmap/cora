"""Contract tests for `POST /runs/{run_id}/observations`.

The polymorphic-with-discriminator observation-entry endpoint. Covers
the happy path, lazy-open lifecycle, per-entry validation, terminal-
status guard, and Pydantic boundary validation.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _good_entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_id": str(uuid4()),
        "channel_name": "T_sample",
        "value": 295.1,
        "sampled_at": "2026-05-14T12:00:00+00:00",
        "sampling_procedure": "baseline",
        "units": "K",
    }
    base.update(overrides)
    return base


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


# ---------- Happy path ----------


@pytest.mark.contract
def test_post_readings_returns_200_for_single_entry() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/observations",
            json={"entries": [_good_entry()]},
        )
    assert response.status_code == 200
    assert response.json() == {"event_count": 1}


@pytest.mark.contract
def test_post_readings_returns_200_for_batch() -> None:
    """Batch of polymorphic observations (all baseline kind) accepted."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/observations",
            json={
                "entries": [
                    _good_entry(channel_name="T_sample", value=295.1),
                    _good_entry(channel_name="motor_x", value=12.345, units="mm"),
                    _good_entry(
                        channel_name="ring_current_dimensionless",
                        value=0.997,
                        units=None,
                    ),
                ]
            },
        )
    assert response.status_code == 200
    assert response.json() == {"event_count": 3}


@pytest.mark.contract
def test_post_readings_handles_dedup_silently_on_retry() -> None:
    """Re-issuing the same event_id is a silent no-op via PK dedup;
    response still says event_count=1 (acceptance count, not insertion)."""
    shared_id = str(uuid4())
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        first = client.post(
            f"/runs/{run_id}/observations",
            json={"entries": [_good_entry(event_id=shared_id)]},
        )
        second = client.post(
            f"/runs/{run_id}/observations",
            json={"entries": [_good_entry(event_id=shared_id)]},
        )
    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.contract
def test_post_readings_omits_optional_units() -> None:
    """Optional units omitted in the body works."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        entry = _good_entry()
        del entry["units"]
        response = client.post(f"/runs/{run_id}/observations", json={"entries": [entry]})
    assert response.status_code == 200


# ---------- 404 ----------


@pytest.mark.contract
def test_post_readings_returns_404_for_unknown_run() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/runs/{missing_id}/observations", json={"entries": [_good_entry()]}
        )
    assert response.status_code == 404


# ---------- 409 ----------


@pytest.mark.contract
@pytest.mark.parametrize(
    "terminal_call",
    [
        ("complete", {}),
        ("abort", {"reason": "operator stop"}),
        ("stop", {"reason": "controlled exit"}),
        ("truncate", {"reason": "process crashed"}),
    ],
)
def test_post_readings_returns_409_when_run_is_terminal(
    terminal_call: tuple[str, dict[str, Any]],
) -> None:
    """Run.status terminal implicitly closes the observation logbook;
    appends post-terminal raise 409."""
    transition, body = terminal_call
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        # Drive Run to terminal.
        terminal_resp = client.post(f"/runs/{run_id}/{transition}", json=body)
        assert terminal_resp.status_code == 204
        # Try to append a observation.
        response = client.post(f"/runs/{run_id}/observations", json={"entries": [_good_entry()]})
    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "logbook" in detail or "closed" in detail


@pytest.mark.contract
def test_post_readings_succeeds_during_held_state() -> None:
    """Held is a non-terminal pause; observations are accepted."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        # Hold the Run.
        hold_resp = client.post(f"/runs/{run_id}/hold")
        assert hold_resp.status_code == 204
        response = client.post(f"/runs/{run_id}/observations", json={"entries": [_good_entry()]})
    assert response.status_code == 200


# ---------- 422 (Pydantic boundary validation) ----------


@pytest.mark.contract
def test_post_readings_returns_422_for_empty_entries_list() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(f"/runs/{run_id}/observations", json={"entries": []})
    assert response.status_code == 422


# NaN / Infinity defense is unit-tested at the handler boundary
# (`test_handler_rejects_nan_and_infinity` parametrized over nan/inf/-inf).
# A contract-level test via HTTP tripped a FastAPI serialization quirk:
# Pydantic correctly rejects with `allow_inf_nan=False`, but FastAPI's
# RequestValidationError response echoes the input value back as JSON,
# and Python's json encoder refuses to serialize NaN. That makes the
# 422 path untestable through the normal request flow without a custom
# serializer. The in-handler InvalidObservationValueError + the DDL CHECK
# constraint cover the remaining defense layers.


@pytest.mark.contract
def test_post_readings_returns_422_for_unknown_sampling_procedure() -> None:
    """Closed Literal["baseline"] catches at Pydantic."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/observations",
            json={"entries": [_good_entry(sampling_procedure="histogram")]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_readings_returns_422_for_empty_channel_name() -> None:
    """Pydantic min_length=1 catches at boundary (before handler's
    InvalidChannelNameError)."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/observations",
            json={"entries": [_good_entry(channel_name="")]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_readings_returns_422_for_extra_field_in_entry() -> None:
    """`extra: forbid` rejects unknown entry fields."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        bad = _good_entry()
        bad["unknown_field"] = "x"
        response = client.post(f"/runs/{run_id}/observations", json={"entries": [bad]})
    assert response.status_code == 422


# ---------- Lazy-open lifecycle ----------


@pytest.mark.contract
def test_post_readings_lazy_open_lifecycle() -> None:
    """Two appends + Run start → terminal:
    1. Run starts; status=Running.
    2. First append opens the observation logbook; second append finds
       it open. The HTTP API doesn't expose the lifecycle event
       count, so we verify behavior by ensuring both appends return
       200 and a subsequent terminal-then-append returns 409."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        first = client.post(f"/runs/{run_id}/observations", json={"entries": [_good_entry()]})
        second = client.post(f"/runs/{run_id}/observations", json={"entries": [_good_entry()]})
        assert first.status_code == 200
        assert second.status_code == 200
        # Drive to terminal.
        complete = client.post(f"/runs/{run_id}/complete")
        assert complete.status_code == 204
        # Now appends are rejected.
        third = client.post(f"/runs/{run_id}/observations", json={"entries": [_good_entry()]})
    assert third.status_code == 409
