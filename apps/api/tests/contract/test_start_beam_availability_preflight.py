"""Contract tests for the cross-BC beam-availability gate (BEAM-1).

Pins the wire-level behavior of the beam pre-flight gate on
POST /runs and POST /procedures/{id}/start: the decider's beam errors
must surface as HTTP 409 (the cannot-transition mapping), mirroring the
sibling Enclosure pre-flight contract tests.

  - 409 closed shutter -> RunRequiresOpenBeamShuttersError /
    ProcedureRequiresOpenBeamShuttersError ("beam is not available").
  - 409 bad-quality read -> RunBeamAvailabilityUnknownError /
    ProcedureBeamAvailabilityUnknownError ("unknown", fail-closed).

Swap-in pattern (same as the Enclosure preflight contract tests): the
test installs a fixed-reading BeamAvailabilityLookup onto the frozen
Kernel via `dataclasses.replace` AFTER `create_app()` and re-wires the
affected BC, since the wiring closures captured the old kernel.
"""

import dataclasses

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from tests.contract._helpers import seed_method_chain
from tests.contract._subject_helpers import register_active_asset


class _FixedBeamLookup:
    def __init__(self, reading: BeamAvailabilityLookupResult) -> None:
        self._reading = reading

    async def read_beam_availability(self) -> BeamAvailabilityLookupResult:
        return self._reading


_CLOSED = BeamAvailabilityLookupResult(
    fes_open=False, sbs_open=True, fes_permit=True, quality_ok=True
)
_BAD_QUALITY = BeamAvailabilityLookupResult(
    fes_open=True, sbs_open=True, fes_permit=True, quality_ok=False
)


def _install_run_beam_lookup(app: FastAPI, reading: BeamAvailabilityLookupResult) -> None:
    from cora.run import wire_run

    new_deps = dataclasses.replace(
        app.state.deps, beam_availability_lookup=_FixedBeamLookup(reading)
    )
    app.state.deps = new_deps
    app.state.run = wire_run(new_deps)


def _install_operation_beam_lookup(app: FastAPI, reading: BeamAvailabilityLookupResult) -> None:
    from cora.operation import wire_operation

    new_deps = dataclasses.replace(
        app.state.deps, beam_availability_lookup=_FixedBeamLookup(reading)
    )
    app.state.deps = new_deps
    app.state.operation = wire_operation(new_deps)


def _seed_plan_and_subject(client: TestClient) -> tuple[str, str]:
    """Build the upstream chain up to (but not starting) a Run."""
    chain = seed_method_chain(client)
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": chain.practice_id, "asset_ids": [chain.asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    return plan_id, subject_id


def _register_procedure(client: TestClient) -> str:
    response = client.post("/procedures", json={"name": "Bakeout", "kind": "bakeout"})
    assert response.status_code == 201, response.text
    return response.json()["procedure_id"]


@pytest.mark.contract
def test_post_runs_returns_409_when_beam_shutter_closed() -> None:
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id = _seed_plan_and_subject(client)
        _install_run_beam_lookup(app, _CLOSED)
        response = client.post(
            "/runs",
            json={"name": "blocked", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    assert "beam is not available" in response.json()["detail"]


@pytest.mark.contract
def test_post_runs_returns_409_when_beam_quality_unknown() -> None:
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id = _seed_plan_and_subject(client)
        _install_run_beam_lookup(app, _BAD_QUALITY)
        response = client.post(
            "/runs",
            json={"name": "unknown-beam", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 409, response.text
    assert "unknown" in response.json()["detail"]


@pytest.mark.contract
def test_post_runs_returns_201_when_beam_open() -> None:
    """Explicit all-open reading (not the default stub) still starts."""
    app = create_app()
    with TestClient(app) as client:
        plan_id, subject_id = _seed_plan_and_subject(client)
        _install_run_beam_lookup(
            app,
            BeamAvailabilityLookupResult(
                fes_open=True, sbs_open=True, fes_permit=True, quality_ok=True
            ),
        )
        response = client.post(
            "/runs",
            json={"name": "open-beam", "plan_id": plan_id, "subject_id": subject_id},
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_start_procedure_returns_409_when_beam_shutter_closed() -> None:
    app = create_app()
    with TestClient(app) as client:
        pid = _register_procedure(client)
        _install_operation_beam_lookup(app, _CLOSED)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    assert "beam is not available" in response.json()["detail"]


@pytest.mark.contract
def test_post_start_procedure_returns_409_when_beam_quality_unknown() -> None:
    app = create_app()
    with TestClient(app) as client:
        pid = _register_procedure(client)
        _install_operation_beam_lookup(app, _BAD_QUALITY)
        response = client.post(f"/procedures/{pid}/start")
    assert response.status_code == 409, response.text
    assert "unknown" in response.json()["detail"]
