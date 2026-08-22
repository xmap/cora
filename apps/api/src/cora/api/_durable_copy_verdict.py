"""What a `locate` verdict means, decided apart from acting on it.

The remote probe reports what it found and judges nothing. This module
holds the judgement, and only the judgement: no IO, no clock, no
subprocess. That separation is the point. These rules were chosen
deliberately and they are the ones most likely to be quietly altered by
someone fixing something else, so they live where a test can pin them
without standing up a sweep.

## The three rules

**No match means keep waiting, not give up.** The durable copy appears
days after the scan, and only when an operator makes it, so "not there"
is the normal state for a while and is not an error. The Dataset stays
a candidate and the next sweep looks again. There is deliberately no
expiry: a bounded window would silently drop a genuinely late copy,
which is the failure that actually costs data.

**Several matches means refuse, and report how many.** Guessing would
record the wrong bytes as the durable copy of this Dataset,
permanently, in a log that cannot be edited. This is not a defensive
edge case. Measured on the real archive: internal beamtime carries no
proposal number, so DMagic names every such folder `...-0`, and 8 of
the last 14 months hold more than one. The filename usually separates
them, and in `2026-02` three internal folders share 45 filenames and it
does not. Expect this to fire roughly one month in eight. The count is
reported and the colliding paths are NOT, for the reason set out below.

**A failure to look is either this one request's problem or the hop's,
and they are not the same verdict.** `DurableCopyRefused` means the
probe declined THIS request; every other Dataset is unaffected and a
sweep must carry on to them. `DurableCopyUnreachable` means the
transport itself failed, so the next request will fail identically and
a sweep gains nothing by trying. Collapsing the two into one verdict
is what lets a single misconfigured Dataset wedge an entire sweep
permanently, which is the head-of-line blocking a gate review already
removed from `CaptureScanIngestor` once. The distinction is not
inferred from the refusal text: it is carried explicitly as `origin`
(`cora.shared.probe_error`) by the client adapter, which is the only
party that knows whether it reached the transport at all.

Anything without an explicit transport origin reads as `Refused`. That
default is deliberate and is the fail-safe direction: over-reporting
per-request costs one wasted probe, while over-reporting systemic
stops a sweep that had no reason to stop.

## Why the ambiguous verdict does NOT carry the colliding paths

It did, and the reasoning was that an operator who cannot see WHICH
folders collided cannot resolve the collision. That reasoning is
sound and the field was still wrong, because the operator read it was
carried for does not exist: the only consumer logs the count and drops
the paths. What remained was a tuple of personal data with no reader,
one keyword away from a log call, justified by a future.

So the paths are dropped rather than held. When the authenticated
operator read is built it will re-probe anyway, since a collision an
hour old may already have been resolved on disk, and a value object
cannot be the place personal data waits for a consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from cora.shared.probe_error import PROBE_ERROR_ORIGIN_TRANSPORT


@dataclass(frozen=True)
class DurableCopyFound:
    """Exactly one candidate file matched."""

    path: str
    """Personal data: embeds the PI surname through the experiment
    folder. Bound for the capture-path vault, never a log line."""
    modified_at: datetime
    """The FILE's own modification time as the substrate reports it,
    not CORA's clock. It is what the capture-path vault's `observed_at`
    column means, and only the probing host can read it. Carrying it
    also makes a retry idempotent, since that vault's upsert is
    monotonic in `observed_at` and an unchanged file re-probes to the
    same value."""


@dataclass(frozen=True)
class DurableCopyNotYetThere:
    """Nothing matched. The normal state until an operator copies the
    experiment, so the Dataset stays a candidate and no reason is
    carried: there is nothing wrong to report."""


@dataclass(frozen=True)
class DurableCopyAmbiguous:
    """More than one candidate matched, so CORA cannot tell which holds
    this Run's file."""

    match_count: int
    """How many experiment folders held a file of this name. The TRUE
    count, uncapped, so an operator sees two versus fifty rather than
    the handful the probe chose to send back."""


@dataclass(frozen=True)
class DurableCopyRefused:
    """The probe declined THIS request: a malformed value, a root
    outside the allowlist, or an answer that did not parse. Scoped to
    one Dataset, so a sweep skips it and carries on to the next."""

    detail: str
    """The refusal text. Never carries the searched path: client-side
    refusals are fixed strings, and the remote renders exception TYPES
    rather than messages precisely so a filesystem error cannot leak
    the filename it failed on."""


@dataclass(frozen=True)
class DurableCopyUnreachable:
    """The transport failed: ssh would not launch, timed out, or exited
    non-zero. The next request fails identically, so a sweep stops
    rather than walking its whole population into the same timeout."""

    detail: str
    """The transport's own failure text. Carries no searched path for
    the same reason as `DurableCopyRefused.detail`."""


DurableCopyVerdict = (
    DurableCopyFound
    | DurableCopyNotYetThere
    | DurableCopyAmbiguous
    | DurableCopyRefused
    | DurableCopyUnreachable
)


def read_locate_response(response: dict[str, object]) -> DurableCopyVerdict:
    """Turn one raw `locate` response into a decision.

    A response that is not a well-formed `Located` verdict is never
    `DurableCopyNotYetThere`. The two are easy to conflate and must not
    be: "we looked and it is not there yet" is a Dataset quietly
    waiting, while "we could not look" is a deployment that may be
    failing every sweep and needs to be visible as such.
    """
    if response.get("kind") != "Located":
        return _failure(response)

    raw_count = response.get("match_count")
    raw_matches = response.get("matches")
    if not isinstance(raw_count, int) or not isinstance(raw_matches, list):
        return DurableCopyRefused(detail="probe verdict is missing its match count or matches")
    matches = [
        cast("dict[str, object]", entry)
        for entry in cast("list[object]", raw_matches)
        if isinstance(entry, dict)
    ]

    if raw_count < 0:
        # Not reachable from the probe as written, and refused rather
        # than left to fall through: a negative count that reached the
        # single-match branch below with one entry present would be read
        # as `Found` and record those bytes permanently.
        return DurableCopyRefused(detail="probe reported a negative match count")
    if raw_count == 0:
        return DurableCopyNotYetThere()
    if raw_count > 1:
        return DurableCopyAmbiguous(match_count=raw_count)

    if len(matches) != 1:
        # One match counted but nothing usable came back. Treating this
        # as "not there" would let the Dataset wait forever on a probe
        # that is answering incoherently.
        return DurableCopyRefused(detail="probe counted one match but returned no usable entry")
    path = matches[0].get("path")
    modified_at = matches[0].get("modified_at")
    if not isinstance(path, str) or not isinstance(modified_at, int | float):
        return DurableCopyRefused(detail="probe's single match is missing its path or timestamp")
    if isinstance(modified_at, bool):
        # `bool` is an `int` in Python, and `True` would silently become
        # 1970-01-01 rather than being refused.
        return DurableCopyRefused(detail="probe's single match is missing its path or timestamp")
    return DurableCopyFound(path=path, modified_at=datetime.fromtimestamp(modified_at, tz=UTC))


def _failure(response: dict[str, object]) -> DurableCopyRefused | DurableCopyUnreachable:
    detail = response.get("detail")
    text = detail if isinstance(detail, str) else "probe returned no usable verdict"
    if response.get("origin") == PROBE_ERROR_ORIGIN_TRANSPORT:
        return DurableCopyUnreachable(detail=text)
    return DurableCopyRefused(detail=text)


__all__ = [
    "DurableCopyAmbiguous",
    "DurableCopyFound",
    "DurableCopyNotYetThere",
    "DurableCopyRefused",
    "DurableCopyUnreachable",
    "DurableCopyVerdict",
    "read_locate_response",
]
