"""Contract tests for `POST /editions/{edition_id}/publish`.

Publishes a Sealed Edition (mints a DOI, re-serializes, transitions to
Published). Returns 200 on success, 403 when Authorize denies, 404 when
the Edition is unknown, 409 when the Edition is not in Sealed state.

Wire-shape note: the happy 200 path requires a Sealed Edition, which
in turn needs a canonical Distribution for each member Dataset. The
TestClient app uses the in-memory DistributionLookup adapter that
resolves to None for every Dataset (no Postgres backing the
projection here), so an Edition can never reach Sealed in TestClient.
The happy path is locked at the integration tier
(tests/integration/test_edition_lifecycle_postgres.py). These contract
tests cover the error-mapping branches reachable in TestClient plus the
403 Authorize-deny stack.
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
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient, *, name: str = "ds") -> str:
    response = client.post(
        "/datasets",
        json={
            "name": name,
            "uri": f"s3://b/{name}",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _register_edition(client: TestClient, *, dataset_ids: list[str]) -> str:
    response = client.post(
        "/editions",
        json={
            "kind": "ROCrate",
            "title": "Edition Title",
            "dataset_ids": dataset_ids,
            "creators": [{"actor_id": str(uuid4()), "affiliation": "ANL"}],
            "publisher_facility_code": "cora",
            "license": "CC-BY-4.0",
            "publication_year": 2026,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["edition_id"]


# ---------- 404 ----------


@pytest.mark.contract
def test_post_publish_edition_returns_404_for_unknown_edition() -> None:
    with TestClient(create_app()) as client:
        unknown_id = uuid4()
        response = client.post(f"/editions/{unknown_id}/publish", json={})
    assert response.status_code == 404


# ---------- 409 ----------


@pytest.mark.contract
def test_post_publish_edition_returns_409_when_not_sealed() -> None:
    with TestClient(create_app()) as client:
        ds = _register_dataset(client, name="ds1")
        edition_id = _register_edition(client, dataset_ids=[ds])
        # Edition is Registered (never sealed in TestClient); publish
        # requires Sealed -> 409.
        response = client.post(f"/editions/{edition_id}/publish", json={})
    assert response.status_code == 409


# ---------- 403 Authorize.Deny via TrustAuthorize policy ----------


def _seed_policy(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal: UUID,
    permitted_commands: frozenset[str],
) -> None:
    event = PolicyDefined(
        policy_id=policy_id,
        name="Publish-edition-authz-test-policy",
        conduit_id=UUID(int=0),
        permitted_principal_ids=(permitted_principal,),
        permitted_commands=tuple(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
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
        "RegisterDataset",
        "RegisterEdition",
    }
)


@pytest.fixture
def publish_authz_app(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with TrustAuthorize wired against a policy
    permitting P1 to register Datasets + Editions but denying P2's
    PublishEdition. Yields (client, p1, p2)."""
    policy_id = UUID("01900000-0000-7000-8000-00000000e801")
    p1 = UUID("01900000-0000-7000-8000-00000000e811")
    p2 = UUID("01900000-0000-7000-8000-00000000e812")

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
def test_post_publish_edition_returns_403_when_authz_denies(
    publish_authz_app: tuple[TestClient, UUID, UUID],
) -> None:
    client, p1, p2 = publish_authz_app
    ds = client.post(
        "/datasets",
        json={
            "name": "ds",
            "uri": "s3://b/ds",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
        headers={"X-Principal-Id": str(p1)},
    ).json()["dataset_id"]
    edition_id = client.post(
        "/editions",
        json={
            "kind": "ROCrate",
            "title": "Edition Title",
            "dataset_ids": [ds],
            "creators": [{"actor_id": str(uuid4()), "affiliation": "ANL"}],
            "publisher_facility_code": "cora",
            "license": "CC-BY-4.0",
            "publication_year": 2026,
        },
        headers={"X-Principal-Id": str(p1)},
    ).json()["edition_id"]

    response = client.post(
        f"/editions/{edition_id}/publish",
        json={},
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, response.text
    assert "detail" in response.json()
