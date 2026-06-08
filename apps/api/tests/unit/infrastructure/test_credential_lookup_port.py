"""Unit tests for the `CredentialLookup` port value types.

Pins the `CredentialLookupResult` dataclass contract that the Seal
deciders rely on: required fields, frozen-immutability, the
string-typed `purpose` / `status` columns (kept as `str` so the port
stays free of Federation BC enum imports per the kernel-tier
`depends_on = []` discipline), and the `FacilityCode`-typed
`facility_id` field (post Slice 3 of project_structural_scope_design;
the VO is the cross-deployment convergent identity at the port surface).
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.infrastructure.ports import (
    CredentialLookup,
    CredentialLookupResult,
)
from cora.infrastructure.ports.credential_lookup import (
    CredentialLookup as CredentialLookupFromModule,
)
from cora.infrastructure.ports.credential_lookup import (
    CredentialLookupResult as CredentialLookupResultFromModule,
)
from cora.shared.facility_code import FacilityCode


@pytest.mark.unit
def test_credential_lookup_result_carries_all_four_fields() -> None:
    cid = uuid4()
    result = CredentialLookupResult(
        id=cid,
        facility_id=FacilityCode("aps-2bm"),
        purpose="SealOnlineSigning",
        status="Active",
    )
    assert result.id == cid
    assert result.facility_id == FacilityCode("aps-2bm")
    assert result.purpose == "SealOnlineSigning"
    assert result.status == "Active"


@pytest.mark.unit
def test_credential_lookup_result_is_frozen() -> None:
    result = CredentialLookupResult(
        id=uuid4(),
        facility_id=FacilityCode("aps-2bm"),
        purpose="SealOfflineRoot",
        status="Active",
    )
    with pytest.raises(FrozenInstanceError):
        result.status = "Revoked"  # type: ignore[misc]


@pytest.mark.unit
def test_credential_lookup_result_supports_value_equality() -> None:
    cid = uuid4()
    a = CredentialLookupResult(
        id=cid,
        facility_id=FacilityCode("aps-2bm"),
        purpose="SealOnlineSigning",
        status="Active",
    )
    b = CredentialLookupResult(
        id=cid,
        facility_id=FacilityCode("aps-2bm"),
        purpose="SealOnlineSigning",
        status="Active",
    )
    assert a == b


@pytest.mark.unit
def test_credential_lookup_result_purpose_and_status_are_str() -> None:
    """Port keeps `purpose` and `status` as plain `str` so callers (Seal
    deciders) compare via literals (`== "SealOnlineSigning"`,
    `== "Active"`) and the port stays free of Federation BC enums."""
    result = CredentialLookupResult(
        id=uuid4(),
        facility_id=FacilityCode("aps-2bm"),
        purpose="SealOnlineSigning",
        status="Active",
    )
    assert isinstance(result.purpose, str)
    assert isinstance(result.status, str)


@pytest.mark.unit
def test_credential_lookup_protocol_re_exported_from_ports_package() -> None:
    """Both names are exported from `cora.infrastructure.ports` (the
    canonical import path) AND from the per-port submodule. Pin both
    so an accidental removal from `__init__.py` surfaces here."""
    assert CredentialLookup is CredentialLookupFromModule
    assert CredentialLookupResult is CredentialLookupResultFromModule
