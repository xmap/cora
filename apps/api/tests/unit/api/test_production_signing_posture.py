# pyright: reportPrivateUsage=false
"""Unit tests for the production signing-posture boot guard.

`_enforce_production_signing_posture` refuses to boot a production-tier
deployment (`prod` / `production` / `staging`, the same `_PROD_LIKE_APP_ENVS`
set the authz guards key on) whose signing factories still resolve to the
in-memory stubs (`InMemorySignaturePort` does no crypto;
`InMemorySigner` uses an ephemeral key). It is the signing-side sibling
of `_enforce_production_principal_policy` and of the
`make_inmemory_kernel` Kernel guard. The escape hatch is
`Settings.allow_insecure_inmemory_signing`.
"""

import pytest

from cora.api.main import (
    _enforce_production_signing_posture,
    _is_insecure_signing_stub,
    create_app,
)
from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort
from cora.infrastructure.adapters.in_memory_signer import InMemorySigner
from cora.infrastructure.config import Settings


class _RealSignaturePort:
    """Stand-in for a future wire-tier SignaturePort (name not InMemory*)."""


class _RealSigner:
    """Stand-in for a durable KMS / Sigstore signer."""


class _RealPublishPort:
    """Stand-in for a wire-tier PublishPort."""


def _settings(*, app_env: str, allow_insecure: bool = False) -> Settings:
    return Settings(  # type: ignore[call-arg]
        app_env=app_env,
        allow_insecure_inmemory_signing=allow_insecure,
    )


def _enforce(settings: Settings, **overrides: object) -> None:
    factories: dict[str, object] = {
        "signature_port_factory": InMemorySignaturePort,
        "signer_factory": InMemorySigner,
        "publish_port_factory": InMemoryPublishPort,
    }
    factories.update(overrides)
    _enforce_production_signing_posture(settings, **factories)  # type: ignore[arg-type]


@pytest.mark.parametrize("app_env", ["prod", "production", "staging"])
def test_prod_with_inmemory_stubs_refuses_boot(app_env: str) -> None:
    with pytest.raises(RuntimeError, match="in-memory signing stubs"):
        _enforce(_settings(app_env=app_env))


def test_refusal_message_names_every_stub_offender() -> None:
    with pytest.raises(RuntimeError) as exc:
        _enforce(_settings(app_env="prod"))
    message = str(exc.value)
    assert "signature_port_factory=InMemorySignaturePort" in message
    assert "signer_factory=InMemorySigner" in message
    assert "publish_port_factory=InMemoryPublishPort" in message


def test_escape_hatch_allows_inmemory_in_prod() -> None:
    _enforce(_settings(app_env="prod", allow_insecure=True))


@pytest.mark.parametrize("app_env", ["test", "local", "dev"])
def test_non_prod_app_env_allows_inmemory(app_env: str) -> None:
    _enforce(_settings(app_env=app_env))


def test_prod_with_real_factories_boots() -> None:
    _enforce(
        _settings(app_env="prod"),
        signature_port_factory=_RealSignaturePort,
        signer_factory=_RealSigner,
        publish_port_factory=_RealPublishPort,
    )


def test_prod_partial_stub_names_only_the_offender() -> None:
    with pytest.raises(RuntimeError) as exc:
        _enforce(
            _settings(app_env="prod"),
            signature_port_factory=InMemorySignaturePort,
            signer_factory=_RealSigner,
            publish_port_factory=_RealPublishPort,
        )
    message = str(exc.value)
    assert "signature_port_factory=InMemorySignaturePort" in message
    assert "signer_factory=" not in message
    assert "publish_port_factory=" not in message


def test_is_insecure_signing_stub_matches_known_classes() -> None:
    assert _is_insecure_signing_stub(InMemorySignaturePort)
    assert _is_insecure_signing_stub(InMemorySigner)
    assert _is_insecure_signing_stub(InMemoryPublishPort)


def test_is_insecure_signing_stub_forward_guards_inmemory_prefix() -> None:
    class InMemoryFutureSigner:
        """A new stub not yet in the explicit set is still caught by name."""

    assert _is_insecure_signing_stub(InMemoryFutureSigner)


def test_is_insecure_signing_stub_passes_real_classes() -> None:
    assert not _is_insecure_signing_stub(_RealSignaturePort)
    assert not _is_insecure_signing_stub(_RealSigner)


def test_create_app_refuses_prod_boot_with_default_inmemory_signing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: create_app wires the in-memory signing stubs, so a prod
    boot is refused at construction (before the lifespan opens a DB pool).

    REQUIRE_AUTHENTICATED_PRINCIPAL=true and a set TRUST_POLICY_ID clear the
    sibling principal-policy guard (which runs first) so the failure is
    provably the signing guard, and the escape hatch is left unset.
    """
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.setenv("TRUST_POLICY_ID", "00000000-0000-0000-0000-000000000002")
    monkeypatch.delenv("ALLOW_INSECURE_INMEMORY_SIGNING", raising=False)
    with pytest.raises(RuntimeError, match="in-memory signing stubs"):
        create_app()


def test_create_app_boots_in_prod_with_signing_escape_hatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The escape hatch lets a production-tier deployment construct the app
    with the in-memory signing stubs still wired. REQUIRE_AUTHENTICATED_PRINCIPAL
    and a set TRUST_POLICY_ID clear the sibling authz guard so only the signing
    escape hatch is under test."""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    monkeypatch.setenv("TRUST_POLICY_ID", "00000000-0000-0000-0000-000000000002")
    monkeypatch.setenv("ALLOW_INSECURE_INMEMORY_SIGNING", "true")
    app = create_app()
    assert app is not None
