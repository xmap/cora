"""Contract tests for `POST /actors/{actor_id}/reactivate`.

Mirrors the test_actors_endpoint.py shape: TestClient context manager
runs the lifespan with APP_ENV=test (InMemoryEventStore), HTTP-level
assertions only, persistence verified by handler unit tests.

The precondition is inverted from the deactivate sibling: every happy
path here needs an actor that has ALREADY been deactivated, so the
helper below performs both steps. Registration alone leaves the actor
active, which is this endpoint's 409 case rather than its 204 case.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_actor(client: TestClient) -> UUID:
    """Helper: register an actor and return its id."""
    response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 201
    return UUID(response.json()["actor_id"])


def _register_deactivated_actor(client: TestClient) -> UUID:
    """Helper: register an actor, deactivate it, return its id."""
    actor_id = _register_actor(client)
    response = client.post(f"/actors/{actor_id}/deactivate")
    assert response.status_code == 204
    return actor_id


@pytest.mark.contract
def test_post_reactivate_returns_204_for_deactivated_actor() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_deactivated_actor(client)
        response = client.post(f"/actors/{actor_id}/reactivate")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_reactivate_returns_404_for_unknown_actor() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/actors/{uuid4()}/reactivate")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_post_reactivate_returns_409_for_never_deactivated_actor() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post(f"/actors/{actor_id}/reactivate")
    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert "already active" in body["detail"].lower()


@pytest.mark.contract
def test_post_reactivate_twice_returns_409_on_the_second_call() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_deactivated_actor(client)
        first = client.post(f"/actors/{actor_id}/reactivate")
        assert first.status_code == 204
        second = client.post(f"/actors/{actor_id}/reactivate")
    assert second.status_code == 409
    body = second.json()
    assert "detail" in body
    assert "already active" in body["detail"].lower()


@pytest.mark.contract
def test_post_reactivate_returns_422_for_malformed_actor_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/actors/not-a-uuid/reactivate")
    assert response.status_code == 422


@pytest.mark.contract
def test_deactivate_reactivate_cycle_leaves_the_actor_listed_active() -> None:
    """The lockout the pair exists to close, end to end at the HTTP surface."""
    with TestClient(create_app()) as client:
        actor_id = _register_deactivated_actor(client)
        assert client.post(f"/actors/{actor_id}/reactivate").status_code == 204
        # A second deactivate must now be accepted again: the actor is
        # genuinely back in service, not merely reported as such.
        assert client.post(f"/actors/{actor_id}/deactivate").status_code == 204
