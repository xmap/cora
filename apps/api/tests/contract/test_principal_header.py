"""Contract tests for the `X-Principal-Id` header.

Three concerns:
  1. **Optional**: existing tests that don't set the header continue
     to pass (fallback to SYSTEM_PRINCIPAL_ID). One test pins this.
  2. **Validated**: malformed UUIDs in the header surface as 422.
  3. **End-to-end with TrustAuthorize**: when TrustAuthorize is wired
     and a policy permits a specific principal, requests with that
     principal's UUID in the header succeed (201/200) while requests
     WITHOUT the header (or with a non-permitted principal) get 403.
     This is the load-bearing test that proves the full chain works:
     header → get_principal_id → handler kwarg → Authorize port →
     TrustAuthorize → load_policy → evaluate → Allow/Deny → HTTP
     status.
"""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests._authz import trust_authorize_client

# ---------- Optional / validation ----------


@pytest.mark.contract
def test_post_actors_works_without_x_principal_id_header() -> None:
    """Pin the legacy-mode fallback: no header → SYSTEM_PRINCIPAL_ID,
    AllowAllAuthorize allows. Existing tests rely on this."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_accepts_explicit_x_principal_id_header() -> None:
    """Header IS extracted and used (passed to handler kwarg). Under
    AllowAllAuthorize the request still succeeds; the header's effect
    is verified end-to-end in the TrustAuthorize tests below."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_rejects_malformed_x_principal_id_with_422() -> None:
    """Pydantic UUID validation surfaces a 422 before the handler runs."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"X-Principal-Id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_zones_accepts_x_principal_id_header_in_trust_bc_too() -> None:
    """Trust BC's get_principal_id mirrors Access's; both honour
    X-Principal-Id. Pin so a future divergence is caught."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/zones",
            json={"name": "Detector"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 201


# ---------- End-to-end with TrustAuthorize ----------


@pytest.fixture
def trust_authorize_app(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with TrustAuthorize wired against a freshly
    seeded permissive policy. Yields (client, allowed_principal_id,
    policy_id).

    The seeded policy permits ONE principal to issue all the commands
    used in these tests. Every other principal (including the
    SYSTEM_PRINCIPAL_ID fallback when no header is sent) gets Deny.
    """
    policy_id = UUID("01900000-0000-7000-8000-00000000700f")
    allowed_principal = UUID("01900000-0000-7000-8000-000000000a01")
    with trust_authorize_client(
        monkeypatch,
        permitted_principal_ids={allowed_principal},
        permitted_commands={
            "RegisterActor",
            "DefineZone",
            "DefineConduit",
            "DefinePolicy",
        },
        policy_id=policy_id,
    ) as client:
        yield client, allowed_principal, policy_id


@pytest.mark.contract
def test_x_principal_id_matching_policy_returns_201(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """End-to-end Allow path: header sets the principal_id that
    TrustAuthorize evaluates against the seeded policy → Allow → 201."""
    client, allowed_principal, _ = trust_authorize_app
    response = client.post(
        "/actors",
        json={"name": "Doga"},
        headers={"X-Principal-Id": str(allowed_principal)},
    )
    assert response.status_code == 201


@pytest.mark.contract
def test_x_principal_id_not_in_policy_returns_403(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """End-to-end Deny path: a different principal in the header
    fails the policy's permitted_principal_ids check → Deny → 403."""
    client, _, _ = trust_authorize_app
    other_principal = UUID("01900000-0000-7000-8000-000000000a02")
    response = client.post(
        "/actors",
        json={"name": "Doga"},
        headers={"X-Principal-Id": str(other_principal)},
    )
    assert response.status_code == 403


@pytest.mark.contract
def test_missing_x_principal_id_falls_back_to_system_and_is_denied(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """No header → SYSTEM_PRINCIPAL_ID fallback → SYSTEM is NOT in
    the permitted_principal_ids → Deny → 403. Important production
    guard: deployments without an auth proxy effectively run as
    SYSTEM, which (under a real policy) gets nothing."""
    client, _, _ = trust_authorize_app
    response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 403


# ---------- require_authenticated_principal ----------


@pytest.mark.contract
def test_missing_header_returns_401_when_authentication_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase-3e production posture: setting
    `require_authenticated_principal=True` makes a missing
    `X-Principal-Id` header a 401 instead of falling back to
    SYSTEM_PRINCIPAL_ID."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")

    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 401
    assert "X-Principal-Id" in response.json()["detail"]


@pytest.mark.contract
def test_present_header_passes_through_when_authentication_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `require_authenticated_principal=True` and AllowAllAuthorize,
    a present X-Principal-Id flows through normally and the request
    succeeds. Pin: enabling the require flag does not break the happy
    path; it only changes the absent-header behavior."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    pid = str(uuid4())

    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_create_app_refuses_to_boot_in_prod_without_require_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase-3e production startup gate: `app_env=prod` (or
    `production`) demands `require_authenticated_principal=True`.
    The cost of failing at boot is cheaper than discovering the
    SYSTEM-fallback in production logs."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    with pytest.raises(RuntimeError, match="require_authenticated_principal"):
        create_app()


@pytest.mark.contract
def test_create_app_boots_in_prod_with_real_policy_and_require_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recommended prod posture boots cleanly.

    Production env with a real TRUST_POLICY_ID + require=True boots. With
    no TRUST_POLICY_ID the AllowAll-in-prod gate would refuse; that path
    is covered by the two tests below.
    """
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TRUST_POLICY_ID", "00000000-0000-0000-0000-000000000002")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    # Just constructing the app is enough; no need to enter lifespan
    # (which would try to open a real DB pool against production URL).
    app = create_app()
    assert app is not None


@pytest.mark.contract
def test_create_app_refuses_prod_with_permissive_authz_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prod with no TRUST_POLICY_ID wires AllowAllAuthorize (permit
    everyone). `require=True` isolates this from condition 1; the new
    gate refuses boot because ALLOW_PERMISSIVE_AUTHZ is not set, so a
    production deployment cannot silently ship the permit-everyone
    default."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    monkeypatch.delenv("ALLOW_PERMISSIVE_AUTHZ", raising=False)
    with pytest.raises(RuntimeError, match="ALLOW_PERMISSIVE_AUTHZ"):
        create_app()


@pytest.mark.contract
def test_create_app_boots_prod_with_explicit_permissive_optin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escape hatch: prod + no policy boots when the operator
    consciously sets ALLOW_PERMISSIVE_AUTHZ=true (an airgapped /
    single-operator pilot that genuinely wants no command gating). The
    insecure choice is allowed, but only as a deliberate one."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    monkeypatch.setenv("ALLOW_PERMISSIVE_AUTHZ", "true")
    app = create_app()
    assert app is not None


@pytest.mark.contract
def test_create_app_refuses_staging_with_permissive_authz_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging is production-tier: it must not silently run AllowAll
    either. require=True isolates this from condition 1; the AllowAll
    gate refuses boot because ALLOW_PERMISSIVE_AUTHZ is not set."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    monkeypatch.delenv("ALLOW_PERMISSIVE_AUTHZ", raising=False)
    with pytest.raises(RuntimeError, match="ALLOW_PERMISSIVE_AUTHZ"):
        create_app()


@pytest.mark.contract
@pytest.mark.parametrize(
    "env_value",
    # Production-tier spellings + case / whitespace variants: the guard
    # normalizes APP_ENV (strip + lower) so "PROD" or " Production "
    # cannot silently bypass the gates (pydantic case-folds env-var
    # NAMES, not VALUES). "staging" is production-tier too.
    ["prod", "production", "staging", "PROD", "Production", " prod "],
)
def test_startup_gate_recognizes_prod_like_app_envs(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
) -> None:
    monkeypatch.setenv("APP_ENV", env_value)
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    with pytest.raises(RuntimeError):
        create_app()


@pytest.mark.contract
def test_create_app_refuses_to_boot_when_trust_policy_set_without_require_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate-review F1: setting TRUST_POLICY_ID without also setting
    REQUIRE_AUTHENTICATED_PRINCIPAL=true would let any caller spoof
    `X-Principal-Id: 00000000-0000-0000-0000-000000000000` and become
    SYSTEM under whichever Policy is wired (the bootstrap seed permits
    SYSTEM to DefinePolicy + RegisterActor). The gate now fires
    regardless of app_env — staging/local with TRUST_POLICY_ID set are
    exactly where operators test auth before going live, and that's
    where the misconfig is most likely to ship."""
    monkeypatch.setenv("APP_ENV", "local")  # explicitly NOT prod
    monkeypatch.setenv("TRUST_POLICY_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    with pytest.raises(RuntimeError, match="require_authenticated_principal"):
        create_app()


@pytest.mark.contract
def test_create_app_boots_when_trust_policy_set_with_require_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate-review F1 inverse: TRUST_POLICY_ID + REQUIRE_AUTHENTICATED_PRINCIPAL=true
    boots cleanly. Operator turns on authz by setting BOTH together."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("TRUST_POLICY_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    app = create_app()
    assert app is not None


@pytest.mark.contract
def test_create_app_boots_with_no_trust_policy_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: today's default (trust_policy_id unset, AllowAllAuthorize)
    still boots without REQUIRE_AUTHENTICATED_PRINCIPAL. The
    runbook simplification kicks in only when TRUST_POLICY_ID is set."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    app = create_app()
    assert app is not None


# ---------- gate-review HIGH F11 ----------


@pytest.mark.contract
def test_create_app_refuses_prod_with_allow_insecure_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate-review HIGH F11: under app_env=prod, any IdP entry with
    allow_insecure_jwks_url=True is rejected at boot. Per-adapter
    HTTPS gate already raises when an http:// URL is paired without
    the opt-in; this Settings-level check defends against an operator
    (or env-var-write attacker) flipping the opt-in to True to
    downgrade ONE IdP to plaintext under prod."""
    import json

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.setenv(
        "IDENTITY_PROVIDERS",
        json.dumps(
            [
                {
                    "issuer": "https://idp.example.com",
                    "jwks_url": "http://attacker.example.com/jwks",
                    "allow_insecure_jwks_url": True,
                    "audiences": {
                        "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                    },
                }
            ]
        ),
    )
    with pytest.raises(RuntimeError, match=r"allow_insecure_jwks_url"):
        create_app()


@pytest.mark.contract
def test_create_app_refuses_prod_with_allow_insecure_introspection_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same F11 defense for the introspection URL — the higher-impact
    case since HTTP Basic auth would expose CORA's client_secret."""
    import json

    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.setenv(
        "IDENTITY_PROVIDERS",
        json.dumps(
            [
                {
                    "issuer": "https://idp.example.com",
                    "introspection_url": "http://attacker.example.com/introspect",
                    "introspection_client_id": "cora-rs",
                    "introspection_client_secret": "secret",
                    "allow_insecure_introspection_url": True,
                    "audiences": {
                        "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                    },
                }
            ]
        ),
    )
    with pytest.raises(RuntimeError, match=r"allow_insecure_introspection_url"):
        create_app()


@pytest.mark.contract
def test_create_app_allows_local_env_with_insecure_idps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inverse sanity: app_env=local + allow_insecure_*=True boots fine.
    The opt-ins exist for localhost test/dev fixtures."""
    import json

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    monkeypatch.setenv(
        "IDENTITY_PROVIDERS",
        json.dumps(
            [
                {
                    "issuer": "https://idp.example.com",
                    "jwks_url": "http://127.0.0.1:9999/jwks",
                    "allow_insecure_jwks_url": True,
                    "audiences": {
                        "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                    },
                }
            ]
        ),
    )
    app = create_app()
    assert app is not None
