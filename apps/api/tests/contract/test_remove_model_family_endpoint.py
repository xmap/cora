"""Contract tests for `DELETE /models/{model_id}/families/{family_id}`.

Targeted-mutation endpoint removing a single Family from the Model's
`declared_families` set. 204 No Content on success. Both ids travel
as path parameters; no request body.

Unlike `add_model_family`, the `remove_model_family` slice performs
NO cross-BC Family lookup; removing a Family that has been deprecated
or deleted from the Family registry still succeeds if it sits in
`declared_families`. The seeding `define_model` call DOES still
resolve `list_family_ids` cross-BC, so we stub that one symbol on
the `define_model` handler module.

The 409-on-Deprecated path appends a `ModelDeprecated` event directly
to the in-memory event store (no `deprecate_model` slice exercised),
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

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fd01")
_OTHER_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fd02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def accept_families(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[UUID]]:
    """Stub `list_family_ids` on the `define_model` handler so the
    seeding call accepts the fixed family-id set. The
    `remove_model_family` handler does NOT perform this lookup."""
    known: list[UUID] = [_FIXED_FAMILY_ID, _OTHER_FAMILY_ID]

    async def _stub(_pool: object) -> list[UUID]:
        return list(known)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_family_ids",
        _stub,
    )
    yield known


def _define_body() -> dict[str, object]:
    return {
        "name": "ANT130-L",
        "manufacturer": {"name": "Aerotech"},
        "part_number": "ANT130-L",
        "declared_families": [str(_FIXED_FAMILY_ID)],
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
def test_delete_remove_model_family_returns_204_on_success(
    accept_families: list[UUID],
) -> None:
    _ = accept_families
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        response = client.delete(f"/models/{model_id}/families/{_FIXED_FAMILY_ID}")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_delete_remove_model_family_returns_404_when_model_does_not_exist(
    accept_families: list[UUID],
) -> None:
    _ = accept_families
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.delete(f"/models/{missing_id}/families/{_FIXED_FAMILY_ID}")
    assert response.status_code == 404


@pytest.mark.contract
def test_delete_remove_model_family_returns_409_when_family_absent(
    accept_families: list[UUID],
) -> None:
    """Strict-not-idempotent: removing a family not in
    declared_families surfaces as 409."""
    _ = accept_families
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        # `_OTHER_FAMILY_ID` was never added to declared_families; the
        # seed only declares `_FIXED_FAMILY_ID`.
        response = client.delete(f"/models/{model_id}/families/{_OTHER_FAMILY_ID}")
    assert response.status_code == 409
    assert "does not declare" in response.json()["detail"]


@pytest.mark.contract
async def test_delete_remove_model_family_returns_409_when_deprecated(
    accept_families: list[UUID],
) -> None:
    """Deprecated Models cannot accept family removals; 409."""
    _ = accept_families
    with TestClient(create_app()) as client:
        model_id = _seed_model(client)
        await _append_deprecated_event(client.app, model_id)  # type: ignore[arg-type]
        response = client.delete(f"/models/{model_id}/families/{_FIXED_FAMILY_ID}")
    assert response.status_code == 409
    assert "Deprecated" in response.json()["detail"]
