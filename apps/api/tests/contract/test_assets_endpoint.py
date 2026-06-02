"""Contract tests for `POST /assets`.

Covers the create-style basics (request schema, response schema,
status codes), the StrEnum level-validation at the API boundary
(unknown levels → 422), the hierarchy rule (Enterprise null-parent,
others required → 400), and the AlreadyExists defensive guard
(→ 409 via dependency_overrides).
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
def test_post_assets_returns_201_with_asset_id_for_enterprise_root() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "ANL", "level": "Enterprise", "parent_id": None},
        )

    assert response.status_code == 201
    body = response.json()
    assert "asset_id" in body
    UUID(body["asset_id"])  # parses


@pytest.mark.contract
def test_post_assets_returns_201_for_site_with_parent() -> None:
    with TestClient(create_app()) as client:
        parent_id = str(uuid4())
        response = client.post(
            "/assets",
            json={"name": "APS", "level": "Site", "parent_id": parent_id},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "  APS-2BM  ", "level": "Unit", "parent_id": str(uuid4())},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_rejects_missing_required_fields_with_422() -> None:
    """Pydantic catches missing name/level/parent_id at the body
    layer; the decider never sees an incomplete command."""
    with TestClient(create_app()) as client:
        response = client.post("/assets", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "", "level": "Site", "parent_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={
                "name": "a" * 201,
                "level": "Site",
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
                "level": "Site",
                "parent_id": str(uuid4()),
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_rejects_unknown_level_with_422() -> None:
    """Pydantic StrEnum validation rejects unknown level strings before
    the decider runs. Pinned because the level vocabulary is closed
    (Enterprise/Site/Area/Unit/Component/Device per BC map); typos and
    legacy values must surface at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "X", "level": "Beamline", "parent_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "   ", "level": "Site", "parent_id": str(uuid4())},
        )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_assets_rejects_enterprise_with_non_null_parent_with_400() -> None:
    """Hierarchy rule: Enterprise must have null parent_id. Decider
    raises InvalidAssetParentError → routed to 400 via the shared
    validation handler."""
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "ANL", "level": "Enterprise", "parent_id": parent_id},
        )
    assert response.status_code == 400
    body = response.json()
    assert "Enterprise" in body["detail"]
    assert parent_id in body["detail"]


@pytest.mark.contract
@pytest.mark.parametrize(
    "level",
    ["Site", "Area", "Unit", "Component", "Device"],
)
def test_post_assets_rejects_non_enterprise_with_null_parent_with_400(
    level: str,
) -> None:
    """All non-Enterprise levels MUST have a parent. Pinned per-level
    so a future relaxation has to flip every parametrized case
    deliberately."""
    with TestClient(create_app()) as client:
        response = client.post("/assets", json={"name": "X", "level": level, "parent_id": None})
    assert response.status_code == 400
    body = response.json()
    assert level in body["detail"]


@pytest.mark.contract
def test_post_assets_rejects_malformed_parent_uuid_with_422() -> None:
    """Pydantic UUID parsing on the body field."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/assets",
            json={"name": "X", "level": "Site", "parent_id": "not-a-uuid"},
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
                json={"name": "X", "level": "Site", "parent_id": str(uuid4())},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]
