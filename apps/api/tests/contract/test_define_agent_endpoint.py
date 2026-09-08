"""Contract tests for `POST /agents`."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.agent.errors import UnauthorizedError
from cora.agent.features.define_agent.route import (
    _get_handler as _get_define_agent_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.api.main import create_app


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_agents_returns_201_with_agent_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/agents", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "agent_id" in body
    UUID(body["agent_id"])  # parses


@pytest.mark.contract
def test_post_agents_accepts_full_payload() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/agents",
            json=_body(
                description="Synthesises terminal Runs.",
                canonical_uri="https://example.org/agents/run-debrief",
                capabilities=["summarize", "categorize"],
                model_ref={
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "snapshot_pin": "20251001",
                },
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_agents_co_registers_actor_with_kind_agent() -> None:
    """Cross-BC atomic write: the Agent's id is queryable as an Actor."""
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_body())
        assert define.status_code == 201, define.text
        agent_id = define.json()["agent_id"]
        # The same id resolves under /actors/{id} (Access BC).
        actor_resp = client.get(f"/actors/{agent_id}")
    assert actor_resp.status_code == 200, actor_resp.text
    actor = actor_resp.json()
    assert actor["id"] == agent_id
    assert actor["name"] == "Run Debrief"


@pytest.mark.contract
def test_post_agents_400_on_invalid_canonical_uri() -> None:
    """https-scheme requirement raises 400 (domain validation)."""
    with TestClient(create_app()) as client:
        response = client.post("/agents", json=_body(canonical_uri="http://no-https.example.org"))
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_agents_422_on_missing_required_field() -> None:
    body = _body()
    del body["model_ref"]
    with TestClient(create_app()) as client:
        response = client.post("/agents", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_agents_422_on_empty_kind() -> None:
    """Pydantic min_length=1 boundary catches empty kind."""
    with TestClient(create_app()) as client:
        response = client.post("/agents", json=_body(kind=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_agents_idempotency_key_returns_same_id_on_replay() -> None:
    """Standard idempotency-key pattern: same key + same body returns same id."""
    headers = {"Idempotency-Key": "test-key-001"}
    body = _body()
    with TestClient(create_app()) as client:
        first = client.post("/agents", json=body, headers=headers)
        second = client.post("/agents", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["agent_id"] == second.json()["agent_id"]


@pytest.mark.contract
def test_post_agents_same_key_different_body_returns_422() -> None:
    """Idempotency-Key reused with a DIFFERENT body must surface as 422.

    Closes gate-review test-coverage P1 (Conduit BC ships the
    equivalent test; agent BC was missing it). Catches regressions
    in `frozenset[capabilities]` hash stability and other body-shape
    drift.
    """
    headers = {"Idempotency-Key": "test-key-002"}
    with TestClient(create_app()) as client:
        first = client.post("/agents", json=_body(name="First"), headers=headers)
        assert first.status_code == 201, first.text
        second = client.post("/agents", json=_body(name="Different"), headers=headers)
    assert second.status_code == 422, second.text


@pytest.mark.contract
def test_post_agents_round_trips_prompt_template_id() -> None:
    """prompt_template_id survives wire -> domain -> event -> read path.

    8f-b's RunDebriefer subscriber will load the registry by this UUID;
    a Pydantic schema regression on the DTO or a missing field in the
    event payload would silently break that lookup.
    """
    template_id = "01900000-0000-7000-8000-00000000aaaa"
    with TestClient(create_app()) as client:
        define = client.post("/agents", json=_body(prompt_template_id=template_id))
        assert define.status_code == 201, define.text
        agent_id = define.json()["agent_id"]
        get_resp = client.get(f"/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["prompt_template_id"] == template_id


@pytest.mark.contract
def test_post_agents_400_on_rule_brain_with_prompt_template() -> None:
    """A Rule brain runs no prompt; naming one over the wire is a 400, not a
    silently-accepted value nobody reads."""
    body = _body(
        model_ref=None,
        brain={"kind": "Rule", "rule": "ExperimentCoordinator:v1"},
        prompt_template_id="01900000-0000-7000-8000-00000000aaaa",
    )
    with TestClient(create_app()) as client:
        response = client.post("/agents", json=body)
    assert response.status_code == 400, response.text


@pytest.mark.contract
def test_post_agents_returns_403_when_authorize_denies() -> None:
    """Authorize-deny surfaces as 403 with the deny reason in detail.

    Closes gate-review test-coverage P1: zero 403 tests existed for any
    Agent endpoint; if `_handle_unauthorized` is removed or remapped,
    only unit tests would catch it.
    """
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_define_agent_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/agents", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
