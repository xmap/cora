"""Contract tests for `GET /procedures`.

End-to-end pagination/filter behavior against a real projection
lives in the integration suite. These tests pin the contract: empty
page when no data, status-code shape, parameter validation.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.operation.errors import UnauthorizedError
from cora.operation.features.list_procedures.handler import Handler as ListProceduresHandler
from cora.operation.features.list_procedures.route import (
    _get_handler as _get_list_procedures_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_procedures_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/procedures")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize(
    "status_value",
    ["Defined", "Running", "Held", "Completed", "Aborted", "Truncated"],
)
def test_get_procedures_accepts_each_status(client: TestClient, status_value: str) -> None:
    """All 6 ProcedureStatus values are accepted by the status filter."""
    with client:
        response = client.get(f"/procedures?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_procedures_accepts_kind_filter(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?kind=bakeout")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_procedures_accepts_parent_run_id_filter(client: TestClient) -> None:
    parent_run = uuid4()
    with client:
        response = client.get(f"/procedures?parent_run_id={parent_run}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_procedures_accepts_target_asset_id_filter(client: TestClient) -> None:
    asset = uuid4()
    with client:
        response = client.get(f"/procedures?target_asset_id={asset}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_procedures_accepts_combined_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            f"/procedures?status=Running&kind=bakeout"
            f"&parent_run_id={uuid4()}&target_asset_id={uuid4()}"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_procedures_rejects_unknown_status_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?status=running")  # lowercase is NOT in Literal
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_invalid_parent_run_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?parent_run_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_invalid_target_asset_id_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?target_asset_id=not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_rejects_empty_kind_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/procedures?kind=")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_procedures_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> ListProceduresHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_list_procedures_handler] = _override
    with TestClient(app) as fastapi_client:
        response = fastapi_client.get("/procedures")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
