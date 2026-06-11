"""HTTP contract tests for `promote_dataset` integrity guards.

The 7 happy/error tests in `test_promote_dataset_endpoint.py` cover
the route-level shape; this file covers the guard branches that
require seeding the upstream chain (Trial peer, aborted Run) plus
the 403/Authorize-deny path that needs a TrustAuthorize policy
fixture.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.infrastructure.event_envelope import to_new_event
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _dataset_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "D",
        "uri": "s3://b/k",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 0,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
    }
    base.update(overrides)
    return base


def _start_run_and_finish(client: TestClient, *, end_state: str) -> str:
    _cap_id = create_capability_via_api(client)
    """Set up the upstream chain, start a Run, then drive it to a
    terminal state via the appropriate transition slice. Returns the
    run_id. `end_state` ∈ {'Completed', 'Aborted', 'Stopped',
    'Truncated'}."""
    cap_id = client.post("/families", json={"name": "FlyMotion", "affordances": []}).json()[
        "family_id"
    ]
    method_id = client.post(
        "/methods", json={"name": "M", "capability_id": _cap_id, "needed_family_ids": [cap_id]}
    ).json()["method_id"]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets",
        json={"name": "A", "tier": "Unit", "parent_id": None, "facility_code": "cora"},
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add-family", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    run_id = client.post(
        "/runs",
        json={"name": "Run-X", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]

    # Drive to terminal state.
    if end_state == "Completed":
        resp = client.post(f"/runs/{run_id}/complete", json={})
    elif end_state == "Aborted":
        resp = client.post(f"/runs/{run_id}/abort", json={"reason": "operator stop"})
    elif end_state == "Stopped":
        resp = client.post(f"/runs/{run_id}/stop", json={"reason": "controlled exit"})
    elif end_state == "Truncated":
        resp = client.post(
            f"/runs/{run_id}/truncate",
            json={"reason": "process crashed"},
        )
    else:
        raise ValueError(f"Unknown end_state: {end_state!r}")
    assert resp.status_code == 204, resp.text
    return run_id


# ---------- S3: lineage-not-Production guard via HTTP ----------


@pytest.mark.contract
def test_post_promote_dataset_returns_409_when_lineage_has_trial() -> None:
    """Register an upstream Dataset (defaults to Trial), register a
    downstream Dataset whose derived_from references the upstream,
    attempt to promote the downstream → 409 with 'Trial' in detail.

    Pinned because this is the route → handler → decider → 409 stack
    for the lineage-must-be-Production guard, which the unit tests
    cover at the decider boundary only."""
    with TestClient(create_app()) as client:
        upstream_id = client.post("/datasets", json=_dataset_body()).json()["dataset_id"]
        downstream_id = client.post(
            "/datasets", json=_dataset_body(derived_from=[upstream_id])
        ).json()["dataset_id"]
        response = client.post(
            f"/datasets/{downstream_id}/promote",
            json={"reason": "trying to promote with trial lineage"},
        )
    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "trial" in detail
    assert upstream_id in response.json()["detail"]


# ---------- S7: Run-not-Completed guard via HTTP ----------


@pytest.mark.contract
@pytest.mark.parametrize("end_state", ["Aborted", "Stopped", "Truncated"])
def test_post_promote_dataset_returns_409_when_producing_run_not_completed(
    end_state: str,
) -> None:
    """Register a Dataset against a Run that ended in a non-Completed
    terminal state, attempt to promote → 409 with the actual end-state
    in the detail message.

    Pinned because the producing_run_end_state capture happens at
    register_dataset time and feeds the promote_dataset Run-must-be-
    Completed guard. Tests the full route → handler → decider → 409
    stack for each non-Completed terminal state."""
    with TestClient(create_app()) as client:
        run_id = _start_run_and_finish(client, end_state=end_state)
        dataset_id = client.post(
            "/datasets",
            json=_dataset_body(producing_run_id=run_id),
        ).json()["dataset_id"]
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "trying despite non-Completed Run"},
        )
    assert response.status_code == 409
    assert end_state in response.json()["detail"]
    assert "Completed" in response.json()["detail"]


@pytest.mark.contract
def test_post_promote_dataset_returns_204_when_producing_run_completed() -> None:
    """Inverse sanity: a Dataset registered against a Completed Run
    promotes successfully (the Run-must-be-Completed guard PASSES)."""
    with TestClient(create_app()) as client:
        run_id = _start_run_and_finish(client, end_state="Completed")
        dataset_id = client.post(
            "/datasets",
            json=_dataset_body(producing_run_id=run_id),
        ).json()["dataset_id"]
        response = client.post(
            f"/datasets/{dataset_id}/promote",
            json={"reason": "production run, ready to publish"},
        )
    assert response.status_code == 204


# ---------- S8: 403 Authorize.Deny via TrustAuthorize policy ----------


def _seed_policy(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal: UUID,
    permitted_commands: frozenset[str],
) -> None:
    """Same shape as test_cross_principal_bola.py + test_plan_wire_authz_endpoint.py."""
    event = PolicyDefined(
        policy_id=policy_id,
        name="Promote-dataset-authz-test-policy",
        conduit_id=UUID(int=0),
        permitted_principal_ids=(permitted_principal,),
        permitted_commands=tuple(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    asyncio.run(
        app.state.deps.event_store.append("Policy", policy_id, 0, [new_event]),
    )


_PERMITTED_SETUP_COMMANDS: frozenset[str] = frozenset(
    {
        # P1 needs to register the Dataset to have something to promote.
        "RegisterDataset",
        # P1 IS permitted to promote; P2 is not.
        "PromoteDataset",
    }
)


@pytest.fixture
def promote_authz_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with TrustAuthorize wired against a policy
    permitting P1 to Register + Promote but denying P2 entirely.

    Yields (client, p1, p2)."""
    policy_id = UUID("01900000-0000-7000-8000-00000000d801")
    p1 = UUID("01900000-0000-7000-8000-00000000d811")
    p2 = UUID("01900000-0000-7000-8000-00000000d812")

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()
    _seed_policy(
        cast("FastAPI", client.app),
        policy_id=policy_id,
        permitted_principal=p1,
        permitted_commands=_PERMITTED_SETUP_COMMANDS,
    )
    try:
        yield client, p1, p2
    finally:
        client.__exit__(None, None, None)


@pytest.mark.contract
def test_p2_gets_403_when_promoting_p1s_dataset(
    promote_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Authz contract: P2 is not in `permitted_principal_ids` for
    PromoteDataset, so POST /datasets/{id}/promote returns 403 before
    any decider logic runs. Pins the full route → handler →
    deps.authz.authorize → 403 stack for promote_dataset."""
    client, p1, p2 = promote_authz_app
    dataset_id = client.post(
        "/datasets",
        json=_dataset_body(),
        headers={"X-Principal-Id": str(p1)},
    ).json()["dataset_id"]

    response = client.post(
        f"/datasets/{dataset_id}/promote",
        json={"reason": "trying as P2"},
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, response.text
    assert "detail" in response.json()


@pytest.mark.contract
def test_p1_can_still_promote_their_own_dataset(
    promote_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Inverse sanity: the gate is per-principal, not blanket-deny.
    P1 (permitted) can promote their own Dataset."""
    client, p1, _ = promote_authz_app
    dataset_id = client.post(
        "/datasets",
        json=_dataset_body(),
        headers={"X-Principal-Id": str(p1)},
    ).json()["dataset_id"]

    response = client.post(
        f"/datasets/{dataset_id}/promote",
        json={"reason": "my own dataset"},
        headers={"X-Principal-Id": str(p1)},
    )
    assert response.status_code == 204, response.text
