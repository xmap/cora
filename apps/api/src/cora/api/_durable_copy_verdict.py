"""What a `locate` verdict means, decided apart from acting on it.

The remote probe reports what it found and judges nothing. This module
holds the judgement, and only the judgement: no IO, no clock, no
subprocess. That separation is the point. These two rules were chosen
deliberately and they are the ones most likely to be quietly altered by
someone fixing something else, so they live where a test can pin them
without standing up a sweep.

## The two rules

**No match means keep waiting, not give up.** The durable copy appears
days after the scan, and only when an operator makes it, so "not there"
is the normal state for a while and is not an error. The Dataset stays
a candidate and the next sweep looks again. There is deliberately no
expiry: a bounded window would silently drop a genuinely late copy,
which is the failure that actually costs data.

**Several matches means refuse, and say which.** Guessing would record
the wrong bytes as the durable copy of this Dataset, permanently, in a
log that cannot be edited. This is not a defensive edge case. Measured
on the real archive: internal beamtime carries no proposal number, so
DMagic names every such folder `...-0`, and 8 of the last 14 months
hold more than one. The filename usually separates them, and in
`2026-02` three internal folders share 45 filenames and it does not.
Expect this to fire roughly one month in eight, which is why the
refusal has to name the colliding folders: an operator who cannot see
WHICH experiments collided cannot resolve it.

## Why the refusal carries paths at all

Those paths embed a PI surname. They are carried here so the caller can
put them in front of a human, and the caller is responsible for routing
them somewhere erasable rather than into a log sink. Naming the
collision is what makes the refusal actionable, and an unactionable
refusal on a recurring case is just a stuck sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True)
class DurableCopyFound:
    """Exactly one candidate file matched."""

    path: str
    """Personal data: embeds the PI surname through the experiment
    folder. Bound for the capture-path vault, never a log line."""


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
    """The TRUE count, which may exceed `len(paths)` because the probe
    caps how many paths one verdict carries. Reported separately so an
    operator sees two versus fifty rather than a truncated list that
    reads like the whole story."""
    paths: tuple[str, ...]
    """Personal data, and the whole value of this verdict: the operator
    needs to see which experiment folders collided."""


@dataclass(frozen=True)
class DurableCopyUnreachable:
    """The probe could not answer: SSH failed, timed out, or refused
    the request. Distinct from "not there", because a Dataset must not
    be treated as merely waiting when CORA never actually looked."""

    detail: str
    """The probe's own refusal text, which by that module's contract
    never carries the searched path."""


DurableCopyVerdict = (
    DurableCopyFound | DurableCopyNotYetThere | DurableCopyAmbiguous | DurableCopyUnreachable
)


def read_locate_response(response: dict[str, object]) -> DurableCopyVerdict:
    """Turn one raw `locate` response into a decision.

    A response that is not a well-formed `Located` verdict is
    `DurableCopyUnreachable`, never `DurableCopyNotYetThere`. The two
    are easy to conflate and must not be: "we looked and it is not
    there yet" is a Dataset quietly waiting, while "we could not look"
    is a deployment that may be failing every sweep and needs to be
    visible as such.
    """
    if response.get("kind") != "Located":
        detail = response.get("detail")
        return DurableCopyUnreachable(
            detail=detail if isinstance(detail, str) else "probe returned no usable verdict"
        )

    raw_count = response.get("match_count")
    raw_paths = response.get("paths")
    if not isinstance(raw_count, int) or not isinstance(raw_paths, list):
        return DurableCopyUnreachable(detail="probe verdict is missing its match count or paths")
    paths = tuple(entry for entry in cast("list[object]", raw_paths) if isinstance(entry, str))

    if raw_count == 0:
        return DurableCopyNotYetThere()
    if raw_count == 1 and len(paths) == 1:
        return DurableCopyFound(path=paths[0])
    if raw_count == 1:
        # One match counted but no usable path came back. Treating this
        # as "not there" would let the Dataset wait forever on a probe
        # that is answering incoherently.
        return DurableCopyUnreachable(detail="probe counted one match but returned no path")
    return DurableCopyAmbiguous(match_count=raw_count, paths=paths)


__all__ = [
    "DurableCopyAmbiguous",
    "DurableCopyFound",
    "DurableCopyNotYetThere",
    "DurableCopyUnreachable",
    "DurableCopyVerdict",
    "read_locate_response",
]
