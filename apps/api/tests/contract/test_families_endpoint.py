"""Contract tests for `POST /families`.

Mirror of the other create-style endpoint tests. Verifies request
schema, response schema, status codes, and that the
whitespace-only-name domain error maps to 400 via the BC's
exception handler.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.family import (
    FAMILY_NAME_MAX_LENGTH,
    FamilyAlreadyExistsError,
)
from cora.equipment.features.define_family.route import (
    _get_handler as _get_define_family_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_families_returns_201_with_family_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "Tomography", "affordances": []})

    assert response.status_code == 201
    body = response.json()
    assert "family_id" in body
    UUID(body["family_id"])  # parses


@pytest.mark.contract
def test_post_families_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "  Tomography  ", "affordances": []})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_families_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_families_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "", "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_families_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "a" * 201, "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_families_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "   ", "affordances": []})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_families_rejects_non_string_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": 123, "affordances": []})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_families_uses_max_length_constant_from_domain() -> None:
    """Pydantic max_length must track the domain FAMILY_NAME_MAX_LENGTH constant."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/families",
            json={"name": "a" * FAMILY_NAME_MAX_LENGTH, "affordances": []},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_families_returns_409_when_capability_already_exists() -> None:
    """Defensive guard: FamilyAlreadyExistsError -> 409. Same
    pattern as ActorAlreadyExistsError / SubjectAlreadyExistsError —
    essentially impossible in production with UUIDv7 ids, but the
    unmapped raise would surface as 500 instead of a clean 409.
    Test overrides the slice handler with a stub that raises
    directly so the route's exception handler is verified
    end-to-end."""
    existing_id = uuid4()

    async def _stub(*_args: object, **_kwargs: object) -> UUID:
        raise FamilyAlreadyExistsError(existing_id)

    app = create_app()
    app.dependency_overrides[_get_define_family_handler] = lambda: _stub
    try:
        with TestClient(app) as client:
            response = client.post("/families", json={"name": "Tomography", "affordances": []})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert "detail" in body
    assert str(existing_id) in body["detail"]


# ---------- non-empty affordance contract tests ----------
#
# Gate review P0 (contract symmetry): the existing endpoint tests
# only exercise empty `"affordances": []`. These tests pin non-empty
# affordance roundtrip, sorted response, dedup-via-frozenset, and
# 422 paths for missing/invalid.


@pytest.mark.contract
def test_post_families_round_trips_non_empty_affordances_sorted() -> None:
    """POST with multiple affordances → GET returns them sorted alphabetically."""
    with TestClient(create_app()) as client:
        post = client.post(
            "/families",
            json={
                "name": "SortTest",
                "affordances": ["Rotatable", "Homeable", "Bendable"],
            },
        )
        assert post.status_code == 201
        family_id = post.json()["family_id"]

        get = client.get(f"/families/{family_id}")
        assert get.status_code == 200
        assert get.json()["affordances"] == ["Bendable", "Homeable", "Rotatable"]


@pytest.mark.contract
def test_post_families_dedupes_duplicate_affordances_via_frozenset() -> None:
    """Duplicate affordance entries in the request body dedupe at the
    handler boundary (`frozenset(body.affordances)`); the response
    shows each affordance exactly once."""
    with TestClient(create_app()) as client:
        post = client.post(
            "/families",
            json={
                "name": "DupTest",
                "affordances": ["Rotatable", "Rotatable", "Homeable"],
            },
        )
        assert post.status_code == 201
        family_id = post.json()["family_id"]
        get = client.get(f"/families/{family_id}")
        assert get.json()["affordances"] == ["Homeable", "Rotatable"]


@pytest.mark.contract
def test_post_families_rejects_unknown_affordance_with_422() -> None:
    """Pydantic enum-validation catches an unknown affordance string
    at the API boundary, before the request reaches the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/families",
            json={"name": "BadAffordance", "affordances": ["Bogus"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_families_rejects_missing_affordances_field_with_422() -> None:
    """The affordances field is REQUIRED at define_family time per
    the Family design (Pattern P). Omitting it returns 422, never 201
    with empty default."""
    with TestClient(create_app()) as client:
        response = client.post("/families", json={"name": "MissingField"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_families_renders_empty_affordances_as_list_not_null() -> None:
    """An explicitly-empty affordance set serializes as `[]`, never
    `null`. Determinism for clients that filter on the field shape."""
    with TestClient(create_app()) as client:
        post = client.post("/families", json={"name": "EmptyAffTest", "affordances": []})
        family_id = post.json()["family_id"]
        get = client.get(f"/families/{family_id}")

    body = get.json()
    assert body["affordances"] == []
    assert body["affordances"] is not None
