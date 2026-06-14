"""Contract tests for `POST /datasets`.

Genesis create-style endpoint mirroring the shape used by every
other register / define endpoint. Body carries nested checksum +
encoding objects, plus the optional cross-aggregate refs.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from tests.contract._helpers import create_capability_via_api
from tests.contract._subject_helpers import register_active_asset

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _good_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 1024,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
    }
    base.update(overrides)
    return base


def _start_run(client: TestClient) -> str:
    _cap_id = create_capability_via_api(client)
    """Set up the full upstream chain and start a Run; return the run_id."""
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
        f"/subjects/{subject_id}/mount", json={"asset_id": mount_asset_id, "reason": "test"}
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


def _register_subject(client: TestClient) -> str:
    return client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]


# ---------- Happy path ----------


@pytest.mark.contract
def test_post_datasets_returns_201_and_dataset_id_for_minimal_body() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body())
    assert response.status_code == 201
    body = response.json()
    assert "dataset_id" in body


@pytest.mark.contract
def test_post_datasets_round_trips_into_get_dataset_response() -> None:
    with TestClient(create_app()) as client:
        create = client.post(
            "/datasets",
            json=_good_body(
                encoding={
                    "media_type": "application/x-hdf5",
                    "conforms_to": [
                        "https://manual.nexusformat.org/",
                        "https://example.com/profile",
                    ],
                },
            ),
        )
        assert create.status_code == 201
        dataset_id = create.json()["dataset_id"]
        get = client.get(f"/datasets/{dataset_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["id"] == dataset_id
    assert body["name"] == "32-ID FlyScan recon"
    assert body["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert body["checksum"]["algorithm"] == "sha256"
    assert body["checksum"]["value"] == _GOOD_SHA256
    assert body["byte_size"] == 1024
    assert body["encoding"]["media_type"] == "application/x-hdf5"
    # Wire-shape conforms_to is sorted (canonical).
    assert body["encoding"]["conforms_to"] == [
        "https://example.com/profile",
        "https://manual.nexusformat.org/",
    ]
    assert body["producing_run_id"] is None
    assert body["subject_id"] is None
    assert body["derived_from"] == []
    assert body["status"] == "Registered"


@pytest.mark.contract
def test_post_datasets_with_producing_run_id_links_through() -> None:
    with TestClient(create_app()) as client:
        run_id = _start_run(client)
        response = client.post("/datasets", json=_good_body(producing_run_id=run_id))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_datasets_with_subject_id_links_through() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post("/datasets", json=_good_body(subject_id=subject_id))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_datasets_with_derived_from_links_through() -> None:
    with TestClient(create_app()) as client:
        upstream = client.post("/datasets", json=_good_body()).json()["dataset_id"]
        response = client.post("/datasets", json=_good_body(derived_from=[upstream]))
    assert response.status_code == 201


# ---------- Cross-aggregate not-found (404) ----------
#
# Per the locked `<X>NotFoundError -> 404` taxonomy, the renamed
# `ProducingRunNotFoundError` / `LinkedSubjectNotFoundError` /
# `DerivedFromDatasetsNotFoundError` route through `_handle_not_found`.
# `_handle_lineage_state_conflict` now only covers
# `DerivedFromDatasetsDiscardedError` -> 409 (referenced upstream
# Dataset is in Discarded status, a real state conflict).


@pytest.mark.contract
def test_post_datasets_returns_404_when_producing_run_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(producing_run_id=missing_id))
    assert response.status_code == 404
    assert "producing_run_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_returns_404_when_producing_procedure_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(producing_procedure_id=missing_id))
    assert response.status_code == 404
    assert "producing_procedure_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_returns_409_when_producing_procedure_is_not_terminal() -> None:
    """A freshly registered Procedure is Defined (non-terminal); registering a
    Dataset against it is a 409 state conflict (its actuation kind isn't final).
    item-6 option A."""
    with TestClient(create_app()) as client:
        procedure_id = client.post(
            "/procedures", json={"name": "fresh proc", "kind": "bakeout"}
        ).json()["procedure_id"]
        response = client.post("/datasets", json=_good_body(producing_procedure_id=procedure_id))
    assert response.status_code == 409
    assert "terminal" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_rejects_actuation_kind_as_free_input_with_422() -> None:
    """Trust posture: actuation_kind is server-derived from the producing
    Procedure, NEVER a caller input. The request model forbids it, so a caller
    trying to self-declare Physical to bypass the gate is rejected at the edge."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(actuation_kind="Physical"))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_datasets_returns_404_when_subject_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(subject_id=missing_id))
    assert response.status_code == 404
    assert "subject_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_returns_404_when_derived_from_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(derived_from=[missing_id]))
    assert response.status_code == 404
    assert missing_id in response.json()["detail"]


# ---------- Schema / domain validation ----------


@pytest.mark.contract
def test_post_datasets_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_datasets_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(name="   "))
    assert response.status_code == 400
    assert "name" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_negative_byte_size_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(byte_size=-1))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_datasets_rejects_unsupported_checksum_algorithm_with_400() -> None:
    """Algorithm passes Pydantic shape but decider rejects non-sha256."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/datasets",
            json=_good_body(checksum={"algorithm": "md5", "value": "d" * 32}),
        )
    assert response.status_code == 400
    assert "sha256" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_uri_without_scheme_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(uri="just-a-path"))
    assert response.status_code == 400
    assert "scheme" in response.json()["detail"].lower()


@pytest.mark.contract
@pytest.mark.parametrize(
    "uri",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ],
)
def test_post_datasets_rejects_known_xss_uri_schemes_with_400(uri: str) -> None:
    """Defensive blocklist applied at the API boundary. Pure blocklist
    so we don't constrain real storage schemes."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(uri=uri))
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_extra_fields_with_422() -> None:
    """Pydantic model_config={'extra': 'forbid'} rejects unknown keys."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json={**_good_body(), "extra_field": "boom"})
    assert response.status_code == 422


# ---------- GET ----------


@pytest.mark.contract
def test_get_datasets_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/datasets/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_datasets_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/datasets/not-a-uuid")
    assert response.status_code == 422


# ---------- Calibration BC AsShot citation ----------


def _load_dataset_payload(app: FastAPI, dataset_id: UUID) -> dict[str, object]:
    """Load the DatasetRegistered payload directly from the in-memory event store.

    The `GET /datasets/{id}` DTO does not expose `used_calibration_ids`
    today, so we drop down to the event store to inspect the
    persisted DatasetRegistered event. Same pattern as
    `_load_run_payload` in `test_start_run_endpoint.py`.
    """
    events, _ = asyncio.run(app.state.deps.event_store.load("Dataset", dataset_id))
    assert events, "expected at least one Dataset event"
    return dict(events[0].payload)


@pytest.mark.contract
def test_post_datasets_with_used_calibration_ids_returns_201() -> None:
    """POST /datasets with used_calibration_ids returns 201 and the
    persisted DatasetRegistered payload carries the sorted list of
    citations (no cross-BC validation of the CalibrationRevision ids
    — eventual-consistency stance per the Dataset lineage design,
    mirrors Run.pinned_calibration_ids exactly)."""
    app = create_app()
    cal_a = uuid4()
    cal_b = uuid4()
    with TestClient(app) as client:
        response = client.post(
            "/datasets",
            json=_good_body(
                name="cited-reconstruction",
                # Scrambled order; decider sorts before emit.
                used_calibration_ids=[str(cal_b), str(cal_a)],
            ),
        )
        assert response.status_code == 201, response.text
        dataset_id = UUID(response.json()["dataset_id"])
        payload = _load_dataset_payload(app, dataset_id)
    assert payload["used_calibration_ids"] == sorted([str(cal_a), str(cal_b)])


@pytest.mark.contract
def test_post_datasets_defaults_used_calibration_ids_to_empty_list() -> None:
    """Omitted used_calibration_ids serializes as `[]` on the payload
    (forward-compat-clean default; DatasetRegistered readers without
    the used_calibration_ids field fold the same way via
    `payload.get(..., [])`)."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/datasets", json=_good_body(name="no-citation-dataset"))
        assert response.status_code == 201, response.text
        dataset_id = UUID(response.json()["dataset_id"])
        payload = _load_dataset_payload(app, dataset_id)
    assert payload["used_calibration_ids"] == []


@pytest.mark.contract
def test_post_datasets_does_not_validate_used_calibration_existence() -> None:
    """Eventual-consistency stance per
    [[project_calibration_design]] anti-hook #3: the write path does
    NOT look up the CalibrationRevision ids. Any well-formed UUID
    list is accepted; downstream consumers that need to dereference
    still go through the Calibration BC. Mirrors
    Run.pinned_calibration_ids exactly."""
    with TestClient(create_app()) as client:
        # Fully synthetic citation ids that will never exist in any
        # Calibration BC stream.
        response = client.post(
            "/datasets",
            json=_good_body(
                name="synthetic-citations-dataset",
                used_calibration_ids=[str(uuid4()) for _ in range(5)],
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_datasets_rejects_malformed_used_calibration_uuid_with_422() -> None:
    """Pydantic enforces UUID format at the wire layer (the decider
    never sees malformed strings). Mirrors the malformed-UUID
    422 guard for Run.pinned_calibration_ids."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/datasets",
            json=_good_body(
                name="bad-citation-uuid-dataset",
                used_calibration_ids=["not-a-uuid"],
            ),
        )
    assert response.status_code == 422
