"""Unit tests for SigningRegistry."""

from datetime import UTC, datetime

import pytest

from cora.infrastructure.adapters.default_signing_adapter import (
    DefaultSigningAdapter,
    JwksKid,
)
from cora.infrastructure.adapters.signing_registry import SigningRegistry
from cora.infrastructure.ports.byte_signer import ByteSigner
from cora.infrastructure.ports.canonicalizer import (
    UnsupportedCanonicalizationVersionError,
)


def _build_default_signing_adapter() -> DefaultSigningAdapter:
    async def loader(_: JwksKid) -> bytes:
        raise KeyError("no keys wired yet")

    async def resolver(_: str) -> bytes:
        raise KeyError("no keys wired yet")

    return DefaultSigningAdapter(
        private_key_loader=loader,
        public_key_resolver=resolver,
        clock=lambda: datetime(2026, 5, 31, tzinfo=UTC),
    )


def test_signing_registry_register_and_resolve_returns_adapter() -> None:
    registry = SigningRegistry()
    adapter = _build_default_signing_adapter()
    registry.register("cora/v1", adapter)
    resolved = registry.resolve("cora/v1")
    assert resolved is adapter
    assert isinstance(resolved, ByteSigner)


def test_signing_registry_resolve_unregistered_raises_with_known_set() -> None:
    registry = SigningRegistry()
    registry.register("cora/v1", _build_default_signing_adapter())
    with pytest.raises(UnsupportedCanonicalizationVersionError) as exc_info:
        registry.resolve("cora/v99")
    assert exc_info.value.requested_version == "cora/v99"
    assert "cora/v1" in exc_info.value.registered_versions


def test_signing_registry_empty_resolve_raises() -> None:
    registry = SigningRegistry()
    with pytest.raises(UnsupportedCanonicalizationVersionError):
        registry.resolve("cora/v1")


def test_signing_registry_duplicate_register_raises_value_error() -> None:
    registry = SigningRegistry()
    registry.register("cora/v1", _build_default_signing_adapter())
    with pytest.raises(ValueError, match="already registered"):
        registry.register("cora/v1", _build_default_signing_adapter())


def test_signing_registry_registered_versions_preserves_registration_order() -> None:
    registry = SigningRegistry()
    registry.register("cora/v1", _build_default_signing_adapter())
    registry.register("cora/v2-cose", _build_default_signing_adapter())
    assert registry.registered_versions() == ("cora/v1", "cora/v2-cose")


@pytest.mark.asyncio
async def test_signing_registry_aclose_is_idempotent() -> None:
    registry = SigningRegistry()
    await registry.aclose()
    await registry.aclose()


@pytest.mark.asyncio
async def test_signing_registry_aclose_suppresses_adapter_exceptions() -> None:
    class _FlakyAdapter:
        adapter_version = "cora/v1"

        async def sign(self, canonicalized: object, key_handle: object) -> object:
            raise NotImplementedError

        async def verify(
            self, canonicalized: object, signature: object, signing_trust_context: object
        ) -> object:
            raise NotImplementedError

        async def aclose(self) -> None:
            raise RuntimeError("flaky teardown")

    registry = SigningRegistry()
    registry.register("cora/v1", _FlakyAdapter())  # type: ignore[arg-type]
    await registry.aclose()
