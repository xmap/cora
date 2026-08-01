"""Contract tests for `POST /clearance-templates/{template_id}/withdraw`.

Pins the no-body 204 transition contract, the UnauthorizedError -> 403
mapping, the ClearanceTemplateNotFoundError -> 404 mapping (no state in
the store for the given id), the ClearanceTemplateCannotWithdrawError
-> 409 mapping (template exists but is already in the terminal Withdrawn
status), and the malformed-path-UUID -> 422 Pydantic boundary rejection.
Handler swaps go through the lifespan-built `app.state.safety` aggregate
via `dataclasses.replace`, mirroring the established sibling pattern.
"""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCannotWithdrawError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
)
from cora.safety.errors import UnauthorizedError


@pytest.mark.contract
def test_post_withdraw_clearance_template_returns_204_with_no_body() -> None:
    async def _stub_handler(*_args: object, **_kwargs: object) -> None:
        return None

    template_id = uuid4()
    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_stub_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 204, response.text
    assert response.content == b""


@pytest.mark.contract
def test_post_withdraw_clearance_template_returns_403_when_authorize_denies() -> None:
    async def _denying_handler(*_args: object, **_kwargs: object) -> None:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_denying_handler,
        )
        response = client.post(
            f"/clearance-templates/{uuid4()}/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_withdraw_clearance_template_returns_404_when_template_unknown() -> None:
    template_id = uuid4()

    async def _missing_handler(*_args: object, **_kwargs: object) -> None:
        raise ClearanceTemplateNotFoundError(template_id)

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_missing_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_withdraw_clearance_template_returns_409_when_already_withdrawn() -> None:
    template_id = uuid4()

    async def _conflict_handler(*_args: object, **_kwargs: object) -> None:
        raise ClearanceTemplateCannotWithdrawError(template_id, ClearanceTemplateStatus.WITHDRAWN)

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_conflict_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_withdraw_clearance_template_returns_422_for_malformed_path_uuid() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates/not-a-uuid/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_withdraw_clearance_template_path_uuid_round_trip() -> None:
    """The template_id from the path threads through unchanged to the wired
    handler's command argument."""
    template_id = uuid4()
    captured: dict[str, UUID] = {}

    async def _capturing_handler(command: object, **_kwargs: object) -> None:
        captured["template_id"] = command.template_id  # type: ignore[attr-defined]

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            withdraw_clearance_template=_capturing_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/withdraw", json={"reason": "policy change"}
        )
    assert response.status_code == 204, response.text
    assert captured["template_id"] == template_id
