"""Contract tests for `POST /campaigns/{campaign_id}/runs/{run_id}/add`."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.add_run_to_campaign.route import (
    _get_handler as _get_add_run_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)
from cora.run.aggregates.run.events import RunStarted

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL = uuid4()
_CORRELATION = uuid4()


def _register_and_start_campaign(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={
            "name": "membership-test",
            "intent": "Series",
            "lead_actor_id": str(uuid4()),
        },
    )
    cid = str(response.json()["campaign_id"])
    client.post(f"/campaigns/{cid}/start")
    return cid


def _seed_run(app: FastAPI, run_id: UUID) -> None:
    """Seed a Run by appending RunStarted directly to the in-memory store."""
    event = RunStarted(
        run_id=run_id,
        name="contract-test-run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(event),
        payload=run_to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="seed",
        correlation_id=_CORRELATION,
        causation_id=None,
        principal_id=_PRINCIPAL,
    )
    asyncio.run(
        app.state.deps.event_store.append("Run", run_id, 0, [new_event]),
    )


@pytest.mark.contract
def test_post_add_run_returns_204_on_happy_path() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = uuid4()
        _seed_run(app, run_id)

        response = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_add_run_returns_404_when_campaign_absent() -> None:
    app = create_app()
    with TestClient(app) as client:
        run_id = uuid4()
        _seed_run(app, run_id)
        response = client.post(f"/campaigns/{uuid4()}/runs/{run_id}/add")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_run_returns_404_when_run_absent() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        response = client.post(f"/campaigns/{cid}/runs/{uuid4()}/add")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_add_run_returns_409_when_campaign_terminal() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        client.post(f"/campaigns/{cid}/close")  # Active -> Closed
        run_id = uuid4()
        _seed_run(app, run_id)
        response = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    assert response.status_code == 409


@pytest.mark.contract
def test_post_add_run_returns_409_when_already_member() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = uuid4()
        _seed_run(app, run_id)
        first = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
        assert first.status_code == 204
        second = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    assert second.status_code == 409


@pytest.mark.contract
def test_post_add_run_returns_409_when_assigned_to_different_campaign() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid_one = _register_and_start_campaign(client)
        cid_two = _register_and_start_campaign(client)
        run_id = uuid4()
        _seed_run(app, run_id)
        first = client.post(f"/campaigns/{cid_one}/runs/{run_id}/add")
        assert first.status_code == 204
        cross = client.post(f"/campaigns/{cid_two}/runs/{run_id}/add")
    assert cross.status_code == 409


@pytest.mark.contract
def test_post_add_run_returns_409_when_campaign_closed() -> None:
    """Pins terminal-frozen-membership at the Closed terminal explicitly.

    Sibling to `test_post_add_run_returns_409_when_campaign_terminal`
    which already covers the same path via the same Active->Closed
    transition; this test exists to anchor the per-terminal naming
    pattern used by the cross-BC test convention (the Abandoned
    sibling lives below).
    """
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        close = client.post(f"/campaigns/{cid}/close")
        assert close.status_code == 204
        run_id = uuid4()
        _seed_run(app, run_id)
        response = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_add_run_returns_409_when_campaign_abandoned() -> None:
    """Same terminal-frozen-membership pin, Abandoned terminal."""
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        abandon = client.post(
            f"/campaigns/{cid}/abandon",
            json={"reason": "test-abandon"},
        )
        assert abandon.status_code == 204
        run_id = uuid4()
        _seed_run(app, run_id)
        response = client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_add_run_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_add_run_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/campaigns/{uuid4()}/runs/{uuid4()}/add")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
