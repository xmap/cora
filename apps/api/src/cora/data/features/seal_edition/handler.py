"""Application handler for the `seal_edition` slice.

Update-style handler. Pre-load order per design memo L15:

  1. UnauthorizedError (Authorize.authorize)
  2. Load Edition stream + fold -> EditionNotFoundError if None
  3. (Decider) status guard (EditionCannotSealError)
  4. (Decider) non-empty member guard
  5. Pre-load member Datasets + canonical Distributions
  6. Resolve effective publisher_facility_code (override -> state -> error)
  7. Validate publisher_facility_code (FacilityLookup -> 404 if missing)
  8. Resolve effective license + publication_year (override -> state ->
     sealing-clock year)
  9. Call EditionSerializer.serialize -> 502 if it raises
  10. Run pure decider with all captured fields in context
  11. Append EditionSealed event
"""

from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetNotFoundError,
    Intent,
    load_dataset,
)
from cora.data.aggregates.dataset.state import DatasetStatus
from cora.data.aggregates.edition import (
    LICENSE_REQUIRED_KINDS,
    EditionCannotSealError,
    EditionCannotSealOnDiscardedDatasetError,
    EditionDatasetsNotAllProductionError,
    EditionEvent,
    EditionLicenseRequiredForKindError,
    EditionNotFoundError,
    EditionPublisherNotFoundError,
    EditionRequiresAtLeastOneDatasetError,
    EditionSerializerError,
    EditionStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.aggregates.edition.state import (
    EditionDatasetDistributionNotFoundError,
    SpdxIdentifier,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.context import SealEditionContext
from cora.data.features.seal_edition.decider import decide
from cora.data.ports.edition_serializer import DatasetRef
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.data.aggregates.edition import EditionKind
    from cora.data.ports.distribution_lookup import DistributionLookup
    from cora.data.ports.edition_serializer import EditionSerializer

_STREAM_TYPE = "Edition"
_COMMAND_NAME = "SealEdition"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare seal_edition handler, what `bind()` returns."""

    async def __call__(
        self,
        command: SealEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _resolve_publisher_code(
    command: SealEdition,
    state_facility_code: FacilityCode | None,
) -> str | None:
    if command.publisher_facility_code is not None:
        return command.publisher_facility_code
    if state_facility_code is not None:
        return state_facility_code.value
    return None


def _resolve_license(
    command: SealEdition,
    state_license: SpdxIdentifier | None,
) -> str | None:
    if command.license_override is not None:
        return SpdxIdentifier(command.license_override).value
    if state_license is not None:
        return state_license.value
    return None


def bind(deps: Kernel) -> Handler:
    """Build a seal_edition handler closed over the shared deps."""
    distribution_lookup = cast(
        "DistributionLookup",
        deps.data.distribution_lookup,  # type: ignore[attr-defined]
    )
    per_kind_serializers = cast(
        "dict[EditionKind, EditionSerializer]",
        deps.data.edition_serializers,  # type: ignore[attr-defined]
    )

    async def handler(
        command: SealEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "seal_edition.start",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
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
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.edition_id,
        )
        history: list[EditionEvent] = [from_stored(s) for s in stored]
        state = fold(history)
        if state is None:
            raise EditionNotFoundError(command.edition_id)

        # Cheap in-memory state guards: surface FSM + member-set errors
        # before issuing N Distribution lookup round trips. The decider
        # repeats these checks defensively; keeping them here matches the
        # L15 firing order (status -> empty -> discarded -> production
        # -> distribution -> license).
        if state.status is not EditionStatus.REGISTERED:
            raise EditionCannotSealError(edition_id=state.id, current_status=state.status)
        if not state.dataset_ids:
            raise EditionRequiresAtLeastOneDatasetError(edition_id=state.id)

        # Bulk-load member Datasets (proof of existence + intent + status).
        datasets: dict[UUID, Dataset] = {}
        for dataset_id in state.dataset_ids:
            dataset = await load_dataset(deps.event_store, dataset_id)
            if dataset is None:
                raise DatasetNotFoundError(dataset_id)
            datasets[dataset_id] = dataset

        discarded_ids = tuple(
            sorted(
                dataset_id
                for dataset_id, dataset in datasets.items()
                if dataset.status is DatasetStatus.DISCARDED
            )
        )
        if discarded_ids:
            raise EditionCannotSealOnDiscardedDatasetError(
                edition_id=state.id,
                dataset_ids=discarded_ids,
            )

        offenders = [
            (dataset_id, dataset.intent.value)
            for dataset_id, dataset in datasets.items()
            if dataset.intent is not Intent.PRODUCTION
        ]
        if offenders:
            raise EditionDatasetsNotAllProductionError(
                edition_id=state.id,
                offenders=tuple(sorted(offenders)),
            )

        # Bulk-load canonical Distributions per Dataset (for the
        # serializer's DatasetRef boundary).
        dataset_refs_map: dict[UUID, DatasetRef] = {}
        missing_distribution_ids: list[UUID] = []
        for dataset_id in state.dataset_ids:
            canonical = await distribution_lookup.lookup_canonical_by_dataset(dataset_id)
            if canonical is None:
                missing_distribution_ids.append(dataset_id)
                continue
            dataset_refs_map[dataset_id] = DatasetRef(
                dataset_id=dataset_id,
                uri=canonical.uri,
                checksum=canonical.checksum,
                byte_size=canonical.byte_size,
                encoding=canonical.encoding,
                intent=datasets[dataset_id].intent,
            )

        if missing_distribution_ids:
            raise EditionDatasetDistributionNotFoundError(
                edition_id=state.id,
                dataset_ids=tuple(sorted(missing_distribution_ids)),
            )

        # Resolve effective publisher_facility_code (override or state).
        effective_publisher = _resolve_publisher_code(command, state.publisher_facility_code)
        if effective_publisher is None:
            raise EditionPublisherNotFoundError(facility_code="")
        facility_code_vo = FacilityCode(effective_publisher)
        facility_result = await deps.facility_lookup.lookup_by_code(facility_code_vo)
        if facility_result is None:
            raise EditionPublisherNotFoundError(facility_code=effective_publisher)

        # Resolve effective license (override or state value).
        effective_license = _resolve_license(command, state.license)
        if state.kind in LICENSE_REQUIRED_KINDS and effective_license is None:
            raise EditionLicenseRequiredForKindError(
                edition_id=state.id,
                kind=state.kind,
            )

        # Resolve effective publication_year (override -> state -> sealing year).
        effective_year = (
            command.publication_year_override
            if command.publication_year_override is not None
            else (state.publication_year if state.publication_year is not None else now.year)
        )

        # Per-kind serializer dispatch (inline dict for today; registry
        # hoist trigger is 4th kind adapter).
        serializer = per_kind_serializers.get(state.kind)
        if serializer is None:
            raise EditionSerializerError(
                kind=state.kind,
                reason=f"no serializer adapter wired for kind={state.kind.value!r}",
            )
        dataset_refs = tuple(
            dataset_refs_map[dataset_id] for dataset_id in sorted(state.dataset_ids)
        )

        try:
            serialized = await serializer.serialize(
                edition_id=state.id,
                kind=state.kind,
                title=state.title.value,
                dataset_refs=dataset_refs,
                publisher_facility_code=facility_code_vo,
                creators=state.creators,
                publication_year=effective_year,
                license=(
                    SpdxIdentifier(effective_license) if effective_license is not None else None
                ),
                external_pid=None,
            )
        except EditionSerializerError:
            raise
        except Exception as exc:
            raise EditionSerializerError(
                kind=state.kind,
                reason=str(exc),
            ) from exc

        context = SealEditionContext(
            datasets=datasets,
            dataset_ids_with_canonical_distribution=frozenset(dataset_refs_map.keys()),
            publisher_facility_code=facility_code_vo.value,
            publication_year=effective_year,
            license=effective_license,
            content_hash=serialized.content_hash,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            sealed_by=ActorId(principal_id),
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.edition_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "seal_edition.success",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
            content_hash=serialized.content_hash,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
