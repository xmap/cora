"""Unit tests for the `build_kernel` wiring.

Verifies the `app_env` branching: `test` selects the in-memory store and
a no-op teardown; the production branch is exercised by integration tests
that have a real Postgres available.

Also covers the Authorize-adapter selection driven by
`Settings.trust_policy_id`: unset -> AllowAllAuthorize; set ->
TrustAuthorize. The factory is injected by the composition root
(see `cora.api.main`); tests inject `build_authorize` directly to
exercise the production wiring without going through FastAPI.
"""

from uuid import UUID

import pytest
from pydantic import SecretStr

from cora.agent import build_llm
from cora.agent.adapters import AnthropicLLM
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import build_kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeLLM
from cora.trust import build_authorize
from cora.trust.authorize import TrustAuthorize


@pytest.mark.unit
async def test_build_kernel_uses_in_memory_stores_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert deps.settings.app_env == "test"
    assert isinstance(deps.event_store, InMemoryEventStore)
    assert isinstance(deps.idempotency_store, InMemoryIdempotencyStore)
    # Teardown is a no-op in test mode but must still be awaitable.
    await teardown()


@pytest.mark.unit
async def test_build_kernel_populates_all_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every BC's wiring relies on these fields being present and non-None."""
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert deps.clock is not None
    assert deps.id_generator is not None
    assert deps.authz is not None
    assert deps.event_store is not None
    assert deps.idempotency_store is not None
    await teardown()


@pytest.mark.unit
async def test_build_kernel_uses_allow_all_authorize_when_no_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permissive default: no `trust_policy_id` -> no real auth.
    Tests + dev environments rely on this; flipping it to fail-closed
    would be a significant behavior change."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)

    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert isinstance(deps.authz, AllowAllAuthorize)
    await teardown()


@pytest.mark.unit
async def test_build_kernel_uses_trust_authorize_when_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting `trust_policy_id` swaps to the real Trust adapter.
    The adapter loads the configured policy at request time; this test
    verifies the WIRING, not the gating semantics (those live in
    `tests/unit/trust/test_trust_authorize.py`)."""
    monkeypatch.setenv("APP_ENV", "test")
    policy_id = UUID("01900000-0000-7000-8000-000000000601")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert isinstance(deps.authz, TrustAuthorize)
    await teardown()


# ---------- LLM + LogbookMirror wiring ----------


@pytest.mark.unit
async def test_kernel_llm_is_none_by_default_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build_kernel` in `app_env=test` does NOT call llm_factory;
    Agent subscribers fail-fast on `kernel.llm is None` at
    registration. Defaulting to None in tests keeps the contract
    explicit: opt-in to LLM by passing FakeLLM to
    make_inmemory_kernel."""
    monkeypatch.setenv("APP_ENV", "test")
    deps, teardown = await build_kernel(authorize_factory=build_authorize, llm_factory=build_llm)
    assert deps.llm is None
    await teardown()


@pytest.mark.unit
async def test_kernel_logbook_mirror_is_none_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No production implementor lands today; the field reserves
    the slot and subscribers short-circuit on `is None`."""
    monkeypatch.setenv("APP_ENV", "test")
    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert deps.logbook_mirror is None
    await teardown()


@pytest.mark.unit
def test_build_llm_returns_none_when_api_key_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent BC's LLMFactory short-circuits cleanly when no
    credential is configured; subscriber registration handles the
    fail-fast at subscriber registration."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings()  # type: ignore[call-arg]
    assert build_llm(settings) is None


@pytest.mark.unit
def test_build_llm_returns_anthropic_adapter_when_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the operator wires ANTHROPIC_API_KEY, the production
    AnthropicLLM lands in the Kernel."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    settings = Settings()  # type: ignore[call-arg]
    llm = build_llm(settings)
    assert isinstance(llm, AnthropicLLM)


@pytest.mark.unit
def test_anthropic_api_key_is_secret_str_and_redacted_in_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes gate-review architecture P1 #2 (secret leak in
    repr/str/json). `SecretStr` redacts the raw value to `**********`
    in every standard serialisation path; the raw key surfaces only
    via `.get_secret_value()`, which only `build_llm` calls."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-VALUE-12345")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.anthropic_api_key is not None
    # `repr(SecretStr)` redacts.
    assert "sk-ant-secret-VALUE-12345" not in repr(settings)
    assert "sk-ant-secret-VALUE-12345" not in repr(settings.anthropic_api_key)
    # `str(SecretStr)` redacts.
    assert "sk-ant-secret-VALUE-12345" not in str(settings.anthropic_api_key)
    # `model_dump_json()` redacts.
    assert "sk-ant-secret-VALUE-12345" not in settings.model_dump_json()
    # Round-trip via `.get_secret_value()` works (the legitimate read path).
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret-VALUE-12345"


@pytest.mark.unit
async def test_make_inmemory_kernel_accepts_fake_llm_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subscriber-level tests that need an LLM inject FakeLLM
    via make_inmemory_kernel(..., llm=...). Pins the override seam."""
    from cora.infrastructure.deps import make_inmemory_kernel
    from cora.infrastructure.ports import SystemClock, UUIDv7Generator

    fake = FakeLLM()
    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
        llm=fake,
    )
    assert kernel.llm is fake


@pytest.mark.unit
def test_make_inmemory_kernel_defaults_enclosure_lookup_to_always_permitted_stub() -> None:
    """`enclosure_lookup` defaults to `AlwaysPermittedEnclosureLookup` so
    existing Run / Procedure tests don't have to seed enclosures.

    Pins the L-port-7 stub-only roster: the kernel always has an
    EnclosureLookup wired, never `None`. Regression here would let
    pre-flight gate handlers crash with AttributeError on tests that
    never opt in to seeded enclosures.
    """
    from cora.infrastructure.deps import make_inmemory_kernel
    from cora.infrastructure.ports import (
        AlwaysPermittedEnclosureLookup,
        SystemClock,
        UUIDv7Generator,
    )

    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )
    assert isinstance(kernel.enclosure_lookup, AlwaysPermittedEnclosureLookup)


@pytest.mark.unit
def test_make_inmemory_kernel_accepts_enclosure_lookup_override() -> None:
    """Pre-flight gate tests that need to seed enclosures inject an
    InMemoryEnclosureLookup via make_inmemory_kernel(..., enclosure_lookup=...).
    Pins the override seam mirroring facility_lookup."""
    from cora.infrastructure.adapters.in_memory_enclosure_lookup import (
        InMemoryEnclosureLookup,
    )
    from cora.infrastructure.deps import make_inmemory_kernel
    from cora.infrastructure.ports import SystemClock, UUIDv7Generator

    fake = InMemoryEnclosureLookup()
    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
        enclosure_lookup=fake,
    )
    assert kernel.enclosure_lookup is fake


# ---------- token_verifier wiring ----------


@pytest.mark.unit
async def test_kernel_token_verifier_is_none_when_no_idps_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Today's default: no IDENTITY_PROVIDERS env var -> empty list ->
    `build_idp_registry` returns None -> kernel.token_verifier is None.
    The bearer-auth middleware short-circuits on None and falls through
    to the legacy X-Principal-Id path, so existing deployments without
    edge-auth configured stay on the trust-the-proxy posture."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("IDENTITY_PROVIDERS", raising=False)

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert deps.token_verifier is None
    await teardown()


@pytest.mark.unit
async def test_kernel_token_verifier_built_when_identity_providers_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator sets IDENTITY_PROVIDERS -> kernel.token_verifier is a
    non-None `IdentityProviderRegistry` ready to verify inbound bearer
    tokens. The middleware uses this slot."""
    import json

    from cora.infrastructure.auth import IdentityProviderRegistry

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "IDENTITY_PROVIDERS",
        json.dumps(
            [
                {
                    "issuer": "https://idp.example.com",
                    "jwks_url": "https://idp.example.com/jwks.json",
                    "audiences": {
                        "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                    },
                }
            ]
        ),
    )

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert isinstance(deps.token_verifier, IdentityProviderRegistry)
    await teardown()


@pytest.mark.unit
def test_build_static_subject_mapper_merges_bindings_across_idps() -> None:
    """Each IdP carries its own subject_bindings; the composition root
    merges them into one StaticSubjectMapper keyed on (issuer, subject).
    Two IdPs each with their own subjects produce one mapper that knows
    both."""
    from cora.infrastructure.auth import (
        IdentityProviderConfig,
        IdpSubjectBinding,
        build_static_subject_mapper,
    )

    actor_a = UUID("01900000-0000-7000-8000-000000000a01")
    actor_b = UUID("01900000-0000-7000-8000-000000000a02")
    idp_a = IdentityProviderConfig(
        issuer="https://idp-a.example.com",
        jwks_url="https://idp-a.example.com/jwks.json",
        audiences={UUID("00000000-0000-0000-0000-000000000020"): "https://cora.example/http"},
        subject_bindings=[IdpSubjectBinding(subject="user-a", actor_id=actor_a, kind="human")],
    )
    idp_b = IdentityProviderConfig(
        issuer="https://idp-b.example.com",
        jwks_url="https://idp-b.example.com/jwks.json",
        audiences={UUID("00000000-0000-0000-0000-000000000020"): "https://cora.example/http"},
        subject_bindings=[
            IdpSubjectBinding(subject="ci-bot", actor_id=actor_b, kind="service_account"),
        ],
    )

    mapper = build_static_subject_mapper([idp_a, idp_b])

    # The internal _bindings dict is private; we exercise the public
    # __call__ instead. Both subjects must resolve through the merged map.
    import asyncio

    assert asyncio.run(mapper("https://idp-a.example.com", "user-a")) == (actor_a, "human")
    assert asyncio.run(mapper("https://idp-b.example.com", "ci-bot")) == (
        actor_b,
        "service_account",
    )


@pytest.mark.unit
def test_build_static_subject_mapper_inherits_idp_principal_kind_when_binding_kind_unset() -> None:
    """A binding with `kind=None` (default) inherits the enclosing IdP's
    `principal_kind`. A binding with explicit `kind` wins. Pins the
    resolution that lives in `build_static_subject_mapper` — the
    static mapper always returns a truthy kind, so the verifier-level
    `kind or principal_kind` fallback would never fire for this path
    if inheritance weren't applied at merge time."""
    from cora.infrastructure.auth import (
        IdentityProviderConfig,
        IdpSubjectBinding,
        build_static_subject_mapper,
    )

    actor_default = UUID("01900000-0000-7000-8000-000000000b01")
    actor_explicit = UUID("01900000-0000-7000-8000-000000000b02")
    actor_ci = UUID("01900000-0000-7000-8000-000000000b03")
    audiences = {UUID("00000000-0000-0000-0000-000000000020"): "https://cora.example/http"}

    # Mixed-use IdP: default human, one binding overrides to service_account.
    idp_humans = IdentityProviderConfig(
        issuer="https://idp.example.com",
        jwks_url="https://idp.example.com/jwks.json",
        audiences=audiences,
        principal_kind="human",
        subject_bindings=[
            IdpSubjectBinding(subject="alice", actor_id=actor_default),  # inherits "human"
            IdpSubjectBinding(
                subject="cron-bot",
                actor_id=actor_explicit,
                kind="service_account",  # explicit override
            ),
        ],
    )
    # CI-only IdP: IdP-wide default is service_account; bindings stay terse.
    idp_ci = IdentityProviderConfig(
        issuer="https://ci.example.com",
        jwks_url="https://ci.example.com/jwks.json",
        audiences=audiences,
        principal_kind="service_account",
        subject_bindings=[
            # Inherits "service_account" from the IdP default.
            IdpSubjectBinding(subject="release-bot", actor_id=actor_ci),
        ],
    )

    mapper = build_static_subject_mapper([idp_humans, idp_ci])

    import asyncio

    assert asyncio.run(mapper("https://idp.example.com", "alice")) == (actor_default, "human")
    assert asyncio.run(mapper("https://idp.example.com", "cron-bot")) == (
        actor_explicit,
        "service_account",
    )
    assert asyncio.run(mapper("https://ci.example.com", "release-bot")) == (
        actor_ci,
        "service_account",
    )


@pytest.mark.unit
def test_build_static_subject_mapper_raises_on_duplicate_issuer_subject_pair() -> None:
    """Two IdPs with the SAME issuer URL declaring the same `subject`
    would let an operator's typo silently grant one IdP's sub to a
    different Actor. Reject at composition time with a named error so
    boot fails loud before any bearer token is checked."""
    from cora.infrastructure.auth import (
        IdentityProviderConfig,
        IdpSubjectBinding,
        build_static_subject_mapper,
    )

    actor_a = UUID("01900000-0000-7000-8000-000000000a01")
    actor_b = UUID("01900000-0000-7000-8000-000000000a02")
    audiences = {UUID("00000000-0000-0000-0000-000000000020"): "https://cora.example/http"}
    # Two entries with the SAME issuer URL but conflicting subject->actor maps.
    idp_1 = IdentityProviderConfig(
        issuer="https://idp.example.com",
        jwks_url="https://idp.example.com/jwks.json",
        audiences=audiences,
        subject_bindings=[IdpSubjectBinding(subject="dup", actor_id=actor_a, kind="human")],
    )
    idp_2 = IdentityProviderConfig(
        issuer="https://idp.example.com",
        introspection_url="https://idp.example.com/introspect",
        introspection_client_id="rs",
        introspection_client_secret=SecretStr("secret"),
        audiences=audiences,
        subject_bindings=[IdpSubjectBinding(subject="dup", actor_id=actor_b, kind="human")],
    )

    with pytest.raises(ValueError, match=r"Duplicate IdP subject binding"):
        build_static_subject_mapper([idp_1, idp_2])


@pytest.mark.unit
def test_make_inmemory_kernel_accepts_token_verifier_override() -> None:
    """Bearer-auth contract tests inject a verifier via
    make_inmemory_kernel(..., token_verifier=...). Pins the override seam
    so the single-kernel-construction-site invariant doesn't grow a
    test-only second site."""
    from cora.infrastructure.deps import make_inmemory_kernel
    from cora.infrastructure.ports import (
        SystemClock,
        TokenVerifier,
        UUIDv7Generator,
        VerifiedPrincipal,
    )

    class _StubVerifier:
        async def verify(self, token: str, *, expected_audience: UUID) -> VerifiedPrincipal:
            _ = token, expected_audience
            raise NotImplementedError

    stub: TokenVerifier = _StubVerifier()
    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
        token_verifier=stub,
    )
    assert kernel.token_verifier is stub
