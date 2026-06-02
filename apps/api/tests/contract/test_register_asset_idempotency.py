"""Contract tests for `Idempotency-Key` support on `POST /assets`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-
key entropy threshold.

The `model_id`-related cases monkeypatch the `load_model` symbol
imported into the `register_asset.handler` module: a stub that
returns a fully-formed Model snapshot pins the happy path (no need
to seed the upstream Model stream via `POST /models` first), and
a stub that always returns `None` pins the 404 path.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    PartNumber,
)


def _body(name: str = "APS-2BM", level: str = "Unit") -> dict[str, object]:
    return {"name": name, "level": level, "parent_id": str(uuid4())}


@pytest.mark.contract
def test_post_assets_without_key_creates_distinct_assets_on_each_call() -> None:
    with TestClient(create_app()) as client:
        # Use the same parent_id so only the Idempotency-Key absence
        # (not body diff) drives distinctness.
        body = _body()
        r1 = client.post("/assets", json=body)
        r2 = client.post("/assets", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] != r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_same_key_and_body_returns_same_asset_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-1"}
        body = _body()
        r1 = client.post("/assets", json=body, headers=headers)
        r2 = client.post("/assets", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] == r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-2"}
        r1 = client.post("/assets", json=_body(name="APS-2BM"), headers=headers)
        r2 = client.post("/assets", json=_body(name="Other"), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_assets_different_keys_create_distinct_assets() -> None:
    with TestClient(create_app()) as client:
        body = _body()
        r1 = client.post("/assets", json=body, headers={"Idempotency-Key": "ak-A"})
        r2 = client.post("/assets", json=body, headers={"Idempotency-Key": "ak-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] != r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-uuid"}
        body = _body()
        r1 = client.post("/assets", json=body, headers=headers)
        r2 = client.post("/assets", json=body, headers=headers)

    UUID(r1.json()["asset_id"])  # parses
    UUID(r2.json()["asset_id"])  # parses
    assert r1.json()["asset_id"] == r2.json()["asset_id"]


# ---------- model_id body field (asset-model binding slice) ----------


_KNOWN_MODEL_ID = UUID("01900000-0000-7000-8000-00000000ad01")
_KNOWN_FAMILY_ID = UUID("01900000-0000-7000-8000-00000000fa11")


@pytest.fixture
def accept_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUID]:
    """Stub `load_model` so `_KNOWN_MODEL_ID` resolves to a real Model.

    The register_asset handler imports `load_model` by name at module
    load, so we patch the binding in the handler's namespace (the one
    it actually calls). Mirrors the `accept_family` pattern in
    `test_define_model_contract.py`.
    """

    async def _stub(_event_store: object, requested_id: UUID) -> Model | None:
        if requested_id == _KNOWN_MODEL_ID:
            return Model(
                id=requested_id,
                name=ModelName("EigerX-9M"),
                manufacturer=Manufacturer(name=ManufacturerName("Dectris")),
                part_number=PartNumber("EX9M-001"),
                declared_families=frozenset({_KNOWN_FAMILY_ID}),
            )
        return None

    monkeypatch.setattr(
        "cora.equipment.features.register_asset.handler.load_model",
        _stub,
    )
    yield _KNOWN_MODEL_ID


@pytest.mark.contract
def test_post_assets_with_known_model_id_returns_201(accept_model: UUID) -> None:
    """Happy path: body carries model_id resolving to a real Model;
    handler appends AssetRegistered and returns 201 + new asset id."""
    body: dict[str, object] = {
        "name": "APS-2BM-Det",
        "level": "Device",
        "parent_id": str(uuid4()),
        "model_id": str(accept_model),
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 201
    UUID(response.json()["asset_id"])  # parses


@pytest.mark.contract
def test_post_assets_with_unknown_model_id_returns_404(accept_model: UUID) -> None:
    """Cross-BC 404: a model_id that does not resolve to a real Model
    stream surfaces as ModelNotFoundError mapped to HTTP 404 by the
    BC's `_handle_not_found` exception handler."""
    _ = accept_model  # fixture's stub returns None for any other id
    unknown_id = UUID("01900000-0000-7000-8000-00000000def0")
    body: dict[str, object] = {
        "name": "APS-2BM-Det",
        "level": "Device",
        "parent_id": str(uuid4()),
        "model_id": str(unknown_id),
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 404


@pytest.mark.contract
def test_post_assets_with_malformed_model_id_returns_422() -> None:
    """Pydantic schema validation: a non-UUID string in `model_id`
    fails request-body validation before the handler runs."""
    body: dict[str, object] = {
        "name": "APS-2BM",
        "level": "Unit",
        "parent_id": str(uuid4()),
        "model_id": "not-a-uuid",
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_without_model_id_still_returns_201() -> None:
    """Forward-compat: omitting model_id from the body continues to
    work (the field is optional, default None). Legacy clients that
    do not know about the binding are unaffected."""
    body: dict[str, object] = {
        "name": "APS",
        "level": "Site",
        "parent_id": str(uuid4()),
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 201


@pytest.mark.contract
def test_post_assets_same_key_different_model_id_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same Idempotency-Key + same body EXCEPT for model_id surfaces as 422.

    Gate-review P1-2: the cross-BC `hash_command` includes model_id
    (RegisterAsset is a frozen dataclass; canonical hash covers every
    field). Two distinct Model bindings under the same Idempotency-Key
    must surface as a key/body conflict, NOT silently return a cached
    asset_id pointing at the wrong Model.

    Patches `load_model` to accept either of two distinct Model ids so
    both requests would otherwise reach the handler successfully; the
    only differentiator on the cached-response check is the model_id
    field in the body.
    """
    model_a = UUID("01900000-0000-7000-8000-00000000a001")
    model_b = UUID("01900000-0000-7000-8000-00000000b002")
    family_id = UUID("01900000-0000-7000-8000-00000000fa12")

    async def _stub(_event_store: object, requested_id: UUID) -> Model | None:
        if requested_id in {model_a, model_b}:
            return Model(
                id=requested_id,
                name=ModelName("EigerX-9M"),
                manufacturer=Manufacturer(name=ManufacturerName("Dectris")),
                part_number=PartNumber("EX9M-001"),
                declared_families=frozenset({family_id}),
            )
        return None

    monkeypatch.setattr(
        "cora.equipment.features.register_asset.handler.load_model",
        _stub,
    )

    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-model"}
        body_a = {**_body(), "model_id": str(model_a)}
        body_b = {**_body(), "model_id": str(model_b)}
        r1 = client.post("/assets", json=body_a, headers=headers)
        r2 = client.post("/assets", json=body_b, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    detail = r2.json().get("detail", "").lower()
    assert "idempotency-key" in detail


# ---------- alternate_identifiers body field ----------


@pytest.mark.contract
def test_post_assets_with_alternate_identifiers_returns_201() -> None:
    """Happy path: body carries optional alternate_identifiers list of
    (kind, value) tuples; handler appends AssetRegistered and returns 201."""
    body: dict[str, object] = {
        "name": "APS-2BM-RotaryStage",
        "level": "Device",
        "parent_id": str(uuid4()),
        "alternate_identifiers": [
            {"kind": "SerialNumber", "value": "ANT130L-12345"},
            {"kind": "InventoryNumber", "value": "APS-2BM-RS-001"},
        ],
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 201
    UUID(response.json()["asset_id"])  # parses


@pytest.mark.contract
def test_post_assets_with_invalid_alternate_identifier_kind_returns_422() -> None:
    """Pydantic enum validation: an unknown kind value fails schema
    validation before the handler runs. ROR / GRID / ISNI deliberately
    belong on Model.manufacturer.identifier_type, NOT on Asset
    alternate identifiers."""
    body: dict[str, object] = {
        "name": "APS",
        "level": "Site",
        "parent_id": str(uuid4()),
        "alternate_identifiers": [{"kind": "ROR", "value": "01y2jtd41"}],
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_with_missing_alternate_identifier_value_returns_422() -> None:
    """Pydantic min_length: a body that omits `value` from one of the
    alternate-identifier entries fails schema validation."""
    body: dict[str, object] = {
        "name": "APS",
        "level": "Site",
        "parent_id": str(uuid4()),
        "alternate_identifiers": [{"kind": "SerialNumber"}],
    }
    with TestClient(create_app()) as client:
        response = client.post("/assets", json=body)

    assert response.status_code == 422


@pytest.mark.contract
def test_post_assets_with_alternate_identifiers_same_key_and_body_returns_same_asset_id() -> None:
    """Idempotency-Key retry with identical body (including the
    alternate_identifiers list) returns the cached asset_id."""
    body: dict[str, object] = {
        "name": "APS-2BM-RotaryStage",
        "level": "Device",
        "parent_id": str(uuid4()),
        "alternate_identifiers": [
            {"kind": "SerialNumber", "value": "ANT130L-12345"},
        ],
    }
    headers = {"Idempotency-Key": "ak-alt"}
    with TestClient(create_app()) as client:
        r1 = client.post("/assets", json=body, headers=headers)
        r2 = client.post("/assets", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] == r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_same_key_different_alternate_identifiers_returns_422() -> None:
    """Same Idempotency-Key + same body EXCEPT for `alternate_identifiers`
    surfaces as 422. The cross-BC `hash_command` includes the field
    (RegisterAsset is a frozen dataclass; canonical hash covers every
    field). Two distinct identifier sets under the same Idempotency-Key
    must surface as a key/body conflict."""
    parent = str(uuid4())
    base_body: dict[str, object] = {
        "name": "APS-2BM-RotaryStage",
        "level": "Device",
        "parent_id": parent,
    }
    body_a = {
        **base_body,
        "alternate_identifiers": [
            {"kind": "SerialNumber", "value": "ANT130L-AAAA"},
        ],
    }
    body_b = {
        **base_body,
        "alternate_identifiers": [
            {"kind": "SerialNumber", "value": "ANT130L-BBBB"},
        ],
    }
    headers = {"Idempotency-Key": "ak-alt-diff"}
    with TestClient(create_app()) as client:
        r1 = client.post("/assets", json=body_a, headers=headers)
        r2 = client.post("/assets", json=body_b, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    detail = r2.json().get("detail", "").lower()
    assert "idempotency-key" in detail
