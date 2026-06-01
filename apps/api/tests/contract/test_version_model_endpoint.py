"""Contract tests for `POST /models/{model_id}/versions`.

Action endpoint carrying a full replacement body (name, manufacturer,
part_number, declared_families, version_tag). Multi-source guard
(Defined | Versioned -> Versioned).

In-memory contract harness has no Postgres pool, so the cross-BC
`list_family_ids` lookup performed by `define_model` returns `[]` and
every model-seeding call would fail. We stub the symbol to a
fixed accept-all set so we can seed a Model via `POST /models` and
exercise `POST /models/{model_id}/versions` end-to-end.

The 409-on-Deprecated path appends a `ModelDeprecated` event directly
to the in-memory event store (no `deprecate_model` slice exists yet),
then exercises the route and expects 409.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.model import (
    ModelDeprecated,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_OTHER_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def accept_family(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `list_family_ids` so the seeding `define_model` succeeds."""

    async def _stub(_pool: object) -> list[UUID]:
        return [_FIXED_FAMILY_ID, _OTHER_FAMILY_ID]

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_family_ids",
        _stub,
    )
    yield _FIXED_FAMILY_ID


def _define_body(*, name: str = "ANT130-L") -> dict[str, object]:
    return {
        "name": name,
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L",
        "declared_families": [str(_FIXED_FAMILY_ID)],
    }


def _version_body(
    *,
    name: str = "ANT130-L rev-B",
    part_number: str = "ANT130-L-B",
    version_tag: str = "v2",
    declared_families: list[str] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "manufacturer": {"name": "Aerotech"},
        "part_number": part_number,
        "declared_families": declared_families
        if declared_families is not None
        else [str(_FIXED_FAMILY_ID), str(_OTHER_FAMILY_ID)],
        "version_tag": version_tag,
    }


def _seed_model(client: TestClient) -> UUID:
    response = client.post("/models", json=_define_body())
    assert response.status_code == 201
    return UUID(response.json()["model_id"])


async def _append_deprecated_event(app: FastAPI, model_id: UUID) -> None:
    deps = app.state.deps
    deprecated = ModelDeprecated(
        model_id=model_id,
        reason="superseded",
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(deprecated),
        payload=to_payload(deprecated),
        occurred_at=deprecated.occurred_at,
        event_id=uuid4(),
        command_name="DeprecateModel",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    _, current_version = await deps.event_store.load("Model", model_id)
    await deps.event_store.append(
        stream_type="Model",
        stream_id=model_id,
        expected_version=current_version,
        events=[new_event],
    )


@pytest.mark.contract
def test_post_version_model_returns_204_from_defined_state(accept_family: UUID) -> None:
    """First revision (Defined -> Versioned)."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.post(
            f"/models/{model_id}/versions",
            json=_version_body(),
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_version_model_returns_204_from_versioned_state(accept_family: UUID) -> None:
    """Subsequent revision (Versioned -> Versioned)."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        first = client.post(f"/models/{model_id}/versions", json=_version_body(version_tag="v1"))
        assert first.status_code == 204
        second = client.post(f"/models/{model_id}/versions", json=_version_body(version_tag="v2"))
    assert second.status_code == 204


@pytest.mark.contract
def test_post_version_model_returns_404_when_model_does_not_exist(accept_family: UUID) -> None:
    _ = accept_family
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(f"/models/{missing_id}/versions", json=_version_body())
    assert response.status_code == 404


@pytest.mark.contract
async def test_post_version_model_returns_409_when_deprecated(accept_family: UUID) -> None:
    """Deprecated Models cannot be re-versioned."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        await _append_deprecated_event(client.app, model_id)  # type: ignore[arg-type]
        response = client.post(f"/models/{model_id}/versions", json=_version_body())
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]


@pytest.mark.contract
def test_post_version_model_missing_required_field_returns_422(accept_family: UUID) -> None:
    """Pydantic schema validation: missing `version_tag`."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        body = _version_body()
        del body["version_tag"]
        response = client.post(f"/models/{model_id}/versions", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_model_empty_declared_families_returns_422(accept_family: UUID) -> None:
    """Pydantic `min_length=1` on `declared_families`."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        body = _version_body(declared_families=[])
        response = client.post(f"/models/{model_id}/versions", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_model_whitespace_only_name_returns_400(accept_family: UUID) -> None:
    """Domain `InvalidModelNameError` after Pydantic min_length=1 passes."""
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.post(
            f"/models/{model_id}/versions",
            json=_version_body(name="   "),
        )
    assert response.status_code == 400
    assert "name" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_version_model_rejects_invalid_path_uuid_with_422(accept_family: UUID) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        response = client.post("/models/not-a-uuid/versions", json=_version_body())
    assert response.status_code == 422
