"""HTTP setup for the Data BC.

`register_data_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Data
does not re-register them.

## Loop-collapse pattern

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry, no new handler function. Mirrors every
other BC.

  - 400 (validation): InvalidDatasetNameError, InvalidDatasetUriError,
    InvalidDatasetChecksumError, InvalidDatasetByteSizeError,
    InvalidDatasetEncodingError, InvalidDerivedFromError,
    InvalidDatasetDiscardReasonError (7b)
  - 404: DatasetNotFoundError (raised by the discard_dataset decider
    when the target stream is empty; also surfaced by get_dataset's
    route HTTPException pathway), plus the renamed cross-aggregate
    not-found family: ProducingRunNotFoundError, LinkedSubjectNotFoundError,
    DerivedFromDatasetsNotFoundError (per the locked <X>NotFoundError -> 404
    taxonomy, clusters 2 / 4 of the 2026-05-22 audit).
  - 409 (defensive AlreadyExists): DatasetAlreadyExistsError
  - 409 (lineage state): DerivedFromDatasetsDiscardedError (referenced
    upstream Dataset is in Discarded status, a real state conflict).
  - 409 (Dataset transition guards, 7b + 7e): DatasetCannotDiscardError,
    DatasetCannotPromoteError, DatasetAlreadyPromotedError
  - 400 (validation, 7e adds): InvalidPromotionReasonError
  - 400 (validation, 12c adds): InvalidUsedCalibrationsError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.data.aggregates.acquisition import (
    AcquisitionAlreadyExistsError,
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionRunNotFoundError,
    InvalidAcquisitionCapturedAtError,
    InvalidAcquisitionEvidenceError,
    InvalidAcquisitionSettingsError,
)
from cora.data.aggregates.attestation import (
    AttestationAlreadyExistsError,
    AttestationChecksumEvidenceMismatchError,
    AttestationDistributionDatasetMismatchError,
    AttestationDistributionNotFoundError,
    AttestationKindNotYetSupportedError,
    AttestationKindRejectsDistributionError,
    AttestationKindRequiresDistributionError,
    AttestationTreeChecksumNotYetSupportedError,
    InvalidAttestationEvidenceError,
    InvalidAttestationKindError,
    InvalidAttestationOutcomeError,
)
from cora.data.aggregates.dataset import (
    DatasetAlreadyExistsError,
    DatasetAlreadyPromotedError,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetCannotDiscardError,
    DatasetCannotPromoteError,
    DatasetNotFoundError,
    DerivedFromDatasetsDiscardedError,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetDiscardReasonError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDemotionReasonError,
    InvalidDerivedFromError,
    InvalidPromotionReasonError,
    InvalidUsedCalibrationsError,
    LinkedSubjectNotFoundError,
    ProducingProcedureNotFoundError,
    ProducingProcedureNotTerminalError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.distribution import (
    DefaultStorageSupplyBootstrapError,
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumAlgorithmMismatchError,
    DistributionChecksumMismatchError,
    DistributionSupplyNotFoundError,
    InvalidAccessProtocolError,
    InvalidDistributionByteSizeError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidDistributionUriError,
    UnmappedDistributionUriSchemeError,
)
from cora.data.aggregates.edition import (
    EditionAlreadyExistsError,
    EditionCannotBeEmptyError,
    EditionCannotBindToDiscardedDatasetError,
    EditionCannotPublishError,
    EditionCannotSealError,
    EditionCannotSealOnDiscardedDatasetError,
    EditionCannotWithdrawError,
    EditionDatasetAlreadyMemberError,
    EditionDatasetDistributionNotFoundError,
    EditionDatasetNotMemberError,
    EditionDatasetsNotAllProductionError,
    EditionLicenseRequiredForKindError,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionPublishedWithoutContentHashError,
    EditionPublisherNotFoundError,
    EditionRequiresAtLeastOneDatasetError,
    EditionSerializerError,
    EditionWithdrawnWithoutPersistentIdError,
    EmptyDatasetIdsAtRegistrationError,
    InvalidCreatorsError,
    InvalidEditionKindError,
    InvalidEditionTitleError,
    InvalidEditionWithdrawalReasonError,
    InvalidPublicationYearError,
    InvalidSpdxIdentifierError,
    PersistentIdentifierMinterTombstoneError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features import (
    add_dataset_to_edition,
    demote_dataset,
    discard_dataset,
    get_dataset,
    list_datasets,
    promote_dataset,
    publish_edition,
    record_acquisition,
    record_attestation,
    register_dataset,
    register_distribution,
    register_edition,
    remove_dataset_from_edition,
    seal_edition,
    withdraw_edition,
)
from cora.data.ports.checksum_verifier import ChecksumVerifierUnsupportedSchemeError
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMintError


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error (Invalid<X>...)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_lineage_state_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for lineage-state conflicts on dataset
    registration.

    Was previously named `_handle_cross_agg_conflict` and covered
    cross-aggregate Missing*Error references too. Per the locked
    `<X>NotFoundError -> 404` taxonomy, the renamed
    `ProducingRunNotFoundError` / `LinkedSubjectNotFoundError` /
    `DerivedFromDatasetsNotFoundError` now route through
    `_handle_not_found`. The only remaining 409-mapped family here is
    `DerivedFromDatasetsDiscardedError` (referenced upstream Dataset
    is in Discarded status, a real state conflict, not a
    missing-reference). Same JSON shape as before.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition / mutation-guard errors.

    7b adds `DatasetCannotDiscardError` (Discarded terminal). 7e adds
    `DatasetCannotPromoteError` (covers Discarded / Run-not-Completed
    / lineage-not-Production branches) and `DatasetAlreadyPromotedError`
    (strict-not-idempotent re-promote). All map to 409 +
    `{"detail": str(exc)}`. Adding a new mutation guard is one
    extra entry in the tuple.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_upstream_port_failure(request: Request, exc: Exception) -> JSONResponse:
    """502 handler for upstream-port failure (serializer, PersistentIdentifierMinter tombstone)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


async def _handle_invariant_violation(request: Request, exc: Exception) -> JSONResponse:
    """500 handler for defensive invariant violations (impossible-by-state)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


def register_data_routes(app: FastAPI) -> None:
    """Attach Data slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_dataset.router)
    app.include_router(discard_dataset.router)
    app.include_router(promote_dataset.router)
    app.include_router(demote_dataset.router)
    app.include_router(get_dataset.router)
    app.include_router(list_datasets.router)
    app.include_router(record_acquisition.router)
    app.include_router(register_distribution.router)
    app.include_router(register_edition.router)
    app.include_router(add_dataset_to_edition.router)
    app.include_router(remove_dataset_from_edition.router)
    app.include_router(seal_edition.router)
    app.include_router(publish_edition.router)
    app.include_router(withdraw_edition.router)
    app.include_router(record_attestation.router)
    for validation_cls in (
        InvalidDatasetNameError,
        InvalidDatasetUriError,
        InvalidDatasetChecksumError,
        InvalidDatasetByteSizeError,
        InvalidDatasetEncodingError,
        InvalidDerivedFromError,
        InvalidDatasetDiscardReasonError,
        # 7e validation guard: free-form promotion reason length check.
        InvalidPromotionReasonError,
        # post-Q4 compensation slice: free-form demotion reason length check.
        InvalidDemotionReasonError,
        # 12c validation guard: cardinality cap on AsShot citation set.
        InvalidUsedCalibrationsError,
        # Acquisition shape-only guards (settings / evidence / captured_at).
        InvalidAcquisitionSettingsError,
        InvalidAcquisitionEvidenceError,
        InvalidAcquisitionCapturedAtError,
        # Distribution VO validation + lifespan-bootstrap fail-loud branches.
        # All produce {"detail": str(exc)} 400 responses. The bootstrap
        # classes are raised at app startup before any route opens; the
        # registration here is defensive in case a test-harness exercises
        # them via direct decider invocation.
        InvalidDistributionUriError,
        InvalidDistributionChecksumError,
        InvalidDistributionByteSizeError,
        InvalidDistributionEncodingError,
        InvalidAccessProtocolError,
        UnmappedDistributionUriSchemeError,
        DefaultStorageSupplyBootstrapError,
        # Edition VO validation: title, kind, license, year, withdrawal
        # reason, creators (cardinality + duplicate detection +
        # affiliation length), empty-dataset-ids-at-registration. All
        # produce 400 `{"detail": str(exc)}`.
        InvalidEditionTitleError,
        InvalidEditionKindError,
        InvalidPublicationYearError,
        InvalidSpdxIdentifierError,
        InvalidEditionWithdrawalReasonError,
        InvalidCreatorsError,
        EmptyDatasetIdsAtRegistrationError,
        # Attestation record-slice 400 family: closed-enum re-checks,
        # evidence VO shape, kind-not-yet-supported (handler-tier),
        # and the verifier-port unsupported-scheme dispatch error.
        InvalidAttestationKindError,
        InvalidAttestationOutcomeError,
        InvalidAttestationEvidenceError,
        AttestationKindNotYetSupportedError,
        AttestationTreeChecksumNotYetSupportedError,
        ChecksumVerifierUnsupportedSchemeError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        DatasetNotFoundError,
        # Edition NotFoundError family: stream-empty + publisher Facility
        # lookup miss + member Dataset not in set + member Dataset has no
        # canonical Distribution. All produce 404 `{"detail": str(exc)}`.
        EditionNotFoundError,
        EditionPublisherNotFoundError,
        EditionDatasetNotMemberError,
        EditionDatasetDistributionNotFoundError,
        # Per the locked <X>NotFoundError -> 404 taxonomy (cluster 4 of
        # the 2026-05-22 audit), the renamed cross-aggregate not-found
        # family now routes through _handle_not_found instead of the
        # old _handle_cross_agg_conflict (renamed _handle_lineage_state_conflict).
        ProducingRunNotFoundError,
        ProducingProcedureNotFoundError,
        LinkedSubjectNotFoundError,
        DerivedFromDatasetsNotFoundError,
        # Acquisition cross-aggregate not-found (producing Asset / Run).
        AcquisitionAssetNotFoundError,
        AcquisitionRunNotFoundError,
        # Distribution cross-BC not-found family.
        DistributionSupplyNotFoundError,
        # Attestation Distribution-binding not-found family. The Dataset
        # not-found pathway reuses DatasetNotFoundError (already
        # registered above); only the new Distribution-specific class
        # needs registration.
        AttestationDistributionNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        DatasetAlreadyExistsError,
        AcquisitionAlreadyExistsError,
        DistributionAlreadyExistsError,
        # Edition defensive 409: same-stream-id race at register decider.
        EditionAlreadyExistsError,
        AttestationAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_record_cls in (AcquisitionCannotRecordWithoutCapturingError,):
        app.add_exception_handler(cannot_record_cls, _handle_cannot_transition)
    for lineage_state_cls in (
        DerivedFromDatasetsDiscardedError,
        # Registration-time cross-aggregate state conflict: the referenced
        # producing Procedure is not terminal (its actuation kind isn't final).
        ProducingProcedureNotTerminalError,
    ):
        app.add_exception_handler(lineage_state_cls, _handle_lineage_state_conflict)
    for cannot_transition_cls in (
        DatasetCannotDiscardError,
        # 7e transition / promotion guards. Both surface as 409 with
        # the same body shape; cannot-promote covers Discarded /
        # Run-not-Completed / lineage-not-Production branches; already-
        # promoted is the strict-not-idempotent re-promote rejection.
        DatasetCannotPromoteError,
        DatasetAlreadyPromotedError,
        # post-Q4 compensation-slice demote guards. cannot-demote
        # covers Discarded / Trial branches; already-retracted is the
        # strict-not-idempotent re-demote rejection.
        DatasetCannotDemoteError,
        DatasetAlreadyRetractedError,
        # Distribution registration-time guards: storage-kind requirement,
        # Discarded-Dataset binding rejection, and the byte-identical-copy
        # invariants (checksum + byte_size must match parent Dataset).
        # All 409 with {"detail": str(exc)}.
        DistributionCannotRegisterOnNonStorageSupplyError,
        DistributionCannotRegisterOnDiscardedDatasetError,
        DistributionChecksumAlgorithmMismatchError,
        DistributionChecksumMismatchError,
        DistributionByteSizeMismatchError,
        # Edition mutation / transition guards. All 409 with
        # `{"detail": str(exc)}`. Covers add / remove state guards,
        # state-FSM transition guards, license-required-for-kind,
        # all-Production-or-reject, member-Discarded, member-missing-
        # Distribution, last-dataset-remove, and the bind-to-Discarded
        # Dataset rejection shared with register / add slices.
        EditionNotInRegisteredStateError,
        EditionDatasetAlreadyMemberError,
        EditionCannotBeEmptyError,
        EditionCannotBindToDiscardedDatasetError,
        EditionCannotSealError,
        EditionRequiresAtLeastOneDatasetError,
        EditionDatasetsNotAllProductionError,
        EditionCannotSealOnDiscardedDatasetError,
        EditionLicenseRequiredForKindError,
        EditionCannotPublishError,
        EditionCannotWithdrawError,
        # Attestation record-slice 409 family: kind/distribution_id
        # dual-binding violations, Distribution.dataset_id mismatch,
        # belt-and-braces checksum mismatch against the loaded
        # Distribution row.
        AttestationKindRequiresDistributionError,
        AttestationKindRejectsDistributionError,
        AttestationDistributionDatasetMismatchError,
        AttestationChecksumEvidenceMismatchError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    for upstream_port_cls in (
        # Serializer adapter failure at seal / publish time, and
        # PersistentIdentifierMinter.tombstone failure at withdraw time. Both 502 because
        # the upstream port (serializer / DataCite) is the failure source,
        # not a domain-state conflict.
        EditionSerializerError,
        PersistentIdentifierMinterTombstoneError,
        # PersistentIdentifierMinter.mint failure at publish time. 502: the DataCite
        # authority (the upstream port) is the failure source.
        PersistentIdentifierMintError,
    ):
        app.add_exception_handler(upstream_port_cls, _handle_upstream_port_failure)
    for invariant_cls in (
        # Defensive invariants: impossible-by-state under happy-path; 500
        # because each signals a contract-breaking adapter swap or
        # malformed stream. Sealed-without-content_hash (publish);
        # Published-without-external_pid (withdraw).
        EditionPublishedWithoutContentHashError,
        EditionWithdrawnWithoutPersistentIdError,
    ):
        app.add_exception_handler(invariant_cls, _handle_invariant_violation)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
