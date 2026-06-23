"""Contract tests for `POST /runs/{run_id}/conduct`.

The external entry to the Reckoner. The default wire-up uses the
in-memory (Simulated) ComputePort, so a conduct succeeds without a real
subprocess. Covers: happy path (run completes, Simulated provenance on
the body), round-trip into GET /runs, failure-in-body (conducting a
non-Running run), and 422 on an empty command.

Same in-process wire-up as the other contract tests: `create_app()` +
TestClient, no DB.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._compute_helpers import setup_run_with_launch_spec
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_run(client: TestClient) -> str:
    """Seed the upstream chain + start a Run. Returns the run_id.

    Mirrors the helper in test_complete_run_endpoint: any Running Run is
    enough for the runtime to conduct (it drives the Run FSM, not the
    Plan), so the recipe here is a generic Batch method, not a compute one.
    """
    capability_id = create_capability_via_api(client)
    family_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "M",
            "capability_id": capability_id,
            "needed_family_ids": [family_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "x"})
    return client.post(
        "/runs",
        json={"name": "recon", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]


@pytest.mark.contract
def test_post_conduct_compute_completes_running_run_with_simulated_provenance() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/conduct",
            json={
                "command": ["tomopy", "recon", "--algorithm", "sirt"],
                "output_uri": "file:///data/recon.h5",
                "parameters": {"num_iter": 200},
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is True
    assert body["status"] == "Succeeded"
    # Default wire-up is the in-memory (Simulated) ComputePort.
    assert body["actuation_kind"] == "Simulated"
    assert body["artifact_uri"] == "file:///data/recon.h5"
    assert body["job_id"] is not None
    assert body["failure"] is None


@pytest.mark.contract
def test_post_conduct_compute_round_trips_run_into_completed() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(
            f"/runs/{run_id}/conduct",
            json={"command": ["noop"], "output_uri": "file:///o.h5"},
        )
        get = client.get(f"/runs/{run_id}")
    assert get.status_code == 200
    assert get.json()["status"] == "Completed"


@pytest.mark.contract
def test_post_conduct_compute_on_non_running_run_returns_200_failure_in_body() -> None:
    """Orchestration semantics: a Run that cannot complete is a 200 with
    succeeded=False + a failure string, not an HTTP error."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        client.post(f"/runs/{run_id}/complete")  # Run is now Completed
        response = client.post(
            f"/runs/{run_id}/conduct",
            json={"command": ["noop"], "output_uri": "file:///o.h5"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["failure"] is not None


@pytest.mark.contract
def test_post_conduct_compute_empty_command_returns_422() -> None:
    """Empty command fails Pydantic min_length before the handler runs."""
    with TestClient(create_app()) as client:
        response = client.post(f"/runs/{uuid4()}/conduct", json={"command": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduct_with_launch_spec_builds_argv_server_side() -> None:
    """A launch_spec Method conducts with NO raw command: the server builds
    the argv from the recipe + the Run's effective_parameters."""
    with TestClient(create_app()) as client:
        run_id = setup_run_with_launch_spec(client)
        response = client.post(
            f"/runs/{run_id}/conduct",
            json={
                "input_uris": ["file:///data/raw.h5"],
                "output_uri": "file:///data/recon.h5",
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["succeeded"] is True
    assert body["status"] == "Succeeded"
    assert body["artifact_uri"] == "file:///data/recon.h5"
    assert body["actuation_kind"] == "Simulated"


@pytest.mark.contract
def test_post_conduct_with_launch_spec_rejects_raw_command_with_422() -> None:
    """A launch_spec Method forbids a caller-supplied raw command."""
    with TestClient(create_app()) as client:
        run_id = setup_run_with_launch_spec(client)
        response = client.post(
            f"/runs/{run_id}/conduct",
            json={"command": ["tomopy", "recon"], "output_uri": "file:///o.h5"},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_conduct_raw_command_returns_422_when_raw_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With CORA_ALLOW_RAW_CONDUCT=false, a no-launch_spec Method cannot
    conduct a raw command."""
    monkeypatch.setenv("CORA_ALLOW_RAW_CONDUCT", "false")
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        response = client.post(
            f"/runs/{run_id}/conduct",
            json={"command": ["noop"], "output_uri": "file:///o.h5"},
        )
    assert response.status_code == 422, response.text
