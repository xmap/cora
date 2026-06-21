"""Application handler for the `publish_edition` slice.

Update-style handler. Pre-load order per design memo L16:

  1. UnauthorizedError (Authorize.authorize)
  2. Load Edition stream + fold -> EditionNotFoundError if None
  3. (Decider) status guard (EditionCannotPublishError)
  4. (Decider) content_hash invariant
  5. PersistentIdentifierMinter.mint(scheme=DOI, suffix=<edition_id>) -> 502 if raises
  6. Re-load member Datasets + canonical Distributions for re-serialize
  7. EditionSerializer.serialize(..., external_pid=minted_pid) ->
     post-mint sha256 = published_content_hash
  8. Decider emits EditionPublished
"""

from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.edition import (
    EditionCannotPublishError,
    EditionEvent,
    EditionNotFoundError,
    EditionPublishedWithoutContentHashError,
    EditionSerializerError,
    EditionStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.aggregates.edition.state import (
    EditionDatasetDistributionNotFoundError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features.publish_edition.command import PublishEdition
from cora.data.features.publish_edition.context import PublishEditionContext
from cora.data.features.publish_edition.decider import decide
from cora.data.ports.edition_serializer import DatasetRef
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identifier import PersistentIdentifierScheme
from cora.shared.identity import ActorId
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMintError

if TYPE_CHECKING:
    from cora.data.aggregates.edition import EditionKind
    from cora.data.ports.distribution_lookup import DistributionLookup
    from cora.data.ports.edition_serializer import EditionSerializer
    from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMinter

_STREAM_TYPE = "Edition"
_COMMAND_NAME = "PublishEdition"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare publish_edition handler, what `bind()` returns."""

    async def __call__(
        self,
        command: PublishEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a publish_edition handler closed over the shared deps."""
    distribution_lookup = cast(
        "DistributionLookup",
        deps.data.distribution_lookup,  # type: ignore[attr-defined]
    )
    per_kind_serializers = cast(
        "dict[EditionKind, EditionSerializer]",
        deps.data.edition_serializers,  # type: ignore[attr-defined]
    )
    minter = cast("PersistentIdentifierMinter", deps.data.persistent_identifier_minter)  # type: ignore[attr-defined]

    async def handler(
        command: PublishEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "publish_edition.start",
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

        # Cheap state guards (decider repeats defensively).
        if state.status is not EditionStatus.SEALED:
            raise EditionCannotPublishError(edition_id=state.id, current_status=state.status)
        if state.content_hash is None:
            raise EditionPublishedWithoutContentHashError(edition_id=state.id)

        # Mint the DOI (suffix derived from edition_id).
        try:
            minted = await minter.mint(
                scheme=PersistentIdentifierScheme.DOI,
                suffix=str(state.id),
            )
        except PersistentIdentifierMintError:
            raise

        # Re-load member Datasets + canonical Distributions for the
        # re-serialize pass with the minted PID baked in.
        datasets: dict[UUID, Dataset] = {}
        for dataset_id in state.dataset_ids:
            dataset = await load_dataset(deps.event_store, dataset_id)
            if dataset is None:
                raise DatasetNotFoundError(dataset_id)
            datasets[dataset_id] = dataset

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

        # state.publisher_facility_code is set at Sealed (never None).
        assert state.publisher_facility_code is not None
        assert state.publication_year is not None
        facility_code_vo = state.publisher_facility_code

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
                publication_year=state.publication_year,
                license=state.license,
                external_pid=minted,
            )
        except EditionSerializerError:
            raise
        except Exception as exc:
            raise EditionSerializerError(
                kind=state.kind,
                reason=str(exc),
            ) from exc

        context = PublishEditionContext(
            external_pid=minted,
            published_content_hash=serialized.content_hash,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            published_by=ActorId(principal_id),
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
            "publish_edition.success",
            command_name=_COMMAND_NAME,
            edition_id=str(command.edition_id),
            external_pid=f"{minted.scheme.value}:{minted.value}",
            published_content_hash=serialized.content_hash,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
