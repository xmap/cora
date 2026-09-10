"""State, status enum, reason enum and errors for the Shortfall aggregate.

A Shortfall is the recorded fact that a capture PRODUCED SOMETHING THAT
CAN NEVER BECOME A DATASET. It is not a re-judgement of the act: the
Run's own terminal stands untouched, faithfully transcribing what the
substrate reported. This records a fact about the PRODUCT.

## Why this exists

Before this aggregate, CORA's record could not distinguish "no scan
ran" from "a scan ran and produced nothing". Both looked identical: a
terminated Run with no Dataset naming it. Three real 2-BM Runs hold
HDF5 files carrying 1 projection of a commanded 1541 and no
`/exchange/theta`, and the sweep retried them 387 times in one recent
log window, at a measured 6.3s per attempt, writing nothing each time.
The reader had already computed the frame counts and discarded them at
the refusal, so CORA threw away its only non-substrate evidence
precisely when that evidence DISAGREED with the substrate. See
tomoscan#181 for why "Scan complete" is reported on every exit path,
and therefore why a `Completed` Run is a faithful transcript and a
false record at the same time.

## Terminal at genesis

Same fact-chain shape as `Acquisition` and `Attestation`: one stream per
Shortfall, exactly one `ShortfallRecorded` event ever, no lifecycle and
no transition arm. A capture that is later ingested by hand does NOT
retract this: both facts stand, because both are true. The file really
did lack its rotation angles when CORA looked, and a human really did
supply what was missing afterwards.

## Finality is what makes the claim safe to make

"Can never become a Dataset" is unfalsifiable unless the record says
how it was reached, so the state and the event carry BOTH sides of the
judgement (`file_modified_at`, `run_ended_at`) rather than only the
verdict. A reader can re-derive the verdict from the payload without
going back to the file, which matters because the file sits on a
detector control PC that may not exist in five years, and because this
row can never be erased.

## Personal data

`capture_path_id` is the surrogate key of the `run_capture_path` vault
row, NOT the path. `host` and `root` are the facility-level storage
tier (`tomdet`, `/local1/2BM`), which is provenance a reader benefits
from and which `capture_path_locator` already argues is safe to carry
in the clear. Everything strictly between the root and the filename,
which at 2-BM embeds `{UserLastName}-{ProposalNumber}`, never reaches
this aggregate at all.

Both land as `drop:text` in the generated redaction table, because they
are bare `str` and the generator cannot tell a storage tier from free
text. That is not a defect to work around: the same already holds for
`AttestationRecorded.kind` / `.outcome`, and dropping a facility's
internal hostname from the PUBLISHED record is the right default even
though carrying it on the internal event is safe. Anyone tempted to add
an override should have a reason to publish them, not just a wish for
symmetry.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.identity import ActorId


class ShortfallStatus(StrEnum):
    """The Shortfall's lifecycle state.

    Single-valued and terminal at genesis, mirroring
    `AcquisitionStatus`. Not carried in the event payload: the event
    type encodes it, same precedent as the rest of the codebase.
    """

    RECORDED = "Recorded"


class ShortfallReason(StrEnum):
    """Why this capture can never become a Dataset.

    A CLOSED enum, deliberately: the free-text refusal messages
    `InvalidScanFileError` carries embed the opened path verbatim (they
    are built from `os.stat` / h5py error strings), and this row is
    unerasable. A closed enum cannot carry a path by construction,
    which is the whole reason the payload names a member here instead
    of a rendered message.

    One member today, and the space is deliberately unfilled rather
    than overlooked. `ScanFileInvalidReason` marks several of its nine
    members permanent, but only this one has ever been OBSERVED, and
    only this one can supply the frame counts that make the record
    worth writing: an `Unrecognized` file yields no `Description` at
    all, so a Shortfall for it would carry a verdict and no evidence.
    Adding that member is a modelling decision about what a countless
    Shortfall means, not a mechanical widening, so it waits for a real
    instance to reason from.
    """

    STRUCTURALLY_INCOMPLETE = "StructurallyIncomplete"


@dataclass(frozen=True)
class Shortfall:
    """Aggregate root: one capture that can never become a Dataset.

    `capture_path_id` identifies the observation this verdict is about,
    and is what the stream is keyed on, so a Run observed under two
    storage locations can carry a separate verdict per location. That
    matches `ScanIngestCandidateLookup`'s own `exclude` key, which is
    scoped the same way and for the same reason.

    `projection_count` is what the file actually holds;
    `commanded_projection_count` is what the scan was told to collect,
    and is `None` when the file does not record it. The pair is the
    substance of the fact: 1 of a commanded 1541 is the shape that
    motivated this aggregate. `dropped_frame_count` is the detector's
    own count of frames it discarded, again `None` when absent, and is
    a SEPARATE fact from the shortfall between the other two: a scan
    can fall short with zero drops (it stopped early) or drop frames
    and still meet its total.

    `file_modified_at` and `run_ended_at` are the two sides of the
    finality judgement, kept so the verdict stays checkable. See the
    module docstring.
    """

    id: UUID
    producing_run_id: UUID
    capture_path_id: UUID
    host: str
    root: str
    projection_count: int
    commanded_projection_count: int | None
    dropped_frame_count: int | None
    reason: ShortfallReason
    file_modified_at: datetime
    run_ended_at: datetime
    recorded_at: datetime
    recorded_by: ActorId
    status: ShortfallStatus = ShortfallStatus.RECORDED
