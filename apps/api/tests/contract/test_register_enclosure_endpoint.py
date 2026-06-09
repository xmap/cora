"""Contract tests for `POST /enclosures`.

Covers create-style basics (request schema, response shape, status
codes), the Pydantic min/max length on name (-> 422), the domain-VO
validation when whitespace-only slips past Pydantic (-> 400), and the
AlreadyExists defensive guard (-> 409 via dependency_overrides).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.enclosure.aggregates.enclosure import (
    ENCLOSURE_NAME_MAX_LENGTH,
    EnclosureAlreadyExistsError,
    EnclosureId,
)
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features.register_enclosure.route import (
    _get_handler as _get_register_enclosure_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_enclosures_returns_201_with_enclosure_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 201
    body = response.json()
    assert "enclosure_id" in body
    UUID(body["enclosure_id"])


@pytest.mark.contract
def test_post_enclosures_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "  2-BM Hutch A  ", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_enclosures_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/enclosures", json={"name": "2-BM Hutch A"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={
                "name": "a" * (ENCLOSURE_NAME_MAX_LENGTH + 1),
                "containing_asset_id": str(uuid4()),
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_non_uuid_containing_asset_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "containing_asset_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the domain VO."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "   ", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 400
    assert "Enclosure name" in response.json()["detail"]


@pytest.mark.contract
def test_post_enclosures_returns_409_when_handler_raises_already_exists() -> None:
    """Defensive guard: stream-already-has-events maps to 409."""
    app = create_app()
    existing_id = EnclosureId(uuid4())

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise EnclosureAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_enclosure_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_enclosures_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_enclosure_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "containing_asset_id": str(uuid4())},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
