"""Where a probe refusal came from, which decides how a caller reacts.

A caller sweeping a population of items has to tell two failures apart,
and the refusal text cannot tell it: "this one request was malformed"
and "the hop is down" both arrive as a `ProbeError` with a sentence in
it. Conflating them costs something either way. Treating a dead hop as
per-item walks every remaining item into the same timeout; treating a
malformed request as systemic lets one bad item wedge the whole sweep
permanently, which is the head-of-line blocking a gate review already
removed from `CaptureScanIngestor` once.

So the origin travels with the refusal instead of being inferred. It is
set by the client adapter that knows which side failed, never by the
remote process: everything the remote says arrived over a transport
that demonstrably works.

Shared rather than owned by either end for the same reason
`is_safe_path_segment` is: the value is a contract between two modules
that must not drift, and a literal copied into both drifts the first
time one of them is edited alone.
"""

PROBE_ERROR_ORIGIN_CLIENT = "client"
"""The request was refused before the transport was touched, so it says
nothing about whether the next request will succeed. Per-item."""

PROBE_ERROR_ORIGIN_TRANSPORT = "transport"
"""The hop itself failed: could not launch, timed out, or exited
non-zero. The next request will hit the same thing. Systemic."""

__all__ = ["PROBE_ERROR_ORIGIN_CLIENT", "PROBE_ERROR_ORIGIN_TRANSPORT"]
