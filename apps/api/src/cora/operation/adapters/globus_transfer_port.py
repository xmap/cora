"""GlobusTransferPort: production `TransferPort` over the Globus Transfer service.

The first real substrate behind CORA's `TransferPort`. It takes an
already-authorized Globus `TransferClient` by injection (the OAuth2 dance is a
composition-root concern, not the adapter's), translates a `TransferRequest`
into a Globus `TransferData` submission, and maps Globus task status back into
CORA's `TransferState`. CORA owns the seam; this adapter is an ACL that speaks
Globus on one side and CORA vocabulary on the other.

The Globus client is synchronous (it speaks HTTP via `requests`), so every
call is run in a worker thread (`asyncio.to_thread`) to keep the async port
contract: the event loop is never blocked on a network round-trip.

## Status mapping

Globus reports exactly four task statuses; CORA's `TransferState` adds the
Pending/Cancelled framing the engine needs:

- `ACTIVE`    -> `Active`
- `INACTIVE`  -> `Suspended` (Globus only enters INACTIVE on credential
  expiry, which is exactly CORA's intervention-required state)
- `SUCCEEDED` -> `Succeeded`
- `FAILED`    -> `Failed`

A partial move has no native Globus terminal: a sync that skips unchanged
files still ends `SUCCEEDED`, and a genuine partial ends `FAILED` carrying
`subtasks_failed > 0` alongside `files_transferred > 0`. That is exactly the
counts-on-`TransferProgress` partial signal the port models, so no enum value
is needed. A caller-issued `cancel` lands the Globus task in `FAILED`; Globus
does not distinguish it from a fault on the status alone, which the port
explicitly allows ("Failed on a substrate that does not distinguish the two").

## Error mapping

Globus transport failures (`NetworkError` and its connection / timeout
subclasses) become `TransferEndpointUnreachableError`: the substrate did not
answer. Globus API errors (`GlobusAPIError`) are dispatched on `http_status`:
401 / 403 -> `TransferAccessDeniedError`, 5xx -> `TransferEndpointUnreachableError`,
and everything else the substrate refused (400 / 404 / 409 / 429 / ...) ->
`TransferRejectedError`. This adapter does not raise `TransferTimeoutError`
(a transport timeout folds into unreachable, since the adapter sets no await
ceiling of its own) nor `TransferIntegrityError` (a verify-on-arrival mismatch
surfaces as a `Failed` observation carrying the substrate's fatal-error text,
not an exception); both stay available for adapters that need them.

## Not run against live Globus

The adapter is unit-tested against a fake `TransferClient`; it has not been
exercised against a real Globus endpoint (that needs credentials and two live
collections). Treat live behaviour as unverified until a sanity run happens.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal, Protocol

from globus_sdk import MISSING, GlobusAPIError, NetworkError, TransferData

from cora.operation.ports.transfer_port import (
    TransferAccessDeniedError,
    TransferEndpointUnreachableError,
    TransferHandle,
    TransferProgress,
    TransferRejectedError,
    TransferRequest,
    TransferState,
)

SyncLevel = Literal["exists", "size", "mtime", "checksum"]
"""Globus sync levels in ascending strictness. `skip_unchanged` maps to one of
these; `checksum` is the default because CORA's "do not re-move identical
bytes" intent is a byte-identity claim, which only the checksum level
guarantees (the cheaper levels compare size or mtime)."""

_STATUS_TO_STATE: dict[str, TransferState] = {
    "ACTIVE": TransferState.ACTIVE,
    "INACTIVE": TransferState.SUSPENDED,
    "SUCCEEDED": TransferState.SUCCEEDED,
    "FAILED": TransferState.FAILED,
}


class _TransferResponse(Protocol):
    """The slice of a Globus HTTP response this adapter reads.

    A `globus_sdk.response.GlobusHTTPResponse` satisfies this structurally, and
    so does a test double, so the adapter depends on the read shape rather than
    the concrete response class.
    """

    def __getitem__(self, key: str) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...


class GlobusTransferClient(Protocol):
    """The slice of `globus_sdk.TransferClient` this adapter calls.

    Owning the seam (rather than depending on the concrete client) keeps the
    adapter unit-testable with a fake and pins exactly the three methods CORA
    relies on. The real client satisfies it structurally; the TYPE_CHECKING
    assertion below fails the type-check if it ever drifts.
    """

    def submit_transfer(self, data: TransferData) -> _TransferResponse: ...
    def get_task(self, task_id: str) -> _TransferResponse: ...
    def cancel_task(self, task_id: str) -> _TransferResponse: ...


if TYPE_CHECKING:
    from typing import cast

    import globus_sdk
    from globus_sdk import MissingType

    # Static-only conformance: pyright fails here if the real Globus
    # TransferClient ever drifts from the GlobusTransferClient seam.
    _CLIENT_CONFORMANCE: GlobusTransferClient = cast("globus_sdk.TransferClient", ...)


def _split_location(location: str) -> tuple[str, str]:
    """Split a CORA `endpoint:path` location into (endpoint_id, path).

    Raises `TransferRejectedError` on a malformed location before any network
    call, so an authoring error fails fast rather than reaching Globus.
    """
    endpoint, separator, path = location.partition(":")
    if not separator or not endpoint or not path:
        msg = f"location {location!r} is not in 'endpoint:path' form"
        raise TransferRejectedError(msg)
    return endpoint, path


def _classify_api_error(
    http_status: int, code: str | None, message: str, *, endpoint: str
) -> Exception:
    """Map a Globus API error's HTTP status to a CORA transfer error.

    Pure (no Globus types), so the mapping is unit-tested directly with plain
    status codes. 401 / 403 are access denials; 5xx are the substrate failing
    to serve (unreachable); everything else is the substrate refusing this
    particular request.
    """
    if http_status in (401, 403):
        return TransferAccessDeniedError(endpoint)
    if http_status in (500, 502, 503, 504):
        return TransferEndpointUnreachableError(endpoint)
    reason = f"{code or http_status}: {message}" if message else f"{code or http_status}"
    return TransferRejectedError(reason)


def _map_task_status(response: _TransferResponse) -> TransferProgress:
    """Translate a Globus get_task response into a CORA `TransferProgress`."""
    status = response["status"]
    state = _STATUS_TO_STATE.get(status, TransferState.ACTIVE)
    detail: str | None = None
    if state is TransferState.FAILED:
        fatal = response.get("fatal_error")
        if fatal:
            detail = fatal.get("description") or fatal.get("code")
    elif state is TransferState.SUSPENDED:
        detail = response.get("nice_status")
    return TransferProgress(
        state=state,
        bytes_moved=response.get("bytes_transferred", 0),
        files_total=response.get("files"),
        files_moved=response.get("files_transferred", 0),
        files_skipped=response.get("files_skipped", 0),
        files_failed=response.get("subtasks_failed", 0),
        detail=detail,
    )


class GlobusTransferPort:
    """`TransferPort` backed by an injected Globus `TransferClient`.

    Construct with an already-authorized client; the adapter never builds the
    authorizer. `skip_unchanged_sync_level` chooses how a `skip_unchanged`
    request is realized (default `checksum`, the byte-identity guarantee).
    """

    def __init__(
        self,
        client: GlobusTransferClient,
        *,
        skip_unchanged_sync_level: SyncLevel = "checksum",
    ) -> None:
        self._client = client
        self._skip_unchanged_sync_level: SyncLevel = skip_unchanged_sync_level

    async def begin(self, request: TransferRequest) -> TransferHandle:
        source_endpoint, source_path = _split_location(request.source)
        destination_endpoint, destination_path = _split_location(request.destination)
        sync_level: SyncLevel | MissingType = (
            self._skip_unchanged_sync_level if request.skip_unchanged else MISSING
        )
        data = TransferData(
            source_endpoint=source_endpoint,
            destination_endpoint=destination_endpoint,
            label=request.label if request.label is not None else MISSING,
            submission_id=request.idempotency_key
            if request.idempotency_key is not None
            else MISSING,
            sync_level=sync_level,
            verify_checksum=request.verify_on_arrival,
        )
        data.add_item(source_path, destination_path, recursive=request.recursive)
        context = f"{request.source} -> {request.destination}"
        response = await self._invoke(self._client.submit_transfer, data, context=context)
        return TransferHandle(str(response["task_id"]))

    async def observe(self, handle: TransferHandle) -> TransferProgress:
        response = await self._invoke(self._client.get_task, str(handle), context=str(handle))
        return _map_task_status(response)

    async def cancel(self, handle: TransferHandle) -> None:
        await self._invoke(self._client.cancel_task, str(handle), context=str(handle))

    async def aclose(self) -> None:
        """No-op: the injected client's lifecycle is the composition root's."""

    async def _invoke(self, call: Any, *args: Any, context: str) -> _TransferResponse:
        """Run a synchronous Globus call off the event loop and map its failures."""
        try:
            return await asyncio.to_thread(call, *args)
        except NetworkError as exc:
            raise TransferEndpointUnreachableError(context) from exc
        except GlobusAPIError as exc:
            raise _classify_api_error(
                getattr(exc, "http_status", 0),
                getattr(exc, "code", None),
                getattr(exc, "message", "") or str(exc),
                endpoint=context,
            ) from exc


__all__ = ["GlobusTransferClient", "GlobusTransferPort", "SyncLevel"]
