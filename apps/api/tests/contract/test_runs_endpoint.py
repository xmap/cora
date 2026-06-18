"""Contract tests for `POST /runs`.

The keystone slice — exercises the full upstream chain (Family +
Asset + Method + Practice + Plan + optionally Subject) end-to-end
against the real app boundary.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.run.aggregates.run import (
    RUN_NAME_MAX_LENGTH,
    RunAlreadyExistsError,
)
from cora.run.features.start_run.route import (
    _get_handler as _get_start_run_handler,  # pyright: ignore[reportPrivateUsage]
)
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset


def _setup_full_chain(client: TestClient) -> tuple[str, str]:
    _cap_id = create_capability_via_api(client)
    """Seed Family + Method + Practice + Asset (with capability) +
    Plan + Subject (Mounted) via the public API. Returns (plan_id, subject_id)."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods",
        json={
            "execution_pattern": "Batch",
            "name": "Test Method",
            "capability_id": _cap_id,
            "needed_family_ids": [cap_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={
            "name": "TestAsset",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
    ).json()["asset_id"]
    add_resp = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    assert add_resp.status_code == 204
    plan_id = client.post(
        "/plans",
        json={"name": "32-ID FlyScan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    # Subject in Mounted state.
    subject_id = client.post("/subjects", json={"name": "PorousCeramicSample-A"}).json()[
        "subject_id"
    ]
    mount_asset_id = register_active_asset(client)
    mount_resp = client.post(
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    assert mount_resp.status_code == 204
    return plan_id, subject_id


@pytest.mark.contract
def test_post_runs_returns_201_with_run_id_for_sample_run() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={
                "name": "32-ID FlyScan morning session",
                "plan_id": plan_id,
                "subject_id": subject_id,
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert "run_id" in body
    UUID(body["run_id"])


@pytest.mark.contract
def test_post_runs_returns_201_for_dark_field_run_without_subject() -> None:
    """Calibration / dark-field run: subject_id omitted."""
    with TestClient(create_app()) as client:
        plan_id, _ = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={"name": "Dark field calibration", "plan_id": plan_id},
        )

    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_runs_accepts_explicit_null_subject_id() -> None:
    """subject_id: null is equivalent to omitting it."""
    with TestClient(create_app()) as client:
        plan_id, _ = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={"name": "Dark field", "plan_id": plan_id, "subject_id": None},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_runs_accepts_raid_and_round_trips_into_get_run_response() -> None:
    """7d retrofit: RAiD (ISO 23527) carries verbatim from POST body
    through the RunStarted event and back out via GET /runs/{id}."""
    raid_value = "https://raid.org/10.7935/cora-test-raid"
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        create = client.post(
            "/runs",
            json={
                "name": "32-ID FlyScan with RAiD",
                "plan_id": plan_id,
                "subject_id": subject_id,
                "raid": raid_value,
            },
        )
        assert create.status_code == 201
        run_id = create.json()["run_id"]
        get = client.get(f"/runs/{run_id}")
    assert get.status_code == 200
    assert get.json()["raid"] == raid_value


@pytest.mark.contract
def test_post_runs_accepts_omitted_raid_and_get_returns_null() -> None:
    """Raid is optional (defaults to None) for requests without a raid field."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        create = client.post(
            "/runs",
            json={
                "name": "no-raid run",
                "plan_id": plan_id,
                "subject_id": subject_id,
            },
        )
        assert create.status_code == 201
        run_id = create.json()["run_id"]
        get = client.get(f"/runs/{run_id}")
    assert get.json()["raid"] is None


@pytest.mark.contract
def test_post_runs_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={
                "name": "  32-ID FlyScan  ",
                "plan_id": plan_id,
                "subject_id": subject_id,
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_runs_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs", json={"plan_id": str(uuid4())})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_runs_rejects_missing_plan_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs", json={"name": "X"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_runs_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs", json={"name": "", "plan_id": str(uuid4())})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_runs_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/runs",
            json={"name": "a" * (RUN_NAME_MAX_LENGTH + 1), "plan_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_runs_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={"name": "   ", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_runs_returns_404_when_plan_does_not_exist() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/runs", json={"name": "X", "plan_id": str(uuid4())})
    assert response.status_code == 404


@pytest.mark.contract
def test_post_runs_returns_404_when_subject_does_not_exist() -> None:
    with TestClient(create_app()) as client:
        plan_id, _ = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={
                "name": "X",
                "plan_id": plan_id,
                "subject_id": str(uuid4()),
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_runs_returns_409_when_plan_is_deprecated() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        deprecate = client.post(f"/plans/{plan_id}/deprecate")
        assert deprecate.status_code == 204
        response = client.post(
            "/runs",
            json={"name": "X", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_runs_returns_409_when_subject_in_received_state() -> None:
    """Subject not yet Mounted (still Received from registration)."""
    with TestClient(create_app()) as client:
        plan_id, _ = _setup_full_chain(client)
        # Register a NEW subject without mounting.
        unmounted_id = client.post("/subjects", json={"name": "Unmounted Sample"}).json()[
            "subject_id"
        ]
        response = client.post(
            "/runs",
            json={"name": "X", "plan_id": plan_id, "subject_id": unmounted_id},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_runs_returns_409_when_asset_decommissioned_after_plan_bind() -> None:
    """Drift since Plan-bind: bound Asset got Decommissioned. Run-start re-validates."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        # Build chain manually so we have asset_id handle.
        cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
            "family_id"
        ]
        method_id = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "M",
                "capability_id": _cap_id,
                "needed_family_ids": [cap_id],
            },
        ).json()["method_id"]
        practice_id = client.post(
            "/practices",
            json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
        ).json()["practice_id"]
        asset_id = client.post(
            "/assets",
            json={
                "name": "A",
                "tier": "Unit",
                "parent_id": None,
                "facility_code": "cora",
            },
        ).json()["asset_id"]
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
        plan_id = client.post(
            "/plans",
            json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
        ).json()["plan_id"]
        # Now Activate then Decommission the Asset (simulating drift).
        client.post(f"/assets/{asset_id}/activate")
        client.post(f"/assets/{asset_id}/decommission")
        response = client.post("/runs", json={"name": "X", "plan_id": plan_id})
    assert response.status_code == 409


@pytest.mark.contract
def test_post_runs_returns_409_when_asset_capabilities_drifted_off() -> None:
    """Drift: Asset's capability got removed since Plan-bind. Run-start re-validates."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
            "family_id"
        ]
        method_id = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "M",
                "capability_id": _cap_id,
                "needed_family_ids": [cap_id],
            },
        ).json()["method_id"]
        practice_id = client.post(
            "/practices",
            json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
        ).json()["practice_id"]
        asset_id = client.post(
            "/assets",
            json={
                "name": "A",
                "tier": "Unit",
                "parent_id": None,
                "facility_code": "cora",
            },
        ).json()["asset_id"]
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
        plan_id = client.post(
            "/plans",
            json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
        ).json()["plan_id"]
        # Now remove the capability from the Asset (drift).
        client.post(f"/assets/{asset_id}/remove-family", json={"family_id": cap_id})
        response = client.post("/runs", json={"name": "X", "plan_id": plan_id})
    assert response.status_code == 409
    assert "missing capabilities" in response.json()["detail"]


@pytest.mark.contract
def test_post_runs_returns_409_when_run_already_exists_via_stub() -> None:
    """Defensive guard: RunAlreadyExistsError → 409 via stubbed handler."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise RunAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_start_run_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post("/runs", json={"name": "X", "plan_id": str(uuid4())})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert str(existing_id) in response.json()["detail"]


@pytest.mark.contract
def test_post_runs_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        plan_id, subject_id = _setup_full_chain(client)
        response = client.post(
            "/runs",
            json={
                "name": "a" * RUN_NAME_MAX_LENGTH,
                "plan_id": plan_id,
                "subject_id": subject_id,
            },
        )
    assert response.status_code == 201
