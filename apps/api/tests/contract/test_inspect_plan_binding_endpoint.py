"""Contract tests for `POST /plans/inspect-binding`.

Pinned response shape:
    {
      practice_id, method_id, capability_id,
      method_needed_family_ids[], capability_required_affordances[],
      wired_assets: [{asset_id, asset_name, condition, lifecycle,
                      family_ids[], contributed_affordances[]}],
      missing_family_ids[], missing_affordances[], binding_status
    }

Lists are deterministically sorted (asset_id stringification for
ids, value for affordance strings) so client diffs / cache
validation are stable across replays.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._helpers import create_capability_via_api


def _seed_practice_with_capability(
    client: TestClient, *, affordances: list[str], family_affordances: list[str]
) -> tuple[str, str, str]:
    """Seed full upstream chain. Returns (practice_id, family_id, asset_id)."""
    cap_id = create_capability_via_api(client, required_affordances=affordances)
    family_id = client.post(
        "/families",
        json={"name": "FlyMotion", "affordances": family_affordances},
    ).json()["family_id"]
    method_id = client.post(
        "/methods",
        json={
            "name": "Test Method",
            "capability_id": cap_id,
            "needed_family_ids": [family_id],
        },
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "Test Practice", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={
            "name": "Camera-04",
            "tier": "Unit",
            "parent_id": None,
            "facility_code": "cora",
        },
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
    return practice_id, family_id, asset_id


@pytest.mark.contract
def test_endpoint_returns_satisfied_for_complete_binding() -> None:
    with TestClient(create_app()) as client:
        practice_id, family_id, asset_id = _seed_practice_with_capability(
            client,
            affordances=["Rotatable", "Marking"],
            family_affordances=["Rotatable", "Marking"],
        )
        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": practice_id, "asset_ids": [asset_id]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["practice_id"] == practice_id
    assert body["binding_status"] == "Satisfied"
    assert body["missing_family_ids"] == []
    assert body["missing_affordances"] == []
    assert body["method_needed_family_ids"] == [family_id]
    assert body["capability_required_affordances"] == ["Marking", "Rotatable"]
    assert len(body["wired_assets"]) == 1
    wired = body["wired_assets"][0]
    assert wired["asset_id"] == asset_id
    assert wired["asset_name"] == "Camera-04"
    assert wired["condition"] == "Nominal"
    assert wired["lifecycle"] == "Commissioned"
    assert wired["family_ids"] == [family_id]
    assert wired["contributed_affordances"] == ["Marking", "Rotatable"]


@pytest.mark.contract
def test_endpoint_returns_missing_affordances_when_family_lacks_affordance() -> None:
    with TestClient(create_app()) as client:
        practice_id, _family_id, asset_id = _seed_practice_with_capability(
            client,
            affordances=["Rotatable", "Marking"],
            family_affordances=["Rotatable"],  # Marking missing
        )
        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": practice_id, "asset_ids": [asset_id]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["binding_status"] == "MissingAffordances"
    assert body["missing_family_ids"] == []
    assert body["missing_affordances"] == ["Marking"]
    # In-memory contract harness has no pool -> candidate enumeration
    # skipped; the field is present but empty regardless of
    # missing_affordances content.
    assert body["missing_affordance_candidates"] == []


@pytest.mark.contract
def test_endpoint_returns_missing_families_when_asset_lacks_required_family() -> None:
    """Asset bound but doesn't carry the Family the Method needs ->
    wire-side `missing_family_ids` populated with a UUID; pins serialization."""
    with TestClient(create_app()) as client:
        cap_id = create_capability_via_api(client, required_affordances=["Rotatable"])
        family_id = client.post(
            "/families", json={"name": "FlyMotion", "affordances": ["Rotatable"]}
        ).json()["family_id"]
        method_id = client.post(
            "/methods",
            json={
                "name": "Test Method",
                "capability_id": cap_id,
                "needed_family_ids": [family_id],
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
        # Register an Asset but DO NOT add the required family.
        asset_id = client.post(
            "/assets",
            json={
                "name": "Bare-Asset",
                "tier": "Unit",
                "parent_id": None,
                "facility_code": "cora",
            },
        ).json()["asset_id"]

        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": practice_id, "asset_ids": [asset_id]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["binding_status"] == "MissingFamilies"
    assert body["missing_family_ids"] == [family_id]
    # Affordances dimension is also unsatisfied because the missing
    # Family was the one that would have contributed Rotatable.
    assert body["missing_affordances"] == ["Rotatable"]


@pytest.mark.contract
def test_endpoint_returns_404_for_unknown_practice_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": str(uuid4()), "asset_ids": [str(uuid4())]},
        )

    assert response.status_code == 404


@pytest.mark.contract
def test_endpoint_returns_404_for_unknown_asset_id() -> None:
    with TestClient(create_app()) as client:
        practice_id, _family_id, _asset_id = _seed_practice_with_capability(
            client,
            affordances=["Rotatable"],
            family_affordances=["Rotatable"],
        )
        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": practice_id, "asset_ids": [str(uuid4())]},
        )

    assert response.status_code == 404


@pytest.mark.contract
def test_endpoint_returns_422_for_empty_asset_ids() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/plans/inspect-binding",
            json={"practice_id": str(uuid4()), "asset_ids": []},
        )

    assert response.status_code == 422


@pytest.mark.contract
def test_endpoint_returns_sorted_wired_assets_for_deterministic_response() -> None:
    """Multi-asset preview: wired_assets ordered by asset_id stringification."""
    with TestClient(create_app()) as client:
        practice_id, family_id, _ = _seed_practice_with_capability(
            client,
            affordances=["Rotatable"],
            family_affordances=["Rotatable"],
        )
        extra_asset_ids: list[str] = []
        for i in range(3):
            asset_id = client.post(
                "/assets",
                json={
                    "name": f"Asset{i}",
                    "tier": "Unit",
                    "parent_id": None,
                    "facility_code": "cora",
                },
            ).json()["asset_id"]
            client.post(f"/assets/{asset_id}/add-family", json={"family_id": family_id})
            extra_asset_ids.append(asset_id)

        response = client.post(
            "/plans/inspect-binding",
            json={
                "practice_id": practice_id,
                "asset_ids": list(reversed(extra_asset_ids)),
            },
        )

    assert response.status_code == 200
    body = response.json()
    actual_order = [wa["asset_id"] for wa in body["wired_assets"]]
    assert actual_order == sorted(extra_asset_ids)
