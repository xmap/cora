"""Contract tests for `POST /models/{model_id}/deprecation`.

Action endpoint carrying a `reason` body. Multi-source guard
(Defined | Versioned -> Deprecated). Strict-not-idempotent.

In-memory contract harness has no Postgres pool, so the cross-BC
`list_all_family_ids` lookup performed by `define_model` returns `[]` and
every model-seeding call would fail. We stub the symbol to a fixed
accept-all set so we can seed a Model via `POST /models` and exercise
`POST /models/{model_id}/deprecation` end-to-end.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fad1")
_REASON = "Superseded"


@pytest.fixture
def accept_family(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `list_all_family_ids` so the seeding `define_model` succeeds."""

    async def _stub(_pool: object) -> list[UUID]:
        return [_FIXED_FAMILY_ID]

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _stub,
    )
    yield _FIXED_FAMILY_ID


def _define_body(*, name: str = "ANT130-L") -> dict[str, object]:
    return {
        "name": name,
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L",
        "declared_family_ids": [str(_FIXED_FAMILY_ID)],
    }


def _deprecate_body(*, reason: str = _REASON) -> dict[str, object]:
    return {"reason": reason}


def _seed_model(client: TestClient) -> UUID:
    response = client.post("/models", json=_define_body())
    assert response.status_code == 201
    return UUID(response.json()["model_id"])


@pytest.mark.contract
def test_post_deprecate_model_returns_204_on_success(accept_family: UUID) -> None:
    """Defined -> Deprecated."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.post(
            f"/models/{model_id}/deprecation",
            json=_deprecate_body(),
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_deprecate_model_missing_reason_returns_422(accept_family: UUID) -> None:
    """Pydantic schema validation: `reason` is required."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.post(f"/models/{model_id}/deprecation", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_model_unknown_reason_returns_422(accept_family: UUID) -> None:
    """`reason` is a closed enum, so vendor prose is rejected at the schema."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.post(
            f"/models/{model_id}/deprecation",
            json=_deprecate_body(reason="vendor EOL 2026"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_deprecate_model_returns_404_when_model_does_not_exist(
    accept_family: UUID,
) -> None:
    _ = accept_family
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/models/{missing_id}/deprecation",
            json=_deprecate_body(),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_deprecate_model_returns_409_when_already_deprecated(
    accept_family: UUID,
) -> None:
    """Strict-not-idempotent: re-deprecating raises 409."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        first = client.post(
            f"/models/{model_id}/deprecation",
            json=_deprecate_body(),
        )
        assert first.status_code == 204
        second = client.post(
            f"/models/{model_id}/deprecation",
            json=_deprecate_body(),
        )
    assert second.status_code == 409
    body = second.json()
    assert "Defined" in body["detail"]
    assert "Versioned" in body["detail"]


@pytest.mark.contract
def test_post_deprecate_model_rejects_invalid_path_uuid_with_422(
    accept_family: UUID,
) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        response = client.post(
            "/models/not-a-uuid/deprecation",
            json=_deprecate_body(),
        )
    assert response.status_code == 422
