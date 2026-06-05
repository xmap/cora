"""OpenAPI surface pins for `POST /fixtures/{fixture_id}/assign-persistent-identifier`.

Per Section 15.3 of project_fixture_pidinst_design: pin the OpenAPI
schema for the Fixture-tier assign-persistent-identifier endpoint.
Mirrors the surface-pin posture of
`test_assign_asset_persistent_id_openapi.py`. Guards Lock 6 (route
path `POST /fixtures/{fixture_id}/assign-persistent-identifier`),
Lock 17 (response echoes scheme + value), Lock 12 (server-mint posture:
request carries scheme + optional suffix, never `value`), and the
Section 13 status-code map (201 success; 400/403/404/409/502 domain
+ authorization failures; 422 wire-layer validation failures).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

pytestmark = pytest.mark.timeout(60, method="thread")

_ROUTE_PATH = "/fixtures/{fixture_id}/assign-persistent-identifier"


@pytest.mark.contract
def test_openapi_has_assign_fixture_persistent_identifier_endpoint() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    assert _ROUTE_PATH in openapi["paths"], (
        f"OpenAPI must expose {_ROUTE_PATH} for the assign_fixture_persistent_id slice"
    )
    assert "post" in openapi["paths"][_ROUTE_PATH], f"{_ROUTE_PATH} must register a POST operation"


@pytest.mark.contract
def test_openapi_request_body_exposes_scheme_and_suffix_only() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    request_component = openapi["components"]["schemas"]["AssignFixturePersistentIdRequest"]
    properties = request_component["properties"]
    assert "scheme" in properties, "request body must expose scheme"
    assert "suffix" in properties, "request body must expose suffix"
    assert "scheme" in request_component["required"], "scheme is REQUIRED at the wire"
    assert "suffix" not in request_component.get("required", []), (
        "suffix is OPTIONAL per Lock 22 (auto-generated when absent)"
    )
    assert "value" not in properties, (
        "request body MUST NOT carry a value field per Lock 12 server-mint posture"
    )


@pytest.mark.contract
def test_openapi_response_body_echoes_scheme_and_value() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    response_component = openapi["components"]["schemas"]["AssignFixturePersistentIdResponse"]
    properties = response_component["properties"]
    assert "scheme" in properties, "response body must echo the assigned scheme"
    assert "value" in properties, "response body must echo the assigned value"
    required = response_component["required"]
    assert "scheme" in required, "response scheme is REQUIRED (always present)"
    assert "value" in required, "response value is REQUIRED (always present)"


@pytest.mark.contract
def test_openapi_documents_201_400_403_404_409_502_422_responses() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    operation = openapi["paths"][_ROUTE_PATH]["post"]
    responses = operation["responses"]
    expected = {"201", "400", "403", "404", "409", "502", "422"}
    missing = expected - set(responses.keys())
    assert not missing, (
        "OpenAPI must document all status codes from Section 13 / Lock 19;"
        f" missing: {sorted(missing)}"
    )
