"""Contract tests for `POST /assets`.

Covers the create-style basics (request schema, response schema,
status codes), the StrEnum tier-validation at the API boundary
(unknown tiers → 422), the anchoring XOR rule (exactly one of
{parent_id, facility_code}: a root binds facility_code with null
parent_id, a non-root carries parent_id and no facility_code → 400),
and the AlreadyExists defensive guard (→ 409 via dependency_overrides).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.asset import (
    ASSET_NAME_MAX_LENGTH,
    AssetAlreadyExistsError,
)
from cora.equipment.features.register_asset.route import (
    _get_handler as _get_register_asset_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_assets_returns_201_with_asset_id_for_facility_rooted_root() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "ANL", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
        )

    assert response.status_code == 201
    body = response.json()
    assert "asset_id" in body
    UUID(body["asset_id"])  # parses


@pytest.mark.contract
def test_post_assets_returns_201_for_non_root_with_parent() -> None:
    with TestClient(create_app()) as client:
        parent_id = str(uuid4())
        response = client.post(
            "/assets",
            json={"name": "APS", "tier": "Component", "parent_id": parent_id},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "  APS-2BM  ", "tier": "Unit", "parent_id": str(uuid4())},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_rejects_missing_required_fields_with_422() -> None:
    """Pydantic catches missing name/tier/parent_id at the body
    layer; the decider never sees an incomplete command."""
    with TestClient(create_app()) as client:
        response = client.post("/assets", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "", "tier": "Unit", "parent_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "a" * 201,
                "tier": "Unit",
                "parent_id": str(uuid4()),
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "a" * ASSET_NAME_MAX_LENGTH,
                "tier": "Unit",
                "parent_id": str(uuid4()),
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_rejects_unknown_tier_with_422() -> None:
    """Pydantic StrEnum validation rejects unknown tier strings before
    the decider runs. Pinned because the tier vocabulary is closed
    (Unit/Component/Device per AssetTier); typos and legacy values
    (Enterprise/Site/Area) must surface at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "X", "tier": "Beamline", "parent_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize("legacy_tier", ["Enterprise", "Site", "Area"])
def test_post_assets_rejects_legacy_tier_values_with_422(legacy_tier: str) -> None:
    """The deleted AssetLevel values (Enterprise/Site/Area) are no
    longer part of the closed AssetTier vocabulary and must be
    rejected at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "X", "tier": legacy_tier, "parent_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "   ", "tier": "Unit", "parent_id": str(uuid4())},
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_assets_rejects_root_that_also_binds_parent_with_400() -> None:
    """Anchoring XOR rule: a non-root Asset (with parent_id) must NOT
    also bind facility_code. Decider raises InvalidAssetParentError →
    routed to 400 via the shared validation handler."""
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "ANL",
                "tier": "Unit",
                "parent_id": parent_id,
                "facility_code": "cora",
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert "facility_code" in body["detail"]
    assert parent_id in body["detail"]


@pytest.mark.contract
def test_post_assets_rejects_root_without_facility_code_with_400() -> None:
    """A root Asset (parent_id=None) MUST bind a facility_code.
    Omitting both anchors violates the XOR rule. Pinned so a future
    relaxation has to flip this case deliberately."""
    with TestClient(create_app()) as client:
        response = client.post("/assets", json={"name": "X", "tier": "Unit", "parent_id": None})
    assert response.status_code == 400
    body = response.json()
    assert "facility_code" in body["detail"]


@pytest.mark.contract
def test_post_assets_rejects_malformed_parent_uuid_with_422() -> None:
    """Pydantic UUID parsing on the body field."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "X", "tier": "Unit", "parent_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_returns_409_when_asset_already_exists() -> None:
    """Defensive guard: AssetAlreadyExistsError -> 409. Same pattern
    as ActorAlreadyExistsError / SubjectAlreadyExistsError /
    FamilyAlreadyExistsError. Test overrides the slice handler
    with a stub that raises directly so the route's exception
    handler is verified end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise AssetAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_register_asset_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/assets",
                json={"name": "X", "tier": "Unit", "parent_id": str(uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
