"""In-process `EditionSerializer` stubs for tests.

Three flavors:

  - `StubEditionSerializer`: returns a pre-configured `SerializedEdition`
    on every call. Useful when the test cares about the seal / publish
    handler path, not the actual bytes.
  - `FailingEditionSerializer`: raises a pre-configured exception on
    every call. Used to exercise the 502 `EditionSerializerError` path
    inside the seal handler.
  - `PerKindEditionSerializer`: dispatches by `EditionKind` to a map
    of per-kind serializers. Useful for the seal handler dispatch
    contract; behaves as `RoCrate12Adapter` for ROCrate plus stub for
    other kinds when needed.

None of these adapters touch the network or filesystem; all are pure
in-process.
"""

from collections.abc import Mapping
from uuid import UUID

from cora.data.aggregates.edition.state import (
    Creator,
    EditionKind,
    SpdxIdentifier,
)
from cora.data.ports.edition_serializer import (
    DatasetRef,
    EditionSerializer,
    SerializedEdition,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier


class StubEditionSerializer:
    """Returns a fixed `SerializedEdition` on every call."""

    def __init__(
        self,
        *,
        content_hash: str = "0" * 64,
        bytes_uri: str = "data:application/octet-stream;base64,",
        content_type: str = "application/octet-stream",
    ) -> None:
        self._result = SerializedEdition(
            content_hash=content_hash,
            bytes_uri=bytes_uri,
            content_type=content_type,
        )

    async def serialize(
        self,
        *,
        edition_id: UUID,
        kind: EditionKind,
        title: str,
        dataset_refs: tuple[DatasetRef, ...],
        publisher_facility_code: FacilityCode,
        creators: tuple[Creator, ...],
        publication_year: int,
        license: SpdxIdentifier | None,
        external_pid: PersistentIdentifier | None,
    ) -> SerializedEdition:
        _ = (
            edition_id,
            kind,
            title,
            dataset_refs,
            publisher_facility_code,
            creators,
            publication_year,
            license,
            external_pid,
        )
        return self._result


class FailingEditionSerializer:
    """Raises a pre-configured exception on every call."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def serialize(
        self,
        *,
        edition_id: UUID,
        kind: EditionKind,
        title: str,
        dataset_refs: tuple[DatasetRef, ...],
        publisher_facility_code: FacilityCode,
        creators: tuple[Creator, ...],
        publication_year: int,
        license: SpdxIdentifier | None,
        external_pid: PersistentIdentifier | None,
    ) -> SerializedEdition:
        _ = (
            edition_id,
            kind,
            title,
            dataset_refs,
            publisher_facility_code,
            creators,
            publication_year,
            license,
            external_pid,
        )
        raise self._exc


class PerKindEditionSerializer:
    """Dispatches `serialize` calls by `EditionKind`.

    Raises `KeyError` (becomes EditionSerializerError when wrapped at
    handler-level) when a kind is not registered.
    """

    def __init__(self, per_kind: Mapping[EditionKind, EditionSerializer]) -> None:
        self._per_kind: dict[EditionKind, EditionSerializer] = dict(per_kind)

    async def serialize(
        self,
        *,
        edition_id: UUID,
        kind: EditionKind,
        title: str,
        dataset_refs: tuple[DatasetRef, ...],
        publisher_facility_code: FacilityCode,
        creators: tuple[Creator, ...],
        publication_year: int,
        license: SpdxIdentifier | None,
        external_pid: PersistentIdentifier | None,
    ) -> SerializedEdition:
        serializer = self._per_kind[kind]
        return await serializer.serialize(
            edition_id=edition_id,
            kind=kind,
            title=title,
            dataset_refs=dataset_refs,
            publisher_facility_code=publisher_facility_code,
            creators=creators,
            publication_year=publication_year,
            license=license,
            external_pid=external_pid,
        )


__all__ = [
    "FailingEditionSerializer",
    "PerKindEditionSerializer",
    "StubEditionSerializer",
]
