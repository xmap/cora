"""Contract tests for `POST /assets/{asset_id}/add-family`.

Action endpoint with body `{family_id}`. Mirrors the relocate
endpoint contract (also two-id action endpoint) but for capability
mutation. Pinned: get_asset reflects the new capability after add.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.aggregates.asset.events import AssetRegistered
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.equipment.aggregates.model.events import ModelDefined
from cora.equipment.aggregates.model.events import (
    event_type_name as model_event_type_name,
)
from cora.equipment.aggregates.model.events import to_payload as model_to_payload
from cora.equipment.aggregates.model.state import (
    Manufacturer,
    ManufacturerName,
)
from cora.infrastructure.event_envelope import to_new_event

_SEED_NOW = datetime(2026, 5, 10, 11, 0, 0, tzinfo=UTC)
_SEED_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


def _register_asset(client: TestClient, name: str = "APS-2BM") -> str:
    response = client.post(
        "/assets",
        json={"name": name, "level": "Unit", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201
    asset_id: str = response.json()["asset_id"]
    return asset_id


async def _seed_model_with_declared_families(
    app: FastAPI,
    *,
    model_id: UUID,
    declared_family_ids: frozenset[UUID],
) -> None:
    """Append a `ModelDefined` event with `declared_families` set
    directly via the app's wired kernel.

    The contract test needs a Model carrying specific declared_families
    so the cross-BC subset gate at `add_asset_family` can be exercised.
    Going through `define_model` would require the Families to exist
    in the projection too (cross-BC lookup at the Model handler);
    seeding the event directly bypasses that and is faithful to the
    invariant the Asset handler is meant to enforce.
    """
    deps = app.state.deps
    event = ModelDefined(
        model_id=model_id,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=declared_family_ids,
        occurred_at=_SEED_NOW,
    )
    new_event = to_new_event(
        event_type=model_event_type_name(event),
        payload=model_to_payload(event),
        occurred_at=_SEED_NOW,
        event_id=uuid4(),
        command_name="DefineModel",
        correlation_id=_SEED_CORRELATION_ID,
        principal_id=_SEED_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Model",
        stream_id=model_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_asset_bound_to_model(
    app: FastAPI,
    *,
    asset_id: UUID,
    model_id: UUID,
) -> None:
    """Append an `AssetRegistered` event with `model_id` set directly.

    The current `register_asset` slice does not yet accept a
    `model_id` argument, so contract tests that need to trigger the
    cross-BC subset gate seed the Asset's genesis event with the
    model binding via the event store.
    """
    deps = app.state.deps
    registered = AssetRegistered(
        asset_id=asset_id,
        name="APS-2BM",
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        occurred_at=_SEED_NOW,
        model_id=model_id,
    )
    new_event = to_new_event(
        event_type=asset_event_type_name(registered),
        payload=asset_to_payload(registered),
        occurred_at=_SEED_NOW,
        event_id=uuid4(),
        command_name="RegisterAsset",
        correlation_id=_SEED_CORRELATION_ID,
        principal_id=_SEED_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.contract
def test_post_add_family_returns_204_on_happy_path() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": cap},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_add_family_round_trips_into_get_asset_response() -> None:
    """End-to-end: add_family + get_asset → family appears in
    the response's family_ids list."""
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap1})
        client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap2})
        response = client.get(f"/assets/{asset_id}")

    assert response.status_code == 200
    body = response.json()
    # Sorted by UUID string form (deterministic).
    assert body["family_ids"] == sorted([cap1, cap2])


@pytest.mark.contract
def test_post_add_family_returns_404_when_asset_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/assets/{missing_id}/add-family",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_family_returns_409_when_family_already_present() -> None:
    """Strict-not-idempotent: re-adding raises 409."""
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        first = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap})
        assert first.status_code == 204
        second = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap})
    assert second.status_code == 409
    assert "already" in second.json()["detail"]


@pytest.mark.contract
def test_post_add_family_returns_409_when_asset_is_decommissioned() -> None:
    cap = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        decom = client.post(f"/assets/{asset_id}/decommission")
        assert decom.status_code == 204
        response = client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap})
    assert response.status_code == 409
    assert "Decommissioned" in response.json()["detail"]


@pytest.mark.contract
def test_post_add_family_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets/not-a-uuid/add-family",
            json={"family_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_family_rejects_missing_family_id_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(f"/assets/{asset_id}/add-family", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_family_rejects_non_uuid_family_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_add_family_with_x_principal_id_header_succeeds() -> None:
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": str(uuid4())},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_post_add_family_returns_409_when_asset_model_mismatch() -> None:
    """Cross-BC subset gate: an Asset bound to a Model whose
    `declared_families` are not satisfied by the post-add Asset
    family set raises `AssetModelMismatch`, mapped to 409 via the
    `cannot_transition_cls` tuple in `routes.py`."""
    asset_id = UUID("01900000-0000-7000-8000-0000000e0d01")
    model_id = UUID("01900000-0000-7000-8000-0000000e0d02")
    declared_a = UUID("01900000-0000-7000-8000-0000000e0d03")
    declared_b = UUID("01900000-0000-7000-8000-0000000e0d04")
    family_to_add = declared_a

    app = create_app()
    with TestClient(app) as client:
        # Model declares TWO families; we add only one; subset gate
        # fails because the post-add Asset families is {declared_a}
        # which is not a superset of {declared_a, declared_b}.
        asyncio.run(
            _seed_model_with_declared_families(
                app,
                model_id=model_id,
                declared_family_ids=frozenset({declared_a, declared_b}),
            )
        )
        asyncio.run(_seed_asset_bound_to_model(app, asset_id=asset_id, model_id=model_id))

        response = client.post(
            f"/assets/{asset_id}/add-family",
            json={"family_id": str(family_to_add)},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert str(model_id) in detail
    assert str(asset_id) in detail
