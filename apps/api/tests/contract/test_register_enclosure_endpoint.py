"""Contract tests for `POST /enclosures`.

Covers create-style basics (request schema, response shape, status
codes), the Pydantic min/max length on name (-> 422), the FacilityCode
regex on `facility_code` (-> 422), the cross-BC facility-not-found path
(-> 404), the domain-VO validation when whitespace-only slips past
Pydantic (-> 400), and the AlreadyExists defensive guard (-> 409 via
dependency_overrides). The default app seeds a `cora` Facility at
lifespan; the not-found contract uses an unseeded slug.
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
            json={"name": "2-BM Hutch A", "facility_code": "cora"},
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
            json={"name": "  2-BM Hutch A  ", "facility_code": "cora"},
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
            json={"facility_code": "cora"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "", "facility_code": "cora"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={
                "name": "a" * (ENCLOSURE_NAME_MAX_LENGTH + 1),
                "facility_code": "cora",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_rejects_missing_facility_code_with_422() -> None:
    """facility_code is required at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post("/enclosures", json={"name": "2-BM Hutch A"})
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_code",
    ["APS", "_underscore", "with space", "a" * 33, ""],
)
def test_post_enclosures_rejects_malformed_facility_code_with_422(bad_code: str) -> None:
    """FacilityCode regex (lowercase ASCII alphanumeric + dash, 1-32 chars)
    enforced at the Pydantic boundary. Uppercase, underscores, spaces,
    over-length, and empty all reject before reaching the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "facility_code": bad_code},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_enclosures_returns_404_when_facility_code_unseeded() -> None:
    """Cross-BC binding: an unknown but well-formed slug surfaces as
    EnclosureFacilityNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "2-BM Hutch A", "facility_code": "unseeded"},
        )
    assert response.status_code == 404
    assert "unseeded" in response.json()["detail"]


@pytest.mark.contract
def test_post_enclosures_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the domain VO."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/enclosures",
            json={"name": "   ", "facility_code": "cora"},
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
            json={"name": "2-BM Hutch A", "facility_code": "cora"},
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
            json={"name": "2-BM Hutch A", "facility_code": "cora"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
