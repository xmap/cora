"""Unit tests for `InMemoryCredentialLookup` (the test-tier adapter).

Mirrors the production `PostgresCredentialLookup` contract under
the in-memory adapter:
  - `register()` installs a credential summary keyed by id.
  - `lookup()` returns the seeded `CredentialLookupResult`.
  - `lookup()` returns `None` for an unknown id (None-on-missing
    semantics; deciders translate to domain errors).
  - The ctor-side `seed=` mapping is an alternative bulk-seed path.
  - The adapter satisfies the `CredentialLookup` Protocol shape.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.adapters.in_memory_credential_lookup import (
    InMemoryCredentialLookup,
)
from cora.infrastructure.ports import (
    CredentialLookup,
    CredentialLookupResult,
)
from cora.shared.facility_code import FacilityCode


@pytest.mark.unit
async def test_register_then_lookup_returns_seeded_result() -> None:
    lookup = InMemoryCredentialLookup()
    cid = uuid4()
    lookup.register(
        credential_id=cid,
        facility_id="aps-2bm",
        purpose="SealOnlineSigning",
        status="Active",
    )

    result = await lookup.lookup(cid)
    assert result is not None
    assert result.id == cid
    assert result.facility_id == FacilityCode("aps-2bm")
    assert result.purpose == "SealOnlineSigning"
    assert result.status == "Active"


@pytest.mark.unit
async def test_lookup_unknown_id_returns_none() -> None:
    lookup = InMemoryCredentialLookup()
    lookup.register(
        credential_id=uuid4(),
        facility_id="aps-2bm",
        purpose="SealOnlineSigning",
        status="Active",
    )

    result = await lookup.lookup(uuid4())
    assert result is None


@pytest.mark.unit
async def test_lookup_on_empty_adapter_returns_none() -> None:
    lookup = InMemoryCredentialLookup()
    assert await lookup.lookup(uuid4()) is None


@pytest.mark.unit
async def test_register_overwrites_existing_record() -> None:
    """Re-registering the same id updates the stored summary; the
    projection worker's UPDATE semantics are mirrored here so handler
    tests can simulate rotation / revocation status transitions."""
    lookup = InMemoryCredentialLookup()
    cid = uuid4()
    lookup.register(
        credential_id=cid,
        facility_id="aps-2bm",
        purpose="SealOnlineSigning",
        status="Active",
    )
    lookup.register(
        credential_id=cid,
        facility_id="aps-2bm",
        purpose="SealOnlineSigning",
        status="Rotating",
    )

    result = await lookup.lookup(cid)
    assert result is not None
    assert result.status == "Rotating"


@pytest.mark.unit
async def test_ctor_seed_mapping_populates_records() -> None:
    cid_online = uuid4()
    cid_offline = uuid4()
    seed = {
        cid_online: CredentialLookupResult(
            id=cid_online,
            facility_id=FacilityCode("aps-2bm"),
            purpose="SealOnlineSigning",
            status="Active",
        ),
        cid_offline: CredentialLookupResult(
            id=cid_offline,
            facility_id=FacilityCode("aps-2bm"),
            purpose="SealOfflineRoot",
            status="Active",
        ),
    }
    lookup = InMemoryCredentialLookup(seed=seed)

    online = await lookup.lookup(cid_online)
    offline = await lookup.lookup(cid_offline)
    assert online is not None
    assert online.purpose == "SealOnlineSigning"
    assert offline is not None
    assert offline.purpose == "SealOfflineRoot"


@pytest.mark.unit
async def test_returns_credentials_in_every_status() -> None:
    """Per the Protocol contract, the adapter returns rows in ANY
    status (Active / Rotating / Revoked). The decider partitions on
    `status == "Active"` so it can tell "no credential" from
    "credential exists but inactive"."""
    lookup = InMemoryCredentialLookup()
    cid_rotating = uuid4()
    cid_revoked = uuid4()
    lookup.register(
        credential_id=cid_rotating,
        facility_id="aps-2bm",
        purpose="SealOnlineSigning",
        status="Rotating",
    )
    lookup.register(
        credential_id=cid_revoked,
        facility_id="aps-2bm",
        purpose="SealOfflineRoot",
        status="Revoked",
    )

    rot = await lookup.lookup(cid_rotating)
    rev = await lookup.lookup(cid_revoked)
    assert rot is not None and rot.status == "Rotating"
    assert rev is not None and rev.status == "Revoked"


@pytest.mark.unit
def test_satisfies_credential_lookup_protocol() -> None:
    """Structural check: the adapter is assignable to the port type.

    Runtime `isinstance` against a `Protocol` is not used (the Protocol
    is non-runtime-checkable by design); a typed assignment is the
    canonical way to pin the structural conformance."""
    lookup: CredentialLookup = InMemoryCredentialLookup()
    assert lookup is not None
