"""Contract tests for `GET /readyz` (the readiness probe route).

`test_readiness.py` covers the pure helper (`probe_database` /
`readiness_body`); this covers the ROUTE that wires them: the status
mapping and the 503 + Retry-After path a probe consumer actually sees.

The test app builds the in-memory kernel (no pool), so the DB fault
paths are exercised by monkeypatching `probe_database` at its point of
use in `cora.api.main`, since the route reads it as a module global.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

import cora.api.main as api_main
from cora.api.main import create_app
from cora.infrastructure.config import Settings


@pytest.mark.contract
def test_readyz_reports_ready_200_with_no_pool() -> None:
    """The in-memory test app has no pool: ready, database skipped, HTTP 200."""
    with TestClient(create_app()) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "skipped"
    assert "Retry-After" not in response.headers


@pytest.mark.contract
def test_readyz_reports_inert_for_an_observe_only_deployment() -> None:
    """The observe-only claim a facility can curl without credentials.

    Settings are INJECTED rather than read from the process env, for two
    reasons: conftest enables control writes for the suite (so an
    env-derived app would report `reachable` and could not show this), and
    injection pins the value end-to-end from settings through the route,
    which a vocabulary check could not distinguish from a hardcode.
    """
    observe_only = Settings(
        app_env="test", control_writes_enabled=False, compute_substrate="in_memory"
    )
    with TestClient(create_app(settings=observe_only)) as client:
        body = client.get("/readyz").json()
    assert body["actuation"] == "inert"


@pytest.mark.contract
def test_readyz_reports_reachable_when_control_writes_are_enabled() -> None:
    """The other direction, so a hardcoded `inert` cannot pass."""
    writable = Settings(app_env="test", control_writes_enabled=True, compute_substrate="in_memory")
    with TestClient(create_app(settings=writable)) as client:
        body = client.get("/readyz").json()
    assert body["actuation"] == "reachable"


@pytest.mark.contract
def test_readyz_reports_503_and_retry_after_when_database_faults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DB fault surfaces as 503 not_ready with a Retry-After header."""

    async def _unreachable(_pool: Any) -> str:
        return "unreachable"

    monkeypatch.setattr(api_main, "probe_database", _unreachable)
    with TestClient(create_app()) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == "unreachable"
    assert response.headers["Retry-After"] == "5"


@pytest.mark.contract
def test_readyz_is_not_in_the_openapi_schema() -> None:
    """Operational plumbing, not API surface (include_in_schema=False)."""
    with TestClient(create_app()) as client:
        spec = client.get("/openapi.json").json()
    assert "/readyz" not in spec["paths"]
