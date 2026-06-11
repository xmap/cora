"""Contract tests for `PATCH /assets/{asset_id}/settings`.

Action endpoint with body `{settings_patch}`. RFC 7396
JSON Merge Patch semantics; cross-Family schema-union
validation at write time.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _define_family(client: TestClient, *, name: str = "Tomography") -> UUID:
    response = client.post("/families", json={"name": name, "affordances": []})
    assert response.status_code == 201, response.text
    return UUID(response.json()["family_id"])


def _set_capability_schema(client: TestClient, family_id: UUID, schema: dict[str, Any]) -> None:
    response = client.post(
        f"/families/{family_id}/settings-schema",
        json={"settings_schema": schema},
    )
    assert response.status_code == 204, response.text


def _register_asset(client: TestClient) -> UUID:
    response = client.post(
        "/assets",
        json={"name": "Detector-X", "tier": "Device", "parent_id": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


def _add_family(client: TestClient, asset_id: UUID, family_id: UUID) -> None:
    response = client.post(
        f"/assets/{asset_id}/add-family",
        json={"family_id": str(family_id)},
    )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_patch_settings_returns_204_on_happy_path() -> None:
    """End-to-end: define Family with schema, register Asset,
    add Family, PATCH settings, get back 204."""
    with TestClient(create_app()) as client:
        cap_id = _define_family(client)
        _set_capability_schema(
            client,
            cap_id,
            {
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {
                        "type": "number",
                        "minimum": 5,
                        "unit": {"system": "udunits", "code": "keV"},
                    }
                },
            },
        )
        asset_id = _register_asset(client)
        _add_family(client, asset_id, cap_id)

        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"energy": 30}},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_patch_settings_returns_400_for_constraint_violation() -> None:
    """Value below the schema's `minimum` rejects with 400."""
    with TestClient(create_app()) as client:
        cap_id = _define_family(client)
        _set_capability_schema(
            client,
            cap_id,
            {
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {
                        "type": "number",
                        "minimum": 10,
                        "unit": {"system": "udunits", "code": "keV"},
                    }
                },
            },
        )
        asset_id = _register_asset(client)
        _add_family(client, asset_id, cap_id)

        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"energy": 1}},
        )
    assert response.status_code == 400
    assert "Invalid Asset settings" in response.json()["detail"]


@pytest.mark.contract
def test_patch_settings_returns_400_for_orphan_key_in_strict_mode() -> None:
    """Family has a schema; an unknown key rejects."""
    with TestClient(create_app()) as client:
        cap_id = _define_family(client)
        _set_capability_schema(
            client,
            cap_id,
            {
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}
                },
            },
        )
        asset_id = _register_asset(client)
        _add_family(client, asset_id, cap_id)

        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"unknown_key": "x"}},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_patch_settings_returns_404_for_missing_asset() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/assets/{missing_id}/settings",
            json={"settings_patch": {"x": 1}},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_patch_settings_returns_400_when_asset_has_no_capabilities() -> None:
    """Asset with no Capabilities cannot have settings (no schema source)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"x": 1}},
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_patch_settings_returns_204_for_empty_patch_no_op() -> None:
    """Empty patch is a no-op (decider returns []) — still 204."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {}},
        )
    assert response.status_code == 204


@pytest.mark.contract
def test_patch_settings_supports_merge_via_two_calls() -> None:
    """Two PATCHes accumulate via merge: first sets one key, second
    sets another, both are present in the get_asset response."""
    with TestClient(create_app()) as client:
        cap_id = _define_family(client)
        _set_capability_schema(
            client,
            cap_id,
            {
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}},
                    "filter": {"type": "string"},
                },
            },
        )
        asset_id = _register_asset(client)
        _add_family(client, asset_id, cap_id)

        first = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"energy": 30}},
        )
        assert first.status_code == 204
        second = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"filter": "Cu"}},
        )
        assert second.status_code == 204

        # Assert via get_asset that both keys are present.
        get_response = client.get(f"/assets/{asset_id}")
        body = get_response.json()
        assert body["settings"] == {"energy": 30, "filter": "Cu"}


@pytest.mark.contract
def test_patch_settings_null_deletes_key() -> None:
    """RFC 7396 null-delete: PATCH with `null` value removes the key."""
    with TestClient(create_app()) as client:
        cap_id = _define_family(client)
        _set_capability_schema(
            client,
            cap_id,
            {
                "$schema": _DRAFT,
                "type": "object",
                "properties": {
                    "energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}},
                    "filter": {"type": "string"},
                },
            },
        )
        asset_id = _register_asset(client)
        _add_family(client, asset_id, cap_id)

        # Set both keys.
        client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"energy": 30, "filter": "Cu"}},
        )
        # Null out filter.
        delete_response = client.patch(
            f"/assets/{asset_id}/settings",
            json={"settings_patch": {"filter": None}},
        )
        assert delete_response.status_code == 204

        get_response = client.get(f"/assets/{asset_id}")
        assert get_response.json()["settings"] == {"energy": 30}


@pytest.mark.contract
def test_patch_settings_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.patch(
            "/assets/not-a-uuid/settings",
            json={"settings_patch": {"x": 1}},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_patch_settings_rejects_missing_settings_patch_field_with_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.patch(
            f"/assets/{asset_id}/settings",
            json={},  # missing settings_patch field
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_asset_response_includes_settings_and_condition_fields() -> None:
    """5g-c side-effect: get_asset response gains both `settings` and
    `condition` (5g-b had been missing on the response model)."""
    with TestClient(create_app()) as client:
        asset_id = _register_asset(client)
        response = client.get(f"/assets/{asset_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["settings"] == {}
    assert body["condition"] == "Nominal"
