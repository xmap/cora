"""Unit tests for ``HttpRangeChecksumAdapter``.

This adapter is on the always-on http/https verifier path for every real
deployment, so its Match / Mismatch / Unreachable outcomes and its
never-raise contract (including malformed URIs) are pinned here. Transport
is stubbed via ``httpx.MockTransport`` so no network I/O runs.
"""

import hashlib
from uuid import uuid4

import httpx

from cora.data.adapters import HttpRangeChecksumAdapter
from cora.data.ports.checksum_verifier import Match, Mismatch, Unreachable

_SUPPLY_ID = uuid4()
_URI = "https://store.example/data/scan.h5"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _serving_client(payload: bytes) -> httpx.AsyncClient:
    """An AsyncClient whose transport serves ``payload`` for HEAD + range GET."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Length": str(len(payload))})
        return httpx.Response(206, content=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _failing_client(status: int) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_verify_returns_match_when_digest_equals_expected() -> None:
    payload = b"reconstructed volume" * 100
    async with _serving_client(payload) as client:
        result = await HttpRangeChecksumAdapter(client=client).verify(
            distribution_uri=_URI,
            expected_checksum=_sha256(payload),
            supply_id=_SUPPLY_ID,
        )
    assert result == Match(computed_checksum=_sha256(payload))


async def test_verify_returns_mismatch_when_digest_differs() -> None:
    payload = b"reconstructed volume" * 100
    async with _serving_client(payload) as client:
        result = await HttpRangeChecksumAdapter(client=client).verify(
            distribution_uri=_URI,
            expected_checksum="a" * 64,
            supply_id=_SUPPLY_ID,
        )
    assert result == Mismatch(computed_checksum=_sha256(payload))


async def test_verify_returns_unreachable_on_head_error_status() -> None:
    async with _failing_client(503) as client:
        result = await HttpRangeChecksumAdapter(client=client).verify(
            distribution_uri=_URI,
            expected_checksum="a" * 64,
            supply_id=_SUPPLY_ID,
        )
    assert isinstance(result, Unreachable)


async def test_verify_returns_unreachable_for_malformed_uri() -> None:
    # A control char in the URI makes httpx raise InvalidURL, which is NOT an
    # httpx.HTTPError subclass; the adapter must still honor the never-raise
    # contract and return Unreachable rather than crash to a 500.
    async with _serving_client(b"data") as client:
        result = await HttpRangeChecksumAdapter(client=client).verify(
            distribution_uri="https://store.example/data/sc\x00an.h5",
            expected_checksum="a" * 64,
            supply_id=_SUPPLY_ID,
        )
    assert isinstance(result, Unreachable)


def test_adapter_advertises_its_kind() -> None:
    assert HttpRangeChecksumAdapter().kind == "HttpRangeChecksum"
