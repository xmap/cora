"""Contract tests for `POST /models`.

Covers the create-style slice surface: happy-path 201 + UUID, Pydantic
422 on schema misses (missing required, empty `declared_family_ids`),
domain 400 on whitespace-only name, and the cross-BC
`with_idempotency` decorator semantics (same key + same body returns
the cached id; same key + different body returns 422). Test keys are
short to stay below the gitleaks generic-API-key entropy threshold.

The Model handler enforces a cross-BC precondition: every entry in
`declared_family_ids` must resolve via the Family read repo's
`list_all_family_ids`, which is pool-backed and returns `[]` in the
in-memory TestClient harness. We monkeypatch the symbol imported into
the handler module to a fixed accept-all stub so the contract surface
under test stays focused on HTTP shape + idempotency semantics (the
cross-BC lookup is exercised at the unit and integration tiers).
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_FIXED_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa01")


@pytest.fixture
def accept_family(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `list_all_family_ids` so `_FIXED_FAMILY_ID` always resolves.

    The handler imports `list_all_family_ids` by name at module load, so we
    patch the binding in the handler's namespace (the one it actually
    calls), mirroring the unit-test pattern in
    `tests/unit/equipment/test_define_model_handler.py`.
    """

    async def _stub(_pool: object) -> list[UUID]:
        return [_FIXED_FAMILY_ID]

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _stub,
    )
    yield _FIXED_FAMILY_ID


def _body(
    *,
    name: str = "ANT130-L",
    part_number: str = "ANT130-L-150",
    manufacturer_name: str = "Aerotech",
) -> dict[str, object]:
    return {
        "name": name,
        "manufacturer": {"name": manufacturer_name},
        "part_number": part_number,
        "declared_family_ids": [str(_FIXED_FAMILY_ID)],
    }


@pytest.mark.contract
def test_post_models_happy_path_returns_201_and_uuid(accept_family: UUID) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        response = client.post("/models", json=_body())

    assert response.status_code == 201
    UUID(response.json()["model_id"])  # parses


@pytest.mark.contract
def test_post_models_missing_required_field_returns_422(accept_family: UUID) -> None:
    """Pydantic schema validation: missing `part_number`."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body()
        del body["part_number"]
        response = client.post("/models", json=body)

    assert response.status_code == 422


@pytest.mark.contract
def test_post_models_empty_declared_family_ids_returns_422(accept_family: UUID) -> None:
    """Pydantic `min_length=1` on `declared_family_ids`."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body()
        body["declared_family_ids"] = []
        response = client.post("/models", json=body)

    assert response.status_code == 422


@pytest.mark.contract
def test_post_models_whitespace_only_name_returns_400(accept_family: UUID) -> None:
    """Domain `InvalidModelNameError` after Pydantic min_length=1 passes."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body(name="   ")
        response = client.post("/models", json=body)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "name" in detail.lower()


@pytest.mark.contract
def test_post_models_unknown_declared_family_returns_404(accept_family: UUID) -> None:
    """Cross-BC precondition surfaces as 404 when a declared family does
    not resolve against `list_all_family_ids`."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body()
        body["declared_family_ids"] = [str(uuid4())]
        response = client.post("/models", json=body)

    assert response.status_code == 404


@pytest.mark.contract
def test_post_models_without_key_same_vendor_key_returns_409(
    accept_family: UUID,
) -> None:
    """Model ids are derived from the vendor key, so a second define with
    the same (manufacturer, part_number) collides on the deterministic
    stream (no Idempotency-Key to short-circuit it) and returns 409."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body()
        r1 = client.post("/models", json=body)
        r2 = client.post("/models", json=body)

    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_models_placeholder_part_number_creates_distinct_models(
    accept_family: UUID,
) -> None:
    """Two Models recorded with the unknown-pending-confirmation
    placeholder cannot derive a stable id, so each gets a distinct random
    id rather than colliding."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body(part_number="unknown-pending-confirmation")
        r1 = client.post("/models", json=body)
        r2 = client.post("/models", json=body)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["model_id"] != r2.json()["model_id"]


@pytest.mark.contract
def test_post_models_same_key_and_body_returns_same_model_id(accept_family: UUID) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-1"}
        body = _body()
        r1 = client.post("/models", json=body, headers=headers)
        r2 = client.post("/models", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["model_id"] == r2.json()["model_id"]


@pytest.mark.contract
def test_post_models_same_key_different_body_returns_422(accept_family: UUID) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-2"}
        r1 = client.post("/models", json=_body(name="ANT130-L"), headers=headers)
        r2 = client.post("/models", json=_body(name="Other"), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_models_different_keys_same_vendor_key_returns_409(accept_family: UUID) -> None:
    """Distinct Idempotency-Keys gate only the response cache, not
    identity: the same vendor key still derives one stream, so the second
    call collides and returns 409."""
    _ = accept_family
    with TestClient(create_app()) as client:
        body = _body()
        r1 = client.post("/models", json=body, headers={"Idempotency-Key": "mk-A"})
        r2 = client.post("/models", json=body, headers={"Idempotency-Key": "mk-B"})

    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_models_cached_response_returns_valid_uuid(accept_family: UUID) -> None:
    _ = accept_family
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-uuid"}
        body = _body()
        r1 = client.post("/models", json=body, headers=headers)
        r2 = client.post("/models", json=body, headers=headers)

    UUID(r1.json()["model_id"])  # parses
    UUID(r2.json()["model_id"])  # parses
    assert r1.json()["model_id"] == r2.json()["model_id"]
