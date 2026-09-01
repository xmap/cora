"""Contract tests for `POST /policies`.

Mirror of `test_conduits_endpoint.py`. Verifies request/response
shape, UUID parsing for `conduit_id` and `permitted_principal_ids`, and
domain-error mapping for whitespace-only policy names.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy import POLICY_NAME_MAX_LENGTH

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


def _body(name: str = "Beam-team", **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": name,
        "conduit_id": _CONDUIT,
        "permitted_principal_ids": [_PRINCIPAL],
        "permitted_commands": ["RegisterActor"],
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_policies_returns_201_with_policy_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body())

    assert response.status_code == 201
    body = response.json()
    assert "policy_id" in body
    UUID(body["policy_id"])  # parses without raising


@pytest.mark.contract
def test_post_policies_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body(name="  Beam-team  "))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_policies_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json={
                "conduit_id": _CONDUIT,
                "permitted_principal_ids": [_PRINCIPAL],
                "permitted_commands": ["RegisterActor"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_missing_conduit_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json={
                "name": "Beam-team",
                "permitted_principal_ids": [_PRINCIPAL],
                "permitted_commands": ["RegisterActor"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_missing_surface_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json={
                "name": "Beam-team",
                "conduit_id": _CONDUIT,
                "permitted_principal_ids": [_PRINCIPAL],
                "permitted_commands": ["RegisterActor"],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_invalid_uuid_in_conduit_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body(conduit_id="not-a-uuid"))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_invalid_uuid_in_permitted_principal_ids_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_body(permitted_principal_ids=["not-a-uuid"]),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body(name="a" * 201))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_body(name="   "))
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_policies_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_body(name="a" * POLICY_NAME_MAX_LENGTH),
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_policies_accepts_empty_permission_lists_as_deny_all() -> None:
    """Deny-all policies (empty allow lists) are valid by construction —
    documented in the Policy aggregate. Pinned in a contract test so a
    future "must have at least one principal" rule has to flip this."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_body(permitted_principal_ids=[], permitted_commands=[]),
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_policies_accepts_dangling_conduit_reference() -> None:
    """Eventual-consistency stance: conduit_id referencing a non-existent
    Conduit is accepted at command time (same as Conduit→Zone).
    Pinned so a future "validate at command time" refactor has to flip
    this."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_body(conduit_id=str(uuid4())),
        )
    assert response.status_code == 201


# ---------- the two grant shapes ----------
#
# The body accepts either an exact `grants` mapping or the two
# cross-producted lists. Exactly one, because they mean different things:
# the pair form grants every listed principal every listed command, and
# quietly preferring one over the other would let a caller ask for a
# narrow mapping and receive a cross-product.


def _grants_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Beam-team",
        "conduit_id": _CONDUIT,
        "grants": {_PRINCIPAL: ["RegisterActor"]},
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_policies_accepts_an_exact_grants_mapping() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_grants_body())

    assert response.status_code == 201
    UUID(response.json()["policy_id"])


@pytest.mark.contract
def test_post_policies_accepts_grants_naming_different_commands_per_principal() -> None:
    """The shape the two-list form cannot express, and the reason for it."""
    other = "01900000-0000-7000-8000-000000000a02"
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_grants_body(grants={_PRINCIPAL: ["ListRuns"], other: ["AbortRun"]}),
        )

    assert response.status_code == 201


@pytest.mark.contract
def test_post_policies_accepts_an_empty_grants_mapping_as_deny_all() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/policies", json=_grants_body(grants={}))

    assert response.status_code == 201


@pytest.mark.contract
def test_post_policies_rejects_both_grant_shapes_with_422() -> None:
    """Refused rather than resolved: a caller sending both has one of the
    two in mind, and guessing which would silently over- or under-grant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json=_grants_body(
                permitted_principal_ids=[_PRINCIPAL],
                permitted_commands=["RegisterActor"],
            ),
        )

    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_neither_grant_shape_with_422() -> None:
    """Omitting both is a typo, not a request for a deny-all policy.

    A deny-all policy is still expressible, and unambiguously: send an
    empty `grants` mapping, or empty lists for the pair.
    """
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json={
                "name": "Beam-team",
                "conduit_id": _CONDUIT,
                "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
            },
        )

    assert response.status_code == 422


@pytest.mark.contract
def test_post_policies_rejects_half_the_pair_shape_with_422() -> None:
    """One list without the other cannot be cross-producted into anything."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/policies",
            json={
                "name": "Beam-team",
                "conduit_id": _CONDUIT,
                "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
                "permitted_principal_ids": [_PRINCIPAL],
            },
        )

    assert response.status_code == 422
