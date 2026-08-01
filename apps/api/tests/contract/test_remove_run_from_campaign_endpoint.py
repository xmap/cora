"""Contract tests for `POST /campaigns/{campaign_id}/runs/{run_id}/remove`."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.remove_run_from_campaign.route import (
    _get_handler as _get_remove_run_handler,  # pyright: ignore[reportPrivateUsage]
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


def _add_member(client: TestClient, app: FastAPI, cid: str) -> UUID:
    """Seed a Run and add it as a member of the given Campaign."""
    run_id = uuid4()
    _seed_run(app, run_id)
    client.post(f"/campaigns/{cid}/runs/{run_id}/add")
    return run_id


@pytest.mark.contract
def test_post_remove_run_returns_204_on_happy_path() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = _add_member(client, app, cid)
        response = client.post(
            f"/campaigns/{cid}/runs/{run_id}/remove",
            json={"reason": "reassigned"},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_remove_run_returns_404_when_campaign_absent() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/runs/{uuid4()}/remove",
            json={"reason": "r"},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_remove_run_returns_409_when_not_member() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = uuid4()
        _seed_run(app, run_id)  # Run exists but never added
        response = client.post(
            f"/campaigns/{cid}/runs/{run_id}/remove",
            json={"reason": "r"},
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_remove_run_returns_400_on_whitespace_only_reason() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = _add_member(client, app, cid)
        response = client.post(
            f"/campaigns/{cid}/runs/{run_id}/remove",
            json={"reason": "   "},
        )
    assert response.status_code == 400
    assert "Campaign run remove reason" in response.json()["detail"]


@pytest.mark.contract
def test_post_remove_run_returns_422_when_reason_missing() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = _add_member(client, app, cid)
        response = client.post(f"/campaigns/{cid}/runs/{run_id}/remove", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_remove_run_returns_409_when_campaign_closed() -> None:
    """Pins NO CASCADE + terminal-frozen-membership: a Run added while
    Active stays a member after Campaign is Closed (NO CASCADE per GLP
    / ISO 17025 / 21 CFR §11.10(e) per-Run audit independence), but
    remove_run_from_campaign refuses to mutate a Closed Campaign's
    membership (terminal-frozen).
    """
    app = create_app()
    with TestClient(app) as client:
        cid = _register_and_start_campaign(client)
        run_id = _add_member(client, app, cid)
        # Active -> Closed; close succeeds even with a member Run
        # (NO CASCADE: Campaign state changes never touch Run state).
        close = client.post(f"/campaigns/{cid}/close")
        assert close.status_code == 204
        # Now attempt to remove the member Run; Campaign is terminal,
        # membership-mutation is frozen.
        response = client.post(
            f"/campaigns/{cid}/runs/{run_id}/remove",
            json={"reason": "post-close attempt"},
        )
    assert response.status_code == 409, response.text


@pytest.mark.contract
def test_post_remove_run_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_remove_run_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/campaigns/{uuid4()}/runs/{uuid4()}/remove",
            json={"reason": "r"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
