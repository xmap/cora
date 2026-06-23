"""Dataset aggregate state, value objects, status enum, and domain errors.

`Dataset` is the logical research data product, not the bytes
themselves. Bytes live wherever the URI points (S3 / Globus /
POSIX / etc.); the Data BC stores only the metadata: identity,
URI, checksum, byte_size, encoding, lineage, and the cross-aggregate
references back to whatever produced or describes the data.

## What a Dataset is NOT

  - Not the bytes (those live at the URI)
  - Not a substream entry (per-projection rows live in a future
    Run samples logbook with the dataset URI as a column; one
    Dataset = one logical product, not one Dataset per projection)
  - Not a Transfer record (Transfer is a separate aggregate,
    deferred to its own phase)


Minimal Dataset: id + name + uri + checksum + byte_size + encoding
+ optional cross-refs (producing_run_id, producing_procedure_id,
subject_id, derived_from) + status (defaults `Registered`).

7a shipped Registered as the genesis state. 7b adds the Discarded
terminal: a Registered Dataset can transition to Discarded with a
free-form reason (1-500 chars; mirrors stop_run / abort_run /
truncate_run shape). Discarded is GDPR-shaped: bytes at the URI
have been deleted from storage but the metadata record + reason are
retained for audit. Re-discarding raises (strict-not-idempotent).

7b also tightens the lineage invariant: registering a Dataset with
`derived_from` referencing any Discarded Dataset raises
`DerivedFromDatasetsDiscardedError` (we don't allow new lineage
edges into bytes that no longer exist).

Archive / Verify / Move transitions defer until storage tiers /
re-checksum workflows ship.

## Encoding as structured VO (gate-review L3 refinement, 2026-05-11)

`encoding` is a small VO: `media_type: str` (loose MIME-type-ish
string) plus `conforms_to: frozenset[str]` (zero or more profile
URIs the Dataset claims to conform to, for example
`https://manual.nexusformat.org/...` or `https://ngff.openmicroscopy.org/0.4/`).
This matches schema.org's `encodingFormat` + `conformsTo` pair and
RO-Crate 1.2's pattern. The free-form-string-only alternative was
the original draft, but the standards survey showed real Datasets
can claim multiple profiles (NeXus + OME-Zarr is a documented
case), and retrofitting `conforms_to` later would be a breaking
change on the genesis event payload.

Field name `encoding` rather than `format` deliberately avoids
shadowing the Python builtin `format()` and aligns with
schema.org's vocabulary; DataCite's export schema uses `format`,
which the export adapter maps to when one ships.

## Cross-aggregate references

Four optional refs:

  - `producing_run_id: UUID | None`: the Run that produced this
    Dataset. None for externally-sourced data, uploaded reference
    sets, or pre-existing data being newly registered.
  - `producing_procedure_id: UUID | None`: the conducted Procedure
    that produced this Dataset (the secondary producer arm; most
    Datasets come from a Run). None for non-conducted / external
    Datasets.
  - `subject_id: UUID | None`: the Subject the Dataset is "about."
    None for calibration / dark-field / synthetic data with no
    sample.
  - `derived_from: frozenset[UUID]`: lineage edges to other
    Datasets this one was derived from (raw → reconstructed →
    segmented → ...). Empty for raw/captured data; multi-source
    for derivations that combine several inputs (multi-modal
    fusion, comparative analyses).

Eventual-consistency stance: existence-only validation at the
handler load step, no status check (so Datasets can be registered
mid-Run, and derived from any non-Discarded Dataset). Re-validation
at fold time is NOT performed; same posture as Run-start's
Plan/Subject loading.

The inverse query "what Datasets did Run X produce?" requires a
projection (deferred); it's never carried on the Run aggregate.

## Lineage in domain vs PROV-O at API boundary

In-domain lineage stays as the simple `derived_from` edge set on
each Dataset; query-time graph walks reconstruct the full
provenance chain. PROV-O export (using `prov:wasDerivedFrom`,
`prov:wasGeneratedBy`, `prov:Entity`/`Activity`/`Agent`) lives at
the API export adapter when a real consumer asks; we don't import
PROV-O vocabulary into the domain core.

## Identifier scheme

Dataset id is UUIDv7 (matches the cross-BC convention). Persistent
identifiers (DOIs via DataCite, including the IGSN-via-DataCite
flow for samples) land at the export layer when first needed; they
are not part of the in-domain Dataset identity.

## Addition: Calibration BC AsShot citation (`used_calibration_ids`)

`used_calibration_ids: frozenset[UUID]` records the CalibrationRevision
IDs the reconstruction (or any derivative) actually used. Symmetric
to Run.pinned_calibration_ids (AsShot anchor on the acquired-from Run);
the two sets are independent — reconstruction
may legitimately cite refined revisions not in the producing Run's
pin set (for example, a `tomopy.find_center_vo` refinement). NO write-time
cross-BC enforcement of derivative-source set equality per
[[project_calibration_design]] anti-hook #3 (revision-cited atomic
IDs make "partial override" a category error in this model). The
dual rule (anti-hook #13) is "no synthesis-by-omission" — every
value used MUST be a cited revision.

## Twelfth bounded-name VO

`DatasetName` calls the shared `validate_bounded_text` helper hoisted in
6e-1 (`cora.shared.bounded_text`). Twelfth occurrence of the
trimmed-bounded-name VO pattern (after Actor / Zone / Conduit /
Policy / Subject / Family / Asset / Method / Practice / Plan /
Run).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.text_bounds import REASON_MAX_LENGTH

DATASET_NAME_MAX_LENGTH = 200
DATASET_URI_MAX_LENGTH = 2048
DATASET_MEDIA_TYPE_MAX_LENGTH = 200
DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH = 2048
DATASET_CONFORMS_TO_MAX_ENTRIES = 16
DATASET_DERIVED_FROM_MAX_ENTRIES = 64
DATASET_USED_CALIBRATIONS_MAX_ENTRIES = 64
DATASET_CHECKSUM_ALGORITHM_SHA256 = "sha256"
DATASET_CHECKSUM_ALGORITHM_SHA256_TREE = "sha256-tree"
DATASET_CHECKSUM_SHA256_HEX_LENGTH = 64
# Both accepted algorithms produce a 64-char lowercase-hex value: sha256 of a
# single file, or sha256 of a directory's canonical manifest (sha256-tree, the
# digest a directory-output compute artifact carries). The value-format rules
# below are therefore identical for both; only the algorithm differs.
DATASET_CHECKSUM_ALGORITHMS = frozenset(
    {DATASET_CHECKSUM_ALGORITHM_SHA256, DATASET_CHECKSUM_ALGORITHM_SHA256_TREE}
)
RUN_END_STATE_COMPLETED = "Completed"  # raw string match against Run BC's RunStatus.COMPLETED.value
# Raw string matches against Operation BC's ActuationKind.value. Stored as a
# string snapshot on the Dataset (the producing BC owns the enum), mirroring
# the producing_run_end_state pattern above. The promote gate blocks the two
# simulator-tainted kinds; Physical (and None, no kind recorded) pass.
ACTUATION_KIND_PHYSICAL = "Physical"
ACTUATION_KIND_SIMULATED = "Simulated"
ACTUATION_KIND_HYBRID = "Hybrid"

# URI schemes that are never legitimate Dataset URIs and that pose
# XSS risk if a downstream UI renders the URI as a clickable link.
# Pure blocklist (not allowlist) so we don't constrain real storage
# schemes (s3, https, file, globus, posix, ipfs, sftp, azure, gs,
# etc.). The broader "allowlist of approved storage backends"
# conversation lands when the first storage adapter ships.
DATASET_URI_BLOCKED_SCHEMES = frozenset[str](
    {
        "javascript",
        "vbscript",
        "data",
        "about",
        "view-source",
    }
)


class DatasetStatus(StrEnum):
    """The Dataset's lifecycle state.

    7a ships `Registered`. 7b adds `Discarded` (terminal, with
    operator-supplied reason; bytes at the URI are gone but the
    metadata + audit trail remain). Archive / Verify / Move
    transitions defer until storage tiers actually exist in a
    deployment (gate-review Q1 lock B).

    Enum values are PascalCase strings (matches BC-map status
    vocabulary; log lines and DTOs read naturally without mapping).
    """

    REGISTERED = "Registered"
    DISCARDED = "Discarded"


class Intent(StrEnum):
    """The Dataset's trust level / promotion state.

    `Trial`: default on register. Working data: calibration scans,
    alignment runs, exposure tests, exploratory acquisitions. Not
    authoritative; no peer-reviewed claims attached.

    `Production`: explicitly promoted via `promote_dataset`.
    Publication-grade, citable. Operator's intent is "this is the
    keeper"; the audit log captures WHY (PromotionReason) immutably.

    `Retracted`: explicitly demoted from Production via
    `demote_dataset`. Terminal Intent value; no re-promote from
    Retracted (semantic: "this Dataset was authoritative, then
    retracted; if you want to re-publish a corrected version,
    register a NEW Dataset with `derived_from` pointing at this
    one"). The audit log captures WHY (DemotionReason) immutably.
    First concrete instantiation of the Q4 compensation-primitive
    pattern (per [[project-dataset-demote-design]]; mirrors the
    Crossref retraction model: additive notice, original
    preserved + marked).

    Open enum: future values (Calibration, Superseded, Authoritative)
    land additively without breaking existing payloads (additive-
    state pattern). See [[project_dataset_lineage_design]].

    Distinct from `DatasetStatus` (Registered | Discarded) which
    captures lifecycle. Intent captures trust level: orthogonal to
    lifecycle, mutated by separate slices (`promote_dataset` /
    `demote_dataset`).
    """

    TRIAL = "Trial"
    PRODUCTION = "Production"
    RETRACTED = "Retracted"


class InvalidDatasetNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Dataset name must be 1-{DATASET_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDatasetUriError(ValueError):
    """The supplied URI is empty, whitespace-only, has no scheme, or too long.

    URI format validation at the BC is intentionally loose: we accept
    anything that `urllib.parse.urlparse` returns with a non-empty
    scheme, after trim, within the length cap. Backend resolution
    (does the URI actually exist? does the checksum match?) is out of
    scope per gate-review Q4 lock A; that lives in a separate
    DatasetVerified workflow when bit-rot detection ships.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Dataset URI invalid ({reason}): {value!r}")
        self.value = value
        self.reason = reason


class InvalidDatasetChecksumError(ValueError):
    """The supplied checksum has an unsupported algorithm or malformed value.

    Only `sha256` is accepted today; the `(algorithm, value)` shape
    is forward-compatible for adding BLAKE3 / SHA3 / etc. when a real
    consumer asks. sha256 values must be 64 lowercase hex chars
    (canonical form).
    """

    def __init__(self, algorithm: str, value: str, reason: str) -> None:
        super().__init__(
            f"Dataset checksum invalid ({reason}): algorithm={algorithm!r}, value={value!r}"
        )
        self.algorithm = algorithm
        self.value = value
        self.reason = reason


class InvalidDatasetByteSizeError(ValueError):
    """The supplied byte_size is negative.

    Zero is allowed (an empty file is a valid Dataset; the operator
    knows what they're recording). Upper bound is not enforced at
    the BC; storage backends impose their own.
    """

    def __init__(self, value: int) -> None:
        super().__init__(f"Dataset byte_size must be >= 0 (got: {value})")
        self.value = value


class InvalidDatasetEncodingError(ValueError):
    """The supplied encoding VO has an invalid media_type or conforms_to entry.

    Media_type must trim to 1-200 chars (loose MIME-type validation;
    the exact taxonomy is free-form per gate-review Q5 lock A,
    pending the same three re-evaluation triggers as RunAborted's
    reason field). conforms_to entries must each be non-empty trimmed
    strings within the per-entry length cap; the set may be empty
    (no profile claimed).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Dataset encoding invalid: {reason}")
        self.reason = reason


class InvalidDerivedFromError(ValueError):
    """The supplied derived_from set has too many entries.

    Per-entry validation (each is a UUID) is type-enforced; the
    set-cardinality cap protects against accidentally massive
    lineage payloads on a single registration.
    """

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Dataset derived_from must have at most "
            f"{DATASET_DERIVED_FROM_MAX_ENTRIES} entries (got: {count})"
        )
        self.count = count


class InvalidUsedCalibrationsError(ValueError):
    """The supplied used_calibration_ids set has too many entries.

    Per-entry validation (each is a UUID) is type-enforced; the
    set-cardinality cap protects against accidentally massive
    AsShot-citation payloads on a single registration. Mirrors
    InvalidDerivedFromError shape exactly (same precedent +
    same default cap).

    NO cross-BC existence check on the cited revision ids per
    [[project_calibration_design]] anti-hook #3 (revision-cited
    atomic-ID model) + canonical DDD eventual-consistency stance
    on cross-aggregate rules (matches Run.pinned_calibration_ids
    precedent exactly).
    """

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Dataset used_calibration_ids must have at most "
            f"{DATASET_USED_CALIBRATIONS_MAX_ENTRIES} entries (got: {count})"
        )
        self.count = count


class DatasetAlreadyExistsError(Exception):
    """Attempted to register a Dataset whose stream already has events."""

    def __init__(self, dataset_id: UUID) -> None:
        super().__init__(f"Dataset {dataset_id} already exists")
        self.dataset_id = dataset_id


class DatasetNotFoundError(Exception):
    """Attempted an operation on a Dataset whose stream has no events."""

    def __init__(self, dataset_id: UUID) -> None:
        super().__init__(f"Dataset {dataset_id} not found")
        self.dataset_id = dataset_id


class ProducingRunNotFoundError(Exception):
    """Attempted to register a Dataset against a Run that doesn't exist.

    Cross-aggregate validation at registration: when `producing_run_id`
    is set, the handler pre-loads the Run and confirms its stream is
    non-empty. No status check (gate-review Q2 lock B): Datasets can
    be registered against Running, Held, or any terminal Run, because
    in-situ measurements register Datasets while the Run is still
    actively running. Mapped to HTTP 409.
    """

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Cannot register Dataset: producing_run_id {run_id} does not exist")
        self.run_id = run_id


class ProducingProcedureNotFoundError(Exception):
    """Attempted to register a Dataset against a Procedure that doesn't exist.

    Cross-aggregate validation at registration: when
    `producing_procedure_id` is set, the handler pre-loads the
    Procedure (Operation BC) and confirms its stream is non-empty.
    No status check (mirrors ProducingRunNotFoundError): the decider
    derives `producing_actuation_kind` from whatever terminal state
    the Procedure holds (None while non-terminal). Mapped to HTTP 404
    via the locked <X>NotFoundError -> 404 taxonomy.
    """

    def __init__(self, procedure_id: UUID) -> None:
        super().__init__(
            f"Cannot register Dataset: producing_procedure_id {procedure_id} does not exist"
        )
        self.procedure_id = procedure_id


class ProducingProcedureNotTerminalError(Exception):
    """Attempted to register a Dataset against a non-terminal producing Procedure.

    The actuation kind is snapshotted from the producing Procedure's
    terminal state at registration (capture, don't recompute). A
    still-Defined / Running Procedure has no final kind yet, so its
    snapshot would be a stale None even after the conduct later resolves
    to Physical -- which the promote-time unprovable-provenance guard
    would then wrongly block. Requiring the Procedure to be terminal at
    registration keeps "producing_procedure_id set + kind None" an
    unambiguous "unprovable" signal. Cross-aggregate state conflict;
    mapped to HTTP 409.
    """

    def __init__(self, procedure_id: UUID, *, current_status: str) -> None:
        super().__init__(
            f"Cannot register Dataset: producing_procedure_id {procedure_id} is "
            f"{current_status!r}; a producing Procedure must be terminal "
            "(Completed / Aborted / Truncated) at registration so its actuation "
            "kind is final"
        )
        self.procedure_id = procedure_id
        self.current_status = current_status


class LinkedSubjectNotFoundError(Exception):
    """Attempted to register a Dataset against a Subject that doesn't exist.

    Cross-aggregate validation at registration: when `subject_id` is
    set, the handler pre-loads the Subject and confirms its stream
    is non-empty. No status check (gate-review Q2 lock B): the link
    is "this Dataset is about that Subject", which is meaningful
    regardless of the Subject's current lifecycle state. Mapped to
    HTTP 409.
    """

    def __init__(self, subject_id: UUID) -> None:
        super().__init__(f"Cannot register Dataset: subject_id {subject_id} does not exist")
        self.subject_id = subject_id


class DerivedFromDatasetsNotFoundError(Exception):
    """One or more derived_from references don't exist as Datasets.

    Cross-aggregate validation at registration: when `derived_from`
    is non-empty, the handler pre-loads each referenced Dataset and
    confirms each stream is non-empty. The error carries the full
    list of missing ids so the operator can fix the input. Mapped
    to HTTP 409.
    """

    def __init__(self, missing_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot register Dataset: derived_from references the following "
            f"non-existent Datasets: {[str(d) for d in missing_ids]}"
        )
        self.missing_ids = missing_ids


class DerivedFromDatasetsDiscardedError(Exception):
    """One or more derived_from references point at Discarded Datasets.

    7b status check on top of the 7a existence check: registering a
    Dataset with `derived_from` referencing a Discarded Dataset is
    rejected (we don't allow new lineage edges into bytes that no
    longer exist). The error carries the full list of discarded ids
    so the operator can fix the input. Mapped to HTTP 409.
    """

    def __init__(self, discarded_ids: list[UUID]) -> None:
        super().__init__(
            f"Cannot register Dataset: derived_from references the following "
            f"Discarded Datasets: {[str(d) for d in discarded_ids]}"
        )
        self.discarded_ids = discarded_ids


class InvalidDatasetDiscardReasonError(ValueError):
    """The supplied discard reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Mirrors the
    InvalidRunStopReasonError / InvalidRunAbortReasonError /
    InvalidRunTruncateReasonError pattern.

    Free-form `str` (1-500 chars) shape with the same future-additive
    structured-taxonomy posture (re-evaluation triggers documented at
    the Run BC's reason-error classes apply identically here).

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Dataset discard reason must be 1-{REASON_MAX_LENGTH} chars after "
            f"trimming (got: {value!r})"
        )
        self.value = value


class DatasetCannotDiscardError(Exception):
    """Attempted to discard a Dataset not in `Registered` status.

    Single-source guard: only `Registered → Discarded`. Re-discarding
    an already-`Discarded` Dataset raises (strict-not-idempotent,
    matches every other terminal-transition pattern in the codebase).

    Mapped to HTTP 409.
    """

    def __init__(self, dataset_id: UUID, current_status: "DatasetStatus") -> None:
        super().__init__(
            f"Dataset {dataset_id} cannot be discarded: currently in status "
            f"{current_status.value}, discard requires {DatasetStatus.REGISTERED.value}"
        )
        self.dataset_id = dataset_id
        self.current_status = current_status


class InvalidPromotionReasonError(ValueError):
    """The supplied promotion reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Mirrors the
    InvalidDatasetDiscardReasonError shape exactly — same free-form
    `str` (1-500 chars) posture, same future-additive structured-
    taxonomy re-evaluation triggers (see RunAbortReason vocabulary
    convergence triggers).

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Dataset promotion reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class DatasetAlreadyPromotedError(Exception):
    """Attempted to promote a Dataset that's already in `Production` intent.

    Strict-not-idempotent: re-promote raises rather than silent no-op
    (same posture as `add_plan_wire`, `add_asset_port`, every other
    add-style mutation in the codebase). Operators get clear feedback
    on accidental double-promote.

    Mapped to HTTP 409.
    """

    def __init__(self, dataset_id: UUID, current_intent: "Intent") -> None:
        super().__init__(
            f"Dataset {dataset_id} cannot be promoted: currently in intent "
            f"{current_intent.value}, promotion requires {Intent.TRIAL.value}"
        )
        self.dataset_id = dataset_id
        self.current_intent = current_intent


class DatasetCannotPromoteError(Exception):
    """A guard rejected the promotion to Production.

    Four branches, all surfaced via this single error class with a
    branch-specific reason string:

      - `dataset is discarded; cannot promote` (status guard)
      - `producing Run X ended in <state>; only Completed Runs can
        produce Production datasets` (Run-must-be-Completed guard)
      - `derived_from Datasets [...] are still Trial; cannot promote
        dataset above its inputs` (lineage-must-be-Production guard;
        mirrors the prior lineage-into-Discarded guard)
      - `data was produced by Simulated / Hybrid actuation; rehearsal /
        simulator-origin data cannot be promoted to Production`
        (actuation-must-not-be-simulated guard)

    Mapped to HTTP 409. Carries the offending entity ids in the
    reason string for operator clarity.
    """

    def __init__(self, dataset_id: UUID, reason: str) -> None:
        super().__init__(f"Dataset {dataset_id} cannot be promoted: {reason}")
        self.dataset_id = dataset_id
        self.reason = reason


@dataclass(frozen=True)
class PromotionReason:
    """Free-form promotion reason. Trimmed; 1-500 chars.

    Mirrors DatasetDiscardReason / RunStopReason / RunTruncateReason /
    RunAbortReason precedent. The on-the-wire representation in
    `DatasetPromoted.reason` is `str` (post-trim); the VO exists at
    decider-input time only to centralize the validation.

    Free-form `str` shape with the same future-additive structured-
    taxonomy posture (re-evaluation triggers documented at the Run BC's
    reason-error classes apply identically here).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidPromotionReasonError,
        )
        object.__setattr__(self, "value", trimmed)


class InvalidDemotionReasonError(ValueError):
    """The supplied demotion reason is empty, whitespace-only, or too long.

    Validated at the API boundary via Pydantic min_length / max_length,
    AND defensively at the decider via this error. Mirrors
    InvalidPromotionReasonError shape exactly — same free-form `str`
    (1-500 chars) posture, same future-additive structured-taxonomy
    re-evaluation triggers.

    Mapped to HTTP 400.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Dataset demotion reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class DatasetAlreadyRetractedError(Exception):
    """Attempted to demote a Dataset that's already in `Retracted` intent.

    Strict-not-idempotent: re-demote raises rather than silent no-op
    (same posture as DatasetAlreadyPromotedError + every other terminal-
    mutation pattern in the codebase). Operators get clear feedback on
    accidental double-demote.

    Mapped to HTTP 409.
    """

    def __init__(self, dataset_id: UUID, current_intent: "Intent") -> None:
        super().__init__(
            f"Dataset {dataset_id} cannot be demoted: currently in intent "
            f"{current_intent.value}, demotion requires {Intent.PRODUCTION.value}"
        )
        self.dataset_id = dataset_id
        self.current_intent = current_intent


class DatasetCannotDemoteError(Exception):
    """A guard rejected the demotion from Production (post-Q4 compensation slice).

    Two branches, both surfaced via this single error class with a
    branch-specific reason string:

      - `dataset is discarded; cannot demote` (status guard —
        Discarded is a stronger terminal than Retracted; bytes
        already gone)
      - `dataset is in Trial intent; cannot demote` (semantic guard
        — Trial→Retracted would conflate "never authoritative" with
        "was authoritative but now isn't"; use discard_dataset for
        the former)

    Mapped to HTTP 409. Carries the offending dataset id in the
    reason string for operator clarity.

    NOT used for the strict-not-idempotent re-demote case (that's
    DatasetAlreadyRetractedError); kept distinct so the rejection
    families mirror the promote-side shape exactly
    (DatasetCannotPromoteError + DatasetAlreadyPromotedError).
    """

    def __init__(self, dataset_id: UUID, reason: str) -> None:
        super().__init__(f"Dataset {dataset_id} cannot be demoted: {reason}")
        self.dataset_id = dataset_id
        self.reason = reason


@dataclass(frozen=True)
class DemotionReason:
    """Free-form demotion reason. Trimmed; 1-500 chars.

    Mirrors PromotionReason / DatasetDiscardReason / RunStopReason
    precedent. The on-the-wire representation in `DatasetDemoted.reason`
    is `str` (post-trim); the VO exists at decider-input time only to
    centralize the validation.

    Free-form `str` shape with the same future-additive structured-
    taxonomy posture (re-evaluation triggers documented at the Run BC's
    reason-error classes apply identically here). Operationally this
    records "we're retracting this dataset's authoritative status
    because <X>" — typical X values: discovered calibration error,
    methodology challenged in peer review, sample compromised post-hoc.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidDemotionReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DatasetDiscardReason:
    """Free-form discard reason. Trimmed; 1-500 chars.

    Mirrors RunStopReason / RunTruncateReason / RunAbortReason. The
    on-the-wire representation in `DatasetDiscarded.reason` is `str`
    (post-trim); the VO exists at decider-input time only.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidDatasetDiscardReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@bounded_name(max_length=DATASET_NAME_MAX_LENGTH, error_class=InvalidDatasetNameError)
@dataclass(frozen=True)
class DatasetName:
    """Display name for a Dataset. Trimmed; 1-200 chars.

    Twelfth occurrence of the trimmed-bounded-name VO pattern. Uses
    the shared `validate_bounded_text` helper hoisted at the
    rule-of-three trigger (see `cora.shared.bounded_text`).
    """

    value: str


def _validate_storage_uri(
    value: str,
    *,
    max_length: int,
    error_factory: Callable[[str, str], Exception],
) -> str:
    """Validate a storage URI string per the shared Dataset/Distribution rules.

    Returns the trimmed value or raises the caller's error class. The
    rules are:

      - non-empty after `.strip()`
      - length <= ``max_length``
      - `urllib.parse.urlparse(trimmed).scheme` non-empty
      - scheme (lower-cased) not in :data:`DATASET_URI_BLOCKED_SCHEMES`
        (defensive XSS blocklist; the same threat surface applies to a
        Distribution URI as to a Dataset URI)

    Bytes resolution / existence check is out of scope at the BC layer
    (gate-review Q4 lock A: trust at registration; periodic re-checksum
    / verification is its own future workflow).
    """
    trimmed = value.strip()
    if not trimmed:
        raise error_factory(value, "empty or whitespace-only")
    if len(trimmed) > max_length:
        raise error_factory(value, f"exceeds {max_length} chars")
    parsed = urlparse(trimmed)
    if not parsed.scheme:
        raise error_factory(value, "missing URI scheme")
    if parsed.scheme.lower() in DATASET_URI_BLOCKED_SCHEMES:
        raise error_factory(
            value,
            f"URI scheme {parsed.scheme!r} is blocked (XSS risk)",
        )
    return trimmed


@dataclass(frozen=True)
class DatasetUri:
    """Opaque URI string pointing at the bulk content. Trimmed; 1-2048 chars.

    Loose validation: `urllib.parse.urlparse` must return a non-empty
    scheme. Bytes resolution / existence check is out of scope at the
    BC layer (gate-review Q4 lock A: trust at registration; periodic
    re-checksum / verification is its own future workflow). Shares the
    XSS-blocklist + trim + length rules with `DistributionUri` via the
    `_validate_storage_uri` helper.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = _validate_storage_uri(
            self.value,
            max_length=DATASET_URI_MAX_LENGTH,
            error_factory=InvalidDatasetUriError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DatasetChecksum:
    """Bulk-content integrity hash. Algorithm + canonical value.

    Deviation from Identifier VO: strict 64-char lowercase-hex value
    invariant beyond Identifier's generic 1-200 bound.

    Two algorithms accepted: `sha256` (a single file) and `sha256-tree`
    (a directory folded into a deterministic sha256 over its canonical
    manifest, the digest a directory-output compute artifact carries).
    Both produce a 64-char lowercase-hex value, so the value-format rules
    are identical; only the algorithm tag distinguishes them. The
    `(algorithm, value)` shape stays forward-compatible for adding
    BLAKE3 / SHA3 / etc. when a real consumer asks.
    """

    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm not in DATASET_CHECKSUM_ALGORITHMS:
            raise InvalidDatasetChecksumError(
                self.algorithm,
                self.value,
                f"algorithm must be one of {sorted(DATASET_CHECKSUM_ALGORITHMS)}",
            )
        if len(self.value) != DATASET_CHECKSUM_SHA256_HEX_LENGTH:
            raise InvalidDatasetChecksumError(
                self.algorithm,
                self.value,
                f"checksum value must be {DATASET_CHECKSUM_SHA256_HEX_LENGTH} hex chars",
            )
        if not all(c in "0123456789abcdef" for c in self.value):
            raise InvalidDatasetChecksumError(
                self.algorithm,
                self.value,
                "checksum value must be lowercase hex (0-9, a-f)",
            )


@dataclass(frozen=True)
class DatasetEncoding:
    """Structured encoding descriptor: media_type + conforms_to profile URIs.

    Per the gate-review L3 refinement (post-standards-survey), this
    is a small VO rather than a free-form string. `media_type` is
    a loose MIME-type-ish string ("application/x-hdf5",
    "application/x-zarr", "application/x-tiff", etc.); `conforms_to`
    is a possibly-empty set of profile URIs the Dataset claims
    (NeXus, OME-Zarr, CIF, etc.). Forward-compatible with RO-Crate
    1.2's pattern.

    The on-the-wire payload representation sorts `conforms_to`
    deterministically (matches the Policy/permitted_principal_ids
    precedent) so two registrations of the same logical encoding
    produce byte-identical jsonb.
    """

    media_type: str
    conforms_to: frozenset[str] = field(default_factory=frozenset[str])

    def __post_init__(self) -> None:
        trimmed_media_type = self.media_type.strip()
        if not trimmed_media_type:
            raise InvalidDatasetEncodingError("media_type empty or whitespace-only")
        if len(trimmed_media_type) > DATASET_MEDIA_TYPE_MAX_LENGTH:
            raise InvalidDatasetEncodingError(
                f"media_type exceeds {DATASET_MEDIA_TYPE_MAX_LENGTH} chars"
            )
        if len(self.conforms_to) > DATASET_CONFORMS_TO_MAX_ENTRIES:
            raise InvalidDatasetEncodingError(
                f"conforms_to has too many entries "
                f"(max {DATASET_CONFORMS_TO_MAX_ENTRIES}, got {len(self.conforms_to)})"
            )
        trimmed_conforms_to: set[str] = set()
        for entry in self.conforms_to:
            entry_trimmed = entry.strip()
            if not entry_trimmed:
                raise InvalidDatasetEncodingError("conforms_to entry is empty or whitespace-only")
            if len(entry_trimmed) > DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH:
                raise InvalidDatasetEncodingError(
                    f"conforms_to entry exceeds "
                    f"{DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH} chars: {entry!r}"
                )
            trimmed_conforms_to.add(entry_trimmed)
        object.__setattr__(self, "media_type", trimmed_media_type)
        object.__setattr__(self, "conforms_to", frozenset(trimmed_conforms_to))


def validate_byte_size(value: int) -> int:
    """Normalize / validate byte_size for the Dataset state and decider.

    Zero is valid (empty files are valid Datasets); negative is not.
    Free function rather than a VO because byte_size has no other
    invariants beyond non-negative-int, and wrapping it in a frozen
    dataclass would just add boilerplate.
    """
    if value < 0:
        raise InvalidDatasetByteSizeError(value)
    return value


def validate_derived_from(value: frozenset[UUID]) -> frozenset[UUID]:
    """Normalize / validate derived_from for the Dataset state and decider.

    Cardinality-only check at this layer; per-element existence is
    cross-aggregate validation in the handler's
    `DatasetRegistrationContext`.
    """
    if len(value) > DATASET_DERIVED_FROM_MAX_ENTRIES:
        raise InvalidDerivedFromError(len(value))
    return value


def validate_used_calibration_ids(value: frozenset[UUID]) -> frozenset[UUID]:
    """Normalize / validate used_calibration_ids for the Dataset state and decider.

    Cardinality-only check. NO per-element existence check (revision-
    cited atomic-ID model; cross-BC eventual-consistency per
    [[project_calibration_design]] anti-hook #3 + Vernon/Evans DDD
    canon). Mirrors Run.pinned_calibration_ids decider-time treatment
    exactly.
    """
    if len(value) > DATASET_USED_CALIBRATIONS_MAX_ENTRIES:
        raise InvalidUsedCalibrationsError(len(value))
    return value


@dataclass(frozen=True)
class Dataset:
    """Aggregate root: one logical research data product.

    `producing_run_id`, `subject_id`, `derived_from` are eventual-
    consistency refs (loaded at handler-load time; not re-verified
    at fold time). All three are optional (None / empty for the
    standalone-upload case). `derived_from` is the lineage edge set
    pointing at upstream Datasets this one was derived from.

    `status` defaults to `Registered`; the lifecycle FSM expands in
    7b (Discarded terminal) and later phases.

    `producing_run_end_state`: captures the producing
    Run's terminal status at the moment of Dataset registration
    (per non-determinism principle: capture, don't recompute). Null
    when there's no producing_run_id (standalone-upload Dataset) OR
    for legacy DatasetRegistered events without the field (they
    fold cleanly via payload.get default). Powers the
    `promote_dataset` Run-must-be-Completed guard.

    `intent`: trust level / promotion state, orthogonal to
    `status` (lifecycle). Defaults to `Trial`; flipped to `Production`
    by an explicit `promote_dataset` call with audit reason. See
    [[project_dataset_lineage_design]].
    """

    id: UUID
    name: DatasetName
    uri: DatasetUri
    checksum: DatasetChecksum
    byte_size: int
    encoding: DatasetEncoding
    producing_run_id: UUID | None = None
    # The conducted Procedure that produced this Dataset; the lineage edge the
    # actuation kind was derived from at registration. None for non-conducted
    # / external Datasets. Eventual-consistency ref (loaded at register time,
    # not re-verified at fold). Additive-state default None.
    producing_procedure_id: UUID | None = None
    subject_id: UUID | None = None
    derived_from: frozenset[UUID] = field(default_factory=frozenset[UUID])
    status: DatasetStatus = DatasetStatus.REGISTERED
    # additions:
    producing_run_end_state: str | None = None
    # Raw ActuationKind value (Physical / Simulated / Hybrid) the producing
    # conduct observed, snapshotted at registration. None for standalone
    # uploads, conducts with no routing table, and legacy events. Powers the
    # promote_dataset simulator-origin guard (Simulated / Hybrid block).
    producing_actuation_kind: str | None = None
    intent: Intent = Intent.TRIAL
    # Calibration BC AsShot citation (revision-cited
    # atomic-ID model per [[project_calibration_design]]). Each entry
    # is a `CalibrationRevision.id` the reconstruction (or any
    # derivative) actually used. Symmetric to Run.pinned_calibration_ids;
    # the two sets are independent — the Dataset cites whatever revisions it
    # used (often the same as the producing Run's pin set, sometimes
    # including post-acquisition refinements like a refined
    # rotation_center revision computed by `tomopy.find_center_vo`,
    # sometimes a fully different set). NO write-time cross-BC
    # enforcement of derivative-source set equality per anti-hook #3
    # (revision-cited atomic IDs make "partial override" a category
    # error in this model) + canonical DDD eventual-consistency
    # stance. Anti-hook #13 (no synthesis-by-omission) is the dual:
    # every calibration value the reconstruction used MUST appear as
    # a revision_id in this set; downstream code paths MUST NOT
    # silently inject fallback values.
    # IMMUTABLE after register_dataset by aggregate-level invariant
    # (mirrors Run.pinned_calibration_ids AsShot immutability) — every
    # transition arm in the evolver (DatasetDiscarded /
    # DatasetPromoted) preserves `prior.used_calibration_ids` verbatim.
    # Defaults to empty frozenset so legacy streams fold cleanly via
    # `payload.get("used_calibration_ids", [])` (additive-state pattern;
    # mirrors derived_from / producing_run_end_state / intent
    # precedent).
    used_calibration_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
