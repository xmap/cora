"""Deterministic stream-id derivation for the Facility aggregate.

The Facility aggregate is a per-code singleton keyed on `FacilityCode`
(the cross-deployment convergent slug per
[[project_structural_scope_design]]). The event store's stream id is
a UUID (per the cross-aggregate convention shared by every other
aggregate read repo and by `EventStore.load`); we derive that UUID
deterministically from the facility code with UUID5 over a fixed
federation namespace.

Two load-bearing properties follow from this derivation:

  - **Live-path uniqueness.** Issuing `register_facility(code="aps")`
    twice produces the same stream_id; the second call collides on
    `append_streams(expected_version=0)` and surfaces as
    `FacilityAlreadyExistsError`. No coordination required.
  - **Bootstrap determinism.** The self-Facility seed at lifespan
    startup (per `_bootstrap.bootstrap_federation`) does not need to
    coordinate ids with `id_generator`; it derives the stream_id from
    the configured `SELF_FACILITY_CODE` and idempotently retries via
    the same ConcurrencyError-as-noop pattern.

`_FEDERATION_FACILITY_NAMESPACE` is a fixed UUID4-shaped sentinel
chosen once and frozen; it MUST NOT change, or existing Facility
streams become unreachable. Mirrors the `_FEDERATION_SEAL_NAMESPACE`
precedent at `cora.federation.aggregates.seal._stream_id`. The
namespace value is intentionally DISTINCT from the Seal namespace so
`facility_stream_id("aps")` and `seal_stream_id("aps")` cannot alias.
"""

from uuid import UUID, uuid5

from cora.shared.facility_code import FacilityCode

_FEDERATION_FACILITY_NAMESPACE = UUID("01900000-0000-7000-8000-0000fac11111")


def facility_stream_id(code: FacilityCode) -> UUID:
    """Derive the deterministic Facility stream UUID from a FacilityCode."""
    return uuid5(_FEDERATION_FACILITY_NAMESPACE, code.value)


__all__ = ["facility_stream_id"]
