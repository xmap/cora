"""Contract tests for `POST /plans`.

Mirror of `test_practices_endpoint.py` shape with the additional
cross-aggregate validation paths (gate-review Q5): the Plan handler
pre-loads Practice + Method + each Asset before reaching the pure
decider. NotFound paths surface as 404; state-of-existing-thing
violations (Deprecated upstream, Decommissioned Asset, capability
superset) surface as 409.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.recipe.aggregates.plan import (
    PLAN_NAME_MAX_LENGTH,
    PlanAlreadyExistsError,
    PlanFamiliesNotSatisfiedError,
)
from cora.recipe.features.define_plan.route import (
    _get_handler as _get_define_plan_handler,  # pyright: ignore[reportPrivateUsage]
)
from tests.contract._helpers import create_capability_via_api


def _setup_chain(client: TestClient) -> tuple[str, str, str]:
    _cap_id = create_capability_via_api(client)
    """Seed Family + Method + Practice + Asset(with capability)
    via the public API. Returns (practice_id, asset_id, family_id)."""
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
        json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    add_resp = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    assert add_resp.status_code == 204
    return practice_id, asset_id, cap_id


@pytest.mark.contract
def test_post_plans_returns_201_with_plan_id() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        response = client.post(
            "/plans",
            json={
                "name": "32-ID FlyScan Plan",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert "plan_id" in body
    UUID(body["plan_id"])


@pytest.mark.contract
def test_post_plans_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        response = client.post(
            "/plans",
            json={
                "name": "  32-ID FlyScan  ",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_plans_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans",
            json={"practice_id": str(uuid4()), "asset_ids": [str(uuid4())]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_plans_rejects_missing_practice_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/plans", json={"name": "X", "asset_ids": [str(uuid4())]})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_plans_rejects_empty_asset_ids_with_422() -> None:
    """Pydantic min_length=1 catches the empty set at the API boundary
    before the decider's defensive check."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans",
            json={"name": "X", "practice_id": str(uuid4()), "asset_ids": []},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_plans_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans",
            json={"name": "", "practice_id": str(uuid4()), "asset_ids": [str(uuid4())]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_plans_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans",
            json={
                "name": "a" * (PLAN_NAME_MAX_LENGTH + 1),
                "practice_id": str(uuid4()),
                "asset_ids": [str(uuid4())],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_plans_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        response = client.post(
            "/plans",
            json={
                "name": "   ",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_plans_returns_404_when_practice_does_not_exist() -> None:
    """Cross-aggregate pre-load (gate-review Q5): Practice not found
    surfaces as 404 via Recipe routes' PracticeNotFoundError handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": str(uuid4()),
                "asset_ids": [str(uuid4())],
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_plans_returns_404_when_referenced_method_does_not_exist() -> None:
    """Practice exists but its method_id is dangling — handler-side
    load_method returns None → MethodNotFoundError → 404."""
    with TestClient(create_app()) as client:
        # Create Practice with a bogus method_id (eventual-consistency:
        # Practice's decider doesn't verify method existence).
        bogus_method_id = str(uuid4())
        practice_id = client.post(
            "/practices",
            json={
                "name": "Practice with dangling method",
                "method_id": bogus_method_id,
                "site_id": str(uuid4()),
            },
        ).json()["practice_id"]
        asset_id = client.post(
            "/assets",
            json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        ).json()["asset_id"]
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_plans_returns_404_when_any_bound_asset_does_not_exist() -> None:
    """One bound asset_id missing → AssetNotFoundError → 404
    (Equipment-BC error globally registered as 404)."""
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        missing_asset_id = str(uuid4())
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id, missing_asset_id],
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_plans_returns_409_when_practice_is_deprecated() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        deprecate_resp = client.post(f"/practices/{practice_id}/deprecate")
        assert deprecate_resp.status_code == 204
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_plans_returns_409_when_method_is_deprecated() -> None:
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
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
            json={
                "name": "Test Practice",
                "method_id": method_id,
                "site_id": str(uuid4()),
            },
        ).json()["practice_id"]
        asset_id = client.post(
            "/assets",
            json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        ).json()["asset_id"]
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
        # Deprecate Method AFTER Practice has been bound to it.
        deprecate_resp = client.post(f"/methods/{method_id}/deprecate")
        assert deprecate_resp.status_code == 204
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_plans_returns_409_when_asset_is_decommissioned() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        # Activate then Decommission the Asset.
        activate_resp = client.post(f"/assets/{asset_id}/activate")
        assert activate_resp.status_code == 204
        dc_resp = client.post(f"/assets/{asset_id}/decommission")
        assert dc_resp.status_code == 204
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_plans_returns_409_when_capabilities_not_satisfied() -> None:
    """Method needs capability X but bound Asset has only Y."""
    with TestClient(create_app()) as client:
        _cap_id = create_capability_via_api(client)
        needed_cap = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
            "family_id"
        ]
        different_cap = client.post(
            "/families", json={"name": "OtherCap", "affordances": []}
        ).json()["family_id"]
        method_id = client.post(
            "/methods",
            json={
                "execution_pattern": "Batch",
                "name": "Test Method",
                "capability_id": _cap_id,
                "needed_family_ids": [needed_cap],
            },
        ).json()["method_id"]
        practice_id = client.post(
            "/practices",
            json={
                "name": "Test Practice",
                "method_id": method_id,
                "site_id": str(uuid4()),
            },
        ).json()["practice_id"]
        asset_id = client.post(
            "/assets",
            json={"name": "TestAsset", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        ).json()["asset_id"]
        # Asset has different capability than Method needs.
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": different_cap})
        response = client.post(
            "/plans",
            json={
                "name": "X",
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_plans_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        practice_id, asset_id, _ = _setup_chain(client)
        response = client.post(
            "/plans",
            json={
                "name": "a" * PLAN_NAME_MAX_LENGTH,
                "practice_id": practice_id,
                "asset_ids": [asset_id],
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_plans_returns_409_when_plan_already_exists() -> None:
    """Defensive guard: PlanAlreadyExistsError -> 409. Stub the
    handler so the route's exception handler is verified end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise PlanAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_plan_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/plans",
                json={
                    "name": "X",
                    "practice_id": str(uuid4()),
                    "asset_ids": [str(uuid4())],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]


@pytest.mark.contract
def test_post_plans_returns_409_when_capabilities_not_satisfied_via_stub() -> None:
    """Stub-based pin that PlanFamiliesNotSatisfiedError → 409
    via the cannot_transition handler tuple."""
    missing = frozenset({uuid4()})

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise PlanFamiliesNotSatisfiedError(missing)

    app = create_app()
    app.dependency_overrides[_get_define_plan_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/plans",
                json={
                    "name": "X",
                    "practice_id": str(uuid4()),
                    "asset_ids": [str(uuid4())],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
