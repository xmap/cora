# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportFunctionMemberAccess=false, reportAttributeAccessIssue=false

"""Contract tests for `GET /models/{model_id}`.

Mirrors `test_get_family_endpoint.py`. Pinned response shape:
`{model_id, name, manufacturer, part_number, declared_families,
status, version_tag}` where `manufacturer` is the nested
`ManufacturerResponse` and `status` is the StrEnum's string value
(Defined / Versioned / Deprecated).

The Model upstream `define_model` slice enforces a cross-BC precondition:
every entry in `declared_families` must resolve via the Family read
repo's `list_all_family_ids`, which is pool-backed and returns `[]` in the
in-memory TestClient harness. We monkeypatch the symbol imported into
the upstream handler module so the seed `POST /models` call succeeds
and we can exercise the read surface here.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa01")


@pytest.fixture
def accept_family(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `list_all_family_ids` so `_FIXED_FAMILY_ID` always resolves."""

    async def _stub(_pool: object) -> list[UUID]:
        return [_FIXED_FAMILY_ID]

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _stub,
    )
    yield _FIXED_FAMILY_ID


def _define_model(client: TestClient) -> UUID:
    response = client.post(
        "/models",
        json={
            "name": "Aerotech ANT130-L",
            "manufacturer": {"name": "Aerotech"},
            "part_number": "ANT130-L",
            "declared_families": [str(_FIXED_FAMILY_ID)],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["model_id"])


@pytest.mark.contract
def test_get_model_returns_200_with_defined_status_for_new_model(
    accept_family: UUID,
) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        model_id = _define_model(client)
        response = client.get(f"/models/{model_id}")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "model_id": str(model_id),
        "name": "Aerotech ANT130-L",
        "manufacturer": {
            "name": "Aerotech",
            "identifier": None,
            "identifier_type": None,
        },
        "part_number": "ANT130-L",
        "declared_families": [str(_FIXED_FAMILY_ID)],
        "status": "Defined",
        # Null until version_model runs (no initial version_tag supplied).
        "version_tag": None,
    }


@pytest.mark.contract
def test_get_model_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/models/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_model_returns_422_for_malformed_model_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/models/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_model_returns_403_when_authorize_denies(
    accept_family: UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorize-deny surfaces as 403 via the BC's exception handler.
    Patched at the bound-handler tier: the create_app default Authorize
    is AllowAll, so we wrap the wired get_model handler to raise
    UnauthorizedError on entry, the same way the production
    TrustAuthorize would on a Deny."""
    _ = accept_family
    from dataclasses import replace

    from cora.equipment.errors import UnauthorizedError

    with TestClient(create_app()) as client:
        model_id = _define_model(client)

        async def _denying_handler(*_args: object, **_kwargs: object) -> None:
            raise UnauthorizedError("denied for test")

        # Replace the wired get_model handler with one that always
        # denies. The FastAPI dep resolves the handler via
        # request.app.state.equipment, an EquipmentHandlers dataclass.
        original_handlers = client.app.state.equipment
        client.app.state.equipment = replace(
            original_handlers,
            get_model=_denying_handler,
        )
        response = client.get(f"/models/{model_id}")

    assert response.status_code == 403
    body = response.json()
    assert "detail" in body
    assert "denied" in body["detail"].lower()
