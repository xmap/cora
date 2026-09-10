"""Deterministic stream-id derivation for Shortfall.

A Shortfall is keyed on the capture observation it judges, one stream
per `capture_path_id`, and the id is derived rather than minted so the
EVENT STORE is what enforces "at most one Shortfall per observation".

## Why derived, when Acquisition and Attestation mint a fresh UUIDv7

Those two are reached once, by a caller who has already decided to
record. This one is reached by a sweep that retries the same candidate
every tick. `_CANDIDATE_SQL` does drop a candidate once its Shortfall
lands, but that read goes through `proj_data_shortfall_summary`, and a
projection lags: between the append and the projection catching up, the
next tick re-selects the same candidate and tries again. With a fresh
id per attempt each of those retries would mint ANOTHER Shortfall
stream, and the record would accumulate one duplicate per tick of
projection lag.

Deriving the id makes the second append a version conflict against a
stream that already exists, so uniqueness is guaranteed by
`expected_version=0` inside the same transaction rather than by a read
that can be stale. Idempotency is not a projection read.

## Derived from the surrogate, never from the path

The input is `capture_path_id`, the opaque surrogate key of the
`run_capture_path` vault row. Never the observed path and never the
filename: both embed `{UserLastName}-{ProposalNumber}` at 2-BM, and a
path-seeded uuid5 would be a confirmation oracle, letting anyone who
could guess a path test that guess against the derived stream id.

`_DATA_SHORTFALL_NAMESPACE` is a fixed sentinel chosen once and frozen;
it MUST NOT change, or existing Shortfall streams become unreachable.
Mirrors `_FEDERATION_SEAL_NAMESPACE` and the
`_DATA_DISTRIBUTION_BACKFILL_NAMESPACE` precedent in this same BC.
"""

from uuid import UUID, uuid5

_DATA_SHORTFALL_NAMESPACE = UUID("01900000-0000-7000-8000-0000da5f0001")


def shortfall_stream_id(capture_path_id: UUID) -> UUID:
    """Derive the deterministic Shortfall stream UUID from the vault
    row's surrogate key.

    The result is used as BOTH the stream id and the `shortfall_id` on
    the payload, same as every other aggregate whose stream id is its
    own identity; the difference here is only that the value is derived
    instead of minted.
    """
    return uuid5(_DATA_SHORTFALL_NAMESPACE, str(capture_path_id))


__all__ = ["shortfall_stream_id"]
