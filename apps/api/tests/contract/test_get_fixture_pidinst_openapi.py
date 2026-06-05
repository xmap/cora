"""OpenAPI surface pins for `GET /fixtures/{fixture_id}/pidinst`.

Per Section 15.3 of project_fixture_pidinst_design: pin the OpenAPI
schema for the Fixture-tier PIDINST read endpoint. Mirrors the
surface-pin posture of `test_assign_asset_persistent_id_openapi.py`.
Guards Lock 6 (route path `GET /fixtures/{fixture_id}/pidinst`),
Lock 1 (response model reuses the slice-E.1 `PidinstRecordResponse`
shape), and the Section 13 status-code map (200 + 403 + 404 + 409 +
422 surface on the GET route).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

pytestmark = pytest.mark.timeout(60, method="thread")

_ROUTE_PATH = "/fixtures/{fixture_id}/pidinst"


@pytest.mark.contract
def test_openapi_has_get_fixtures_id_pidinst_endpoint() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    assert _ROUTE_PATH in openapi["paths"], (
        f"OpenAPI must expose {_ROUTE_PATH} for the get_fixture_pidinst slice"
    )
    assert "get" in openapi["paths"][_ROUTE_PATH], f"{_ROUTE_PATH} must register a GET operation"


@pytest.mark.contract
def test_openapi_response_schema_has_pidinst_record_shape() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    response_component = openapi["components"]["schemas"]["PidinstRecordResponse"]
    properties = response_component["properties"]
    for field in (
        "identifier",
        "schema_version",
        "landing_page",
        "name",
        "publisher",
        "publication_year",
        "owners",
        "manufacturers",
        "model",
        "description",
        "instrument_types",
        "measured_variables",
        "dates",
        "related_identifiers",
        "alternate_identifiers",
        "measurement_techniques",
    ):
        assert field in properties, (
            f"PidinstRecordResponse must expose {field} per slice-C kernel shape"
        )


@pytest.mark.contract
def test_openapi_documents_200_404_500_response_codes() -> None:
    with TestClient(create_app()) as client:
        openapi = client.get("/openapi.json").json()

    operation = openapi["paths"][_ROUTE_PATH]["get"]
    responses = operation["responses"]
    expected = {"200", "403", "404", "409", "422"}
    missing = expected - set(responses.keys())
    assert not missing, (
        f"OpenAPI must document all status codes from Section 13; missing: {sorted(missing)}"
    )
