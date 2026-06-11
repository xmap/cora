"""Contract tests for `POST /assets/{asset_id}/partition-rule`.

Action endpoint with body `{partition_rule}`. PartitionRule is a
typed-VO discriminated union (Affine, Aggregation, LookupTable,
CompositePartition, SolverReference) carried as a Pydantic shape at
the route boundary; null clears the rule. Only Assets of Family
PseudoAxis accept the rule.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.update_asset_partition_rule.route import (
    _get_handler as _get_update_asset_partition_rule_handler,  # pyright: ignore[reportPrivateUsage]
)


def _define_family(client: TestClient, *, name: str = "PseudoAxis") -> UUID:
    response = client.post("/families", json={"name": name, "affordances": []})
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _register_asset(client: TestClient) -> UUID:
    response = client.post(
        "/assets",
        json={"name": "VirtualAxis-X", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


def _add_family(client: TestClient, asset_id: UUID, family_id: UUID) -> None:
    response = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert response.status_code == 204, response.text


def _decommission(client: TestClient, asset_id: UUID) -> None:
    response = client.post(f"/assets/{asset_id}/decommission")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_partition_rule_returns_200_for_affine_body() -> None:
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client)
        _add_family(client, asset_id, family_id)

        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={
                "partition_rule": {
                    "kind": "Affine",
                    "gain": 2.0,
                    "offset": 0.5,
                    "unit_in": "mm",
                    "unit_out": "deg",
                },
            },
        )
    assert response.status_code == 200, response.text
    assert response.json() == {}


@pytest.mark.contract
def test_post_partition_rule_returns_200_for_null_clear() -> None:
    """Null partition_rule clears the existing rule."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client)
        _add_family(client, asset_id, family_id)

        seed = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
        assert seed.status_code == 200, seed.text

        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={"partition_rule": None},
        )
    assert response.status_code == 200, response.text
    assert response.json() == {}


@pytest.mark.contract
def test_post_partition_rule_returns_400_for_nan_gain() -> None:
    """Affine.__post_init__ rejects NaN gain with InvalidPartitionRuleError.

    `NaN` is sent as a raw JSON literal (Python's stdlib `json.loads`
    accepts it) because the httpx JSON encoder refuses non-finite floats.
    """
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client)
        _add_family(client, asset_id, family_id)

        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            content=b'{"partition_rule": {"kind": "Affine", "gain": NaN, "offset": 0.0}}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400, response.text
    assert "Invalid PartitionRule" in response.json()["detail"]


@pytest.mark.contract
def test_post_partition_rule_returns_404_for_missing_asset() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/partition-rule",
            json={
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_partition_rule_returns_409_when_asset_is_decommissioned() -> None:
    """Decommissioned PseudoAxis Asset rejects partition rule updates."""
    with TestClient(create_app()) as client:
        family_id = _define_family(client)
        asset_id = _register_asset(client)
        _add_family(client, asset_id, family_id)
        _decommission(client, asset_id)

        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_partition_rule_returns_422_for_unknown_kind() -> None:
    """Discriminator value not in the closed enum trips Pydantic 422."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={"partition_rule": {"kind": "NotARealKind"}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_partition_rule_returns_422_for_missing_required_field() -> None:
    """SolverReference requires solver_id; omitting it trips Pydantic 422."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/partition-rule",
            json={
                "partition_rule": {
                    "kind": "SolverReference",
                    "solver_version": "1.0",
                },
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_partition_rule_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/partition-rule",
            json={
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_partition_rule_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_update_asset_partition_rule_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/assets/{uuid4()}/partition-rule",
            json={
                "partition_rule": {"kind": "Affine", "gain": 1.0, "offset": 0.0},
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
