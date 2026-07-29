"""Application handler for `IngestScan`: read, digest, compose, append once.

Orchestration slice: no decider of its own. It composes the three
existing DECIDERS (register_dataset, register_distribution,
record_acquisition) and persists their genesis events in ONE
`append_streams` call, atomically. It never calls those slices'
HANDLERS: each handler is its own `append` transaction, so chaining
them can commit a Dataset and then reject the Acquisition, stranding a
permanent half-record in the system of record. All-or-nothing here is
the whole reason this slice exists; the batch either lands the full
Dataset + Distribution + Acquisition chain in a single Postgres
transaction via `append_streams`, or nothing at all is written.

The distribution and acquisition deciders receive the in-flight Dataset
state folded from the just-decided genesis events, not a store load;
the Dataset does not exist anywhere else yet.

## Refusal order

Everything that can refuse does so BEFORE the deciders run: the reader
(unreadable, unrecognized, structurally incomplete), the timestamp
policy, the digest pass, the changed-under-read guard, the natural-key
duplicate check, and the cross-aggregate pre-loads. A refusal at any
point leaves zero events. Decider rejections (Capturing gate, future
captured_at, non-Storage supply) then fire inside the composition and
also leave zero events, because nothing has been appended yet.

## The timestamp policy

A parseable (timezone-aware) file `start_date` always wins; supplying
`captured_at` alongside one is refused as ambiguous rather than
silently overridden. With no parseable file value, the operator's
`captured_at` is accepted as caller-asserted provenance, the same trust
the base record_acquisition slice extends. With neither, the ingest
refuses and names the remedy. Ingest observation time is NEVER written:
the only files lacking a timestamp here are complete-but-timestampless
ones (layout divergence, time-IOC disconnect, format drift), each a
staff-visible anomaly a fabricated value would bury.
"""

from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse
from uuid import UUID

from cora.data._ingest import StreamPlan, decide_ingest
from cora.data.aggregates.acquisition import AcquisitionAssetNotFoundError
from cora.data.aggregates.dataset import (
    DatasetAlreadyIngestedError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.distribution import DistributionSupplyNotFoundError
from cora.data.errors import InvalidScanFileError, UnauthorizedError
from cora.data.features.ingest_scan.command import IngestScan
from cora.data.ports.checksum_computer import ChecksumComputer
from cora.data.ports.checksum_verifier import Unreachable
from cora.data.ports.scan_reader import Description, ScanReader, Unreadable, Unrecognized
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import load_run
from cora.shared.identity import ActorId
from cora.shared.json_schema_validation import validate_values_against_schema

_COMMAND_NAME = "IngestScan"
_DATASET_STREAM = "Dataset"
_DISTRIBUTION_STREAM = "Distribution"
_ACQUISITION_STREAM = "Acquisition"

_log = get_logger(__name__)

#: The profile marker recorded on conforms_to. No canonical schema URI
#: exists for Data Exchange and real 2-BM files carry no
#: self-identification (nothing writes /implements), so conformance is
#: CORA's assertion, pinned to the DXfile paper's DOI.
DATA_EXCHANGE_PROFILE = "https://doi.org/10.1107/S160057751401604X"

#: Declared shape of the frame-accounting evidence this slice records
#: (declarer-owns-schema: the ingest slice declares, the Acquisition
#: carries). Optional keys are OMITTED when the source cannot know
#: them, never nulled: absence means source-cannot-know, 0 means
#: verified-none, and a consumer must not collapse the two.
EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reader_kind": {"type": "string"},
        "checksum_computer_kind": {"type": "string"},
        "captured_at_source": {"type": "string", "enum": ["start_date", "operator"]},
        "start_date_raw": {"type": "string"},
        "projection_count": {"type": "integer"},
        "flat_count": {"type": "integer"},
        "dark_count": {"type": "integer"},
        "invalid_count": {"type": "integer"},
        "commanded_projection_count": {"type": "integer"},
        "commanded_flat_count": {"type": "integer"},
        "commanded_dark_count": {"type": "integer"},
        "dropped_frame_count": {"type": "integer"},
        "projection_angle_count": {"type": "integer"},
        "projection_angle_first": {
            "type": "number",
            "unit": {"system": "udunits", "code": "degree"},
        },
        "projection_angle_last": {
            "type": "number",
            "unit": {"system": "udunits", "code": "degree"},
        },
    },
}


class DatasetByChecksumLookup(Protocol):
    """Digest-equality probe against the dataset read model.

    Returns the existing dataset id holding these bytes, or None. Backed
    by `proj_data_dataset_summary`'s checksum columns in production;
    the projection lag window (and a concurrent double-submit racing it)
    is an accepted TOCTOU for a human-triggered slice.
    """

    async def __call__(self, *, checksum_algorithm: str, checksum_value: str) -> UUID | None: ...


class Handler(Protocol):
    """Bare ingest_scan handler, what `bind()` returns."""

    async def __call__(
        self,
        command: IngestScan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """ingest_scan handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: IngestScan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(
    deps: Kernel,
    *,
    scan_reader: ScanReader,
    checksum_computer: ChecksumComputer,
    dataset_by_checksum_lookup: DatasetByChecksumLookup,
) -> Handler:
    """Build an ingest_scan handler closed over the shared deps.

    The three extra ports arrive explicitly rather than through the
    Kernel: they are Data-BC-local (the Kernel carries cross-BC
    primitives only), and `wire_data` constructs them from settings.
    """

    async def handler(
        command: IngestScan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "ingest_scan.start",
            command_name=_COMMAND_NAME,
            locator=command.locator,
            producing_asset_id=str(command.producing_asset_id),
            supply_id=str(command.supply_id),
            producing_run_id=(
                str(command.producing_run_id) if command.producing_run_id is not None else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "ingest_scan.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # 1. Read the file's facts. Any non-Description is a refusal
        # with the reader's reason; an incomplete file is refused too,
        # because its facts are still changing by construction.
        described = await scan_reader.describe(locator_uri=command.locator)
        if isinstance(described, Unreadable):
            raise InvalidScanFileError(
                f"scan file is not readable: {described.reason}. If the file "
                f"is still transferring, retry once it has arrived."
            )
        if isinstance(described, Unrecognized):
            raise InvalidScanFileError(f"not a recognizable scan file: {described.reason}")
        if not described.structurally_complete:
            raise InvalidScanFileError(
                "scan file is structurally incomplete: the rotation-angle "
                "dataset is absent, meaning post-processing has not "
                "completed (not yet run, failed, or zero projections). "
                "Ingest the file once its writer has finished with it."
            )

        captured_at, captured_at_source = _resolve_captured_at(command, described)

        # 2. Digest the bytes; this is also the second stat point of
        # the live-file guard.
        computed = await checksum_computer.compute(
            locator_uri=command.locator, supply_id=command.supply_id
        )
        if isinstance(computed, Unreachable):
            raise InvalidScanFileError(f"could not digest scan file: {computed.error_detail}")
        if (computed.byte_size, computed.mtime_ns) != (described.byte_size, described.mtime_ns):
            raise InvalidScanFileError(
                "scan file changed while being read (size or mtime moved "
                "between the structural read and the digest pass). It is "
                "still being written or transferred; retry once it is final."
            )

        # 3. Natural-key duplicate check: the digest, not the uri, since
        # the same bytes are legitimately multi-homed across tiers.
        existing = await dataset_by_checksum_lookup(
            checksum_algorithm=computed.algorithm, checksum_value=computed.value
        )
        if existing is not None:
            raise DatasetAlreadyIngestedError(existing, computed.value)

        # 4. Cross-aggregate pre-loads, same order and errors as the
        # composed slices' own handlers.
        asset = await deps.asset_lookup.lookup(command.producing_asset_id)
        if asset is None:
            raise AcquisitionAssetNotFoundError(command.producing_asset_id)
        supply = await deps.supply_lookup.lookup(command.supply_id)
        if supply is None:
            raise DistributionSupplyNotFoundError(command.supply_id)
        run = None
        if command.producing_run_id is not None:
            run = await load_run(deps.event_store, command.producing_run_id)
            if run is None:
                # The dataset decider validates producing_run through its
                # context; surface the same error its handler would.
                raise ProducingRunNotFoundError(command.producing_run_id)

        evidence = _build_evidence(described, captured_at_source, scan_reader, checksum_computer)
        validate_values_against_schema(
            evidence,
            EVIDENCE_SCHEMA,
            error_class=InvalidScanFileError,
        )

        now = deps.clock.now()
        dataset_id = deps.id_generator.new_id()
        distribution_id = deps.id_generator.new_id()
        acquisition_id = deps.id_generator.new_id()

        # 5. Compose the three deciders in memory via the BC-root core
        # (slices must not import siblings; cora.data._ingest is the one
        # sanctioned home for the composition, per the conductor
        # precedent). Any decider rejection propagates here, before
        # anything is appended.
        plans = decide_ingest(
            name=_filename_of(command.locator),
            locator=command.locator,
            checksum_algorithm=computed.algorithm,
            checksum_value=computed.value,
            byte_size=computed.byte_size,
            media_type=described.media_type,
            conforms_to=frozenset({DATA_EXCHANGE_PROFILE}),
            access_protocol=command.access_protocol,
            producing_run_id=command.producing_run_id,
            run=run,
            asset=asset,
            supply=supply,
            supply_id=command.supply_id,
            captured_at=captured_at,
            evidence=evidence,
            now=now,
            dataset_id=dataset_id,
            distribution_id=distribution_id,
            acquisition_id=acquisition_id,
            actor=ActorId(principal_id),
        )

        # 6. One atomic append: all three genesis streams land in a
        # single Postgres transaction via append_streams, or none do.
        def envelopes(plan: StreamPlan) -> list[Any]:
            return [
                to_new_event(
                    event_type=event_type,
                    payload=payload,
                    occurred_at=occurred_at,
                    event_id=deps.id_generator.new_id(),
                    command_name=_COMMAND_NAME,
                    correlation_id=correlation_id,
                    causation_id=causation_id,
                    principal_id=principal_id,
                )
                for event_type, payload, occurred_at in plan.events
            ]

        dataset_plan, distribution_plan, acquisition_plan = plans
        await deps.event_store.append_streams(
            [
                StreamAppend(
                    stream_type=dataset_plan.stream_type,
                    stream_id=dataset_plan.stream_id,
                    expected_version=0,
                    events=envelopes(dataset_plan),
                ),
                StreamAppend(
                    stream_type=distribution_plan.stream_type,
                    stream_id=distribution_plan.stream_id,
                    expected_version=0,
                    events=envelopes(distribution_plan),
                ),
                StreamAppend(
                    stream_type=acquisition_plan.stream_type,
                    stream_id=acquisition_plan.stream_id,
                    expected_version=0,
                    events=envelopes(acquisition_plan),
                ),
            ]
        )

        _log.info(
            "ingest_scan.success",
            command_name=_COMMAND_NAME,
            dataset_id=str(dataset_id),
            distribution_id=str(distribution_id),
            acquisition_id=str(acquisition_id),
            captured_at_source=captured_at_source,
            projection_count=described.projection_count,
            dropped_frame_count=described.dropped_frame_count,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )
        return dataset_id

    return handler


def _resolve_captured_at(command: IngestScan, described: Description) -> tuple[Any, str]:
    """Apply the locked timestamp policy; see the module docstring."""
    if described.start_date is not None:
        if command.captured_at is not None:
            raise InvalidScanFileError(
                f"captured_at was supplied but the file carries its own "
                f"parseable timestamp ({described.start_date_raw}). Drop the "
                f"supplied value; the file's own timestamp always wins."
            )
        return described.start_date, "start_date"
    if command.captured_at is not None:
        return command.captured_at, "operator"
    detail = (
        f"present but not parseable as an unambiguous instant: {described.start_date_raw!r}"
        if described.start_date_raw is not None
        else "absent"
    )
    raise InvalidScanFileError(
        f"the file's acquisition timestamp is {detail}. Supply captured_at "
        f"with the operator-asserted capture time (logbook, folder date) to "
        f"ingest this file; CORA never fabricates one."
    )


def _build_evidence(
    described: Description,
    captured_at_source: str,
    scan_reader: ScanReader,
    checksum_computer: ChecksumComputer,
) -> dict[str, Any]:
    """Frame accounting per EVIDENCE_SCHEMA: omit what the source cannot
    know, record who produced each fact."""
    evidence: dict[str, Any] = {
        "reader_kind": scan_reader.kind,
        "checksum_computer_kind": checksum_computer.kind,
        "captured_at_source": captured_at_source,
        "projection_count": described.projection_count,
        "flat_count": described.flat_count,
        "dark_count": described.dark_count,
        "invalid_count": described.invalid_count,
    }
    if described.start_date_raw is not None:
        evidence["start_date_raw"] = described.start_date_raw
    if described.commanded_projection_count is not None:
        evidence["commanded_projection_count"] = described.commanded_projection_count
    if described.commanded_flat_count is not None:
        evidence["commanded_flat_count"] = described.commanded_flat_count
    if described.commanded_dark_count is not None:
        evidence["commanded_dark_count"] = described.commanded_dark_count
    if described.dropped_frame_count is not None:
        evidence["dropped_frame_count"] = described.dropped_frame_count
    if described.projection_angles_deg:
        evidence["projection_angle_count"] = len(described.projection_angles_deg)
        evidence["projection_angle_first"] = described.projection_angles_deg[0]
        evidence["projection_angle_last"] = described.projection_angles_deg[-1]
    return evidence


def _filename_of(locator: str) -> str:
    name = Path(unquote(urlparse(locator).path)).name
    if not name:
        raise InvalidScanFileError(
            "the locator carries no filename to name the Dataset after; "
            "point it at the scan file itself, not a directory."
        )
    return name


__all__ = [
    "DATA_EXCHANGE_PROFILE",
    "EVIDENCE_SCHEMA",
    "DatasetByChecksumLookup",
    "Handler",
    "IdempotentHandler",
    "bind",
]
