"""`cora-capture-path://` locators: indirect references CORA mints so an
automated ingest never writes a personal-data path onto an event.

## Why this exists

2-BM's directory layout embeds `{PIlastname}-{GUP#}` (a real person's
surname) in every scan path. `DatasetRegistered.uri` /
`DistributionRegistered.uri` are immutable, INSERT-only event fields
with no erasure path today. A human pasting a path into the ordinary
`ingest_scan` POST route has always been able to do this; `slice 17`'s
`CaptureScanIngestor` makes it automatic and unconditional, for every
run, which is the difference that makes it worth closing rather than
accepting.

The disposition table (`cora.infrastructure.record_export._dispositions`)
already drops `uri` from the published, redacted record, and has no
person-name field anywhere else. This scheme is what keeps that true of
the INTERNAL record too: `mint_capture_path_locator` is the only thing
`CaptureScanIngestor` calls to build a locator, so the automated path
never constructs a `file://` URI carrying the real, personal-data path.

## Structured, not opaque

The real path is never in the locator; the personal segment is replaced
with a `run-<uuid>` token resolved through `run_capture_path` (the
same erasable vault `capture_path.py` already keeps `observed_path`
in, for the identical reason -- see that module's docstring). Host and
tier stay visible because neither is personal data and both are real
provenance a reader benefits from, unlike a fully opaque
`cora-capture-path://<uuid>`.

Keeping them structured has two consequences. `_filename_of`
(ingest_scan's own Dataset-naming helper) keeps working unmodified,
because the locator's last path segment is still a real filename. And
host and tier are LOAD-BEARING at resolve time: they are the key this
module looks the vault row up by, since a Run may hold one row per
storage location (acquisition tier, archive tier) and a locator naming
one must never resolve to the other's bytes.

That is a change from this module's first version, which keyed the
lookup on `run_id` alone and argued that re-verifying host and tier
would be decorative -- correctly, at the time: both had been chosen
unilaterally at mint time from the same settings a resolve-time check
would have compared against, and a check against your own output is
not independent (see [[project_independent_check_principle]]). Once the
vault holds more than one row per Run, they stop being a self-comparison
and become a genuine selector against independently written rows.

The filename comparison remains the module's other real cross-check:
its two sides come from separate reads (the candidate query at mint
time, a fresh `get` at resolve time), so a drift between them is a
signal rather than decoration.

## Scope

Understood ONLY by `ingest_scan`'s own read path (this module's
`resolve`, called once from its handler). `record_attestation`'s
checksum verifier map (`cora.data.wire._build_checksum_verifiers`) has
no entry for this scheme and never will as part of this slice:
verifying a Distribution registered through the SSH transport is a
pre-existing gap this slice does not create or widen (no
`ChecksumVerifier` exists for a plain SSH-sourced `file://` Distribution
either, and `SshPosixChecksumComputer`'s own docstring already deferred
building one "per the rule-of-three"). Also NOT registered with
`launch_argv`'s allowed schemes or the compute port's path resolver: a
recipe or job spec must not reference an indirect locator directly.
Nothing today wires a Dataset/Distribution URI into a launch spec
automatically, so this is a documented boundary, not a fitness test.

## Residual risk: `resolve` is a pass-through, not an authorization check

`resolve` is called unconditionally on every `IngestScan` locator, not
only the ones `CaptureScanIngestor` mints. A caller of the ordinary POST
route or MCP tool who is authorized for `IngestScan` (but review this
against whatever else that principal holds) could hand-craft a
`cora-capture-path://.../run-<uuid>/<filename>` string naming a DIFFERENT
run than the one they intend, and have `ingest_scan` read, digest, and
register a Dataset from THAT run's real bytes -- `run_id` is not
brute-forceable, but is exposed to any `GetRun`-authorized caller via
`observed_capture_path`, and the filename-match check this module makes
(see above) only catches accidental drift, not a caller who already
knows both. If that same principal already holds `GetRun`, this adds no
new confidentiality capability (they could already read the real path
directly); the residual case is a principal authorized for `IngestScan`
without also being authorized to read Run capture paths. Fixing this
structurally would mean identity-gating this scheme to the one pinned
agent principal that is supposed to mint it, which would couple this
Data BC module to an `cora.api`/`cora.agent`-owned identity constant --
a worse cross-layer dependency than the risk it would close. Deployments
should keep `IngestScan` and Run capture-path read access commensurately
scoped rather than relying on this module to enforce that boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote, unquote, urlparse
from uuid import UUID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.run.aggregates.run import CapturePath


class CapturePathLookup(Protocol):
    """The one method this module ever calls on Run BC's `CapturePathStore`.

    A consumer-local narrowing, in the spirit of the
    port-shaped-by-consumer convention though not the same shape as it:
    `ClearanceLookup`/`SupplyLookup`/`DatasetDistributionLookup` are
    Kernel-injected cross-BC ports in `cora.infrastructure.ports`,
    satisfied by an adapter in the owning BC. This is narrower than
    that, a Protocol declared where it is consumed over a concrete
    class, and hoisting it for one consumer would be premature. The
    principle it borrows is only that the CONSUMER shapes the surface
    it actually uses, even though `cora.data`
    is separately sanctioned to import the full `CapturePathStore`
    Protocol directly (`tach.toml` already permits `cora.data` ->
    `cora.run.aggregates`). That sanctioned IMPORT PATH is not a license
    to require more surface than this module calls: `resolve` only ever
    reads, so requiring a caller to also supply `upsert` would be
    asking for capability this module has no use for and no business
    depending on. `PostgresCapturePathStore` / `InMemoryCapturePathStore`
    satisfy this structurally, unchanged.
    """

    async def get(
        self, run_id: UUID, *, host: str | None, root: str | None
    ) -> CapturePath | None: ...


CAPTURE_PATH_SCHEME = "cora-capture-path"

_RUN_SEGMENT_PREFIX = "run-"


def active_scan_transport(deps: Kernel) -> tuple[str, tuple[str, ...]]:
    """(host_label, configured_roots) for whichever transport
    `cora.data.wire._build_scan_ingest_pair` would select for this
    deployment.

    Shared by both callers -- minting here, pair selection in
    `wire.py` -- so a locator's host/tier segments always describe the
    SAME transport that will actually read it, rather than two copies
    of this conditional drifting apart under a future settings change.
    """
    host = deps.settings.scan_probe_remote_host
    if host is not None:
        return host, deps.settings.scan_probe_allowed_roots
    return "localhost", deps.settings.posix_checksum_roots


def mint_capture_path_locator(
    *,
    observed_path: str,
    run_id: UUID,
    host: str | None,
    root: str | None,
) -> str | None:
    """Build an indirect `cora-capture-path://` locator for `observed_path`.

    `host` and `root` are the location the VAULT ROW RECORDED at
    observation time, not a fresh match against current settings. That
    is the point: `resolve` looks the row up by exactly these two
    values, so deriving them here from settings that may have moved
    since the row was written would mint a locator that resolves to
    nothing, silently. Passing the row's own location makes the two
    sides the same fact rather than two reads of a mutable one.

    Returns `None` when either is `None`, which is how a row observed
    under no configured root (or written before the vault recorded
    location at all) declines to produce a locator instead of getting a
    fabricated one. The caller (only `CaptureScanIngestor` today)
    treats `None` as this candidate is stuck, mirroring its existing
    missing-binding SKIP.

    The personal segment is never inspected: everything strictly
    between the matched root and the filename is discarded, regardless
    of how many directory levels it spans or what it is named. This is
    what makes the scheme correct for any facility's layout, not just
    2-BM's `{PIlastname}-{GUP#}` convention.

    CAUTION for whoever configures the storage roots: `root` is
    embedded in the locator VERBATIM, trusted as safe with no way for
    this function to verify that from the string alone. Configured
    roots MUST name the facility-level storage tier (`/local1/2BM`),
    never a path that itself contains personal data (an experiment
    folder). A root
    misconfigured to the latter would leak that data into the locator's
    supposedly-safe tier segment, defeating this module's whole purpose.

    At 2-BM this is a live hazard rather than a hypothetical: alongside
    the beamline tree at `<tier>/2BM/`, the analysis tiers carry
    per-person workspaces directly at their root (`/data3/vnikitin`,
    `/data3/sboyer`), so a root pointed at one of those would embed a
    username. The correct roots there are `<tier>/2BM` exactly. How
    many levels sit below that root is irrelevant here, which is just
    as well, because it varies: the experiment folder is nested under a
    year-month on `/data2` and flat on `/local2`.
    """
    if host is None or root is None:
        return None
    filename = Path(observed_path).name
    return f"{CAPTURE_PATH_SCHEME}://{host}{root}/{_RUN_SEGMENT_PREFIX}{run_id}/{quote(filename)}"


async def resolve_capture_path_locator(
    locator: str,
    *,
    capture_path_store: CapturePathLookup,
) -> str | None:
    """Resolve `locator` to the real `file://` URI the scan reader /
    checksum computer can act on.

    Pass-through for every scheme other than `cora-capture-path`: the manual
    `ingest_scan` POST route and MCP tool keep sending real `file://`
    URIs directly, unaffected by this module, per the scope decision
    that only the automated sweep mints indirect locators.

    Returns `None` -- never a reason string -- on every failure mode
    (malformed locator; no vault row at all; a row that exists but not
    at the location the locator names; filename mismatch), so a caller
    cannot accidentally log or surface anything that touches
    `observed_path`. The vault row's absence is treated the same as a
    malformed locator: this is also what an erasure would look like
    once a forget-style slice calls `CapturePathStore`'s (currently
    unused) `DELETE` grant, so refusing quietly here is already the
    right behavior for that future, not a placeholder for it.
    """
    parsed = urlparse(locator)
    if parsed.scheme != CAPTURE_PATH_SCHEME:
        return locator

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None
    run_segment, filename_segment = segments[-2], segments[-1]
    host = parsed.netloc
    root = "/" + "/".join(segments[:-2]) if len(segments) > 2 else ""
    if not run_segment.startswith(_RUN_SEGMENT_PREFIX):
        return None
    try:
        run_id = UUID(run_segment[len(_RUN_SEGMENT_PREFIX) :])
    except ValueError:
        return None

    row = await capture_path_store.get(run_id, host=host, root=root)
    if row is None:
        return None

    # The one genuine cross-check this module makes: the filename
    # minted into the locator (read from the vault at candidate-lookup
    # time) against the vault's OWN current basename (a fresh read).
    # Host and tier are the LOOKUP KEY above, not a post-hoc
    # comparison; see the module docstring.
    if Path(row.observed_path).name != unquote(filename_segment):
        return None

    return "file://" + quote(row.observed_path)


__all__ = [
    "CAPTURE_PATH_SCHEME",
    "CapturePathLookup",
    "active_scan_transport",
    "mint_capture_path_locator",
    "resolve_capture_path_locator",
]
