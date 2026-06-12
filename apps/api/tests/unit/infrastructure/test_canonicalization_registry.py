"""Unit tests for CanonicalizationRegistry."""

import pytest

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.ports.canonicalizer import (
    CanonicalizedBytes,
    Canonicalizer,
    UnsupportedCanonicalizationVersionError,
)


class _FakeAdapter:
    def __init__(self, version: str = "fake/v0") -> None:
        self._version = version

    @property
    def adapter_version(self) -> str:
        return self._version

    def canonicalize(self, payload_type: str, payload: object) -> CanonicalizedBytes:
        raise NotImplementedError

    def verify_content_hash(self, payload_type: str, payload: object, claimed_hash: str) -> bool:
        raise NotImplementedError


def test_canonicalization_registry_register_and_resolve_returns_adapter() -> None:
    registry = CanonicalizationRegistry()
    adapter = DefaultCanonicalizationAdapter()
    registry.register("cora/v1", adapter)
    resolved = registry.resolve("cora/v1")
    assert resolved is adapter
    assert isinstance(resolved, Canonicalizer)


def test_canonicalization_registry_resolve_unregistered_raises_with_known_set() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", DefaultCanonicalizationAdapter())
    with pytest.raises(UnsupportedCanonicalizationVersionError) as exc_info:
        registry.resolve("cora/v99")
    assert exc_info.value.requested_version == "cora/v99"
    assert "cora/v1" in exc_info.value.registered_versions


def test_canonicalization_registry_duplicate_register_raises_value_error() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", DefaultCanonicalizationAdapter())
    with pytest.raises(ValueError, match="already registered"):
        registry.register("cora/v1", DefaultCanonicalizationAdapter())


def test_canonicalization_registry_set_default_requires_registered_version() -> None:
    registry = CanonicalizationRegistry()
    with pytest.raises(UnsupportedCanonicalizationVersionError):
        registry.set_default("cora/v1")


def test_canonicalization_registry_default_version_returns_set_value() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", DefaultCanonicalizationAdapter())
    registry.set_default("cora/v1")
    assert registry.default_version() == "cora/v1"


def test_canonicalization_registry_default_version_unset_raises() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", DefaultCanonicalizationAdapter())
    with pytest.raises(UnsupportedCanonicalizationVersionError):
        registry.default_version()


def test_canonicalization_registry_registered_versions_preserves_registration_order() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", _FakeAdapter("cora/v1"))
    registry.register("cora/v2-cose", _FakeAdapter("cora/v2-cose"))
    assert registry.registered_versions() == ("cora/v1", "cora/v2-cose")


@pytest.mark.asyncio
async def test_canonicalization_registry_aclose_is_idempotent() -> None:
    registry = CanonicalizationRegistry()
    await registry.aclose()
    await registry.aclose()


@pytest.mark.asyncio
async def test_canonicalization_registry_aclose_suppresses_adapter_exceptions() -> None:
    class _FlakyAdapter(_FakeAdapter):
        async def aclose(self) -> None:
            raise RuntimeError("flaky teardown")

    registry = CanonicalizationRegistry()
    registry.register("cora/v1", _FlakyAdapter("cora/v1"))
    await registry.aclose()


@pytest.mark.asyncio
async def test_canonicalization_registry_aclose_skips_adapters_without_aclose() -> None:
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", _FakeAdapter("cora/v1"))
    await registry.aclose()
