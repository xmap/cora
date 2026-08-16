"""Unit tests for `CaptureExperimentIdentityReader`
(cora.api._capture_experiment_identity_reader).

Covers the one-shot read-three-roles-and-vault-once contract, the two
named traps ("Unknown" and empty treated as absent; no substrate time
means skip, never synthesize), that one bad PV does not abort the
sweep over the rest, and that every failure mode -- a dead PV, an
uncoercible reading, or the vault write itself -- is caught and logged
rather than raised.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.api._capture_experiment_identity_reader import (
    ROLE_ESAF_DOI_NUMBER,
    ROLE_ESAF_NUMBER,
    ROLE_PROPOSAL_NUMBER,
    CaptureExperimentIdentityReader,
    resolved_experiment_identity_text,
)
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    Measurement,
)
from cora.run.aggregates.run import ExperimentIdentity, InMemoryExperimentIdentityStore
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-000000007114")

_EXPERIMENT_IDENTITY_PVS = {
    _CODE: {
        ROLE_PROPOSAL_NUMBER: "2bmb:TomoScan:ProposalNumber",
        ROLE_ESAF_NUMBER: "2bmb:TomoScan:ESAFNumber",
        ROLE_ESAF_DOI_NUMBER: "2bmb:TomoScan:ESAFDOINumber",
    }
}


def _reading(value: object, *, produced_at: datetime | None = _NOW) -> Measurement:
    return Measurement(  # type: ignore[arg-type]
        value=value,
        kind="Scalar",
        quality="Good",  # type: ignore[arg-type]
        produced_at=produced_at,
        units=None,
    )


class _FakeControlPort:
    """Scripted `read()`-only fake, mirroring `_capture_baseline_reader`'s own."""

    def __init__(self, script: dict[str, Measurement | Exception]) -> None:
        self._script = script

    async def read(self, address: str) -> Measurement:
        outcome = self._script[address]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _reader(
    *,
    control_port: _FakeControlPort,
    store: InMemoryExperimentIdentityStore | None = None,
    experiment_identity_pvs: dict[str, dict[str, str]] | None = None,
) -> tuple[CaptureExperimentIdentityReader, InMemoryExperimentIdentityStore]:
    vault = store if store is not None else InMemoryExperimentIdentityStore()
    reader = CaptureExperimentIdentityReader(
        deps=build_deps(ids=[uuid4() for _ in range(10)], now=_NOW),
        control_port=control_port,  # type: ignore[arg-type]
        experiment_identity_pvs=experiment_identity_pvs
        if experiment_identity_pvs is not None
        else _EXPERIMENT_IDENTITY_PVS,
        store=vault,
    )
    return reader, vault


# ---------------------------------------------------------------------------
# resolved_experiment_identity_text: the shared absent-value rule (Trap 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["Unknown", "", "  ", "  Unknown  ", 42, None, 3.14],
)
def test_resolved_experiment_identity_text_treats_these_as_absent(value: object) -> None:
    assert resolved_experiment_identity_text(value) is None


@pytest.mark.unit
def test_resolved_experiment_identity_text_strips_and_returns_a_real_value() -> None:
    assert resolved_experiment_identity_text("  12345  ") == "12345"
    assert resolved_experiment_identity_text("12345") == "12345"


# ---------------------------------------------------------------------------
# CaptureExperimentIdentityReader.read
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_read_with_all_roles_present_vaults_all_three() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading("12345"),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("10.1234/esaf.67890"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number == "12345"
    assert row.esaf_number == "67890"
    assert row.esaf_doi_number == "10.1234/esaf.67890"
    assert row.proposal_number_observed_at == _NOW


@pytest.mark.unit
async def test_read_for_an_undeclared_code_is_a_no_op() -> None:
    reader, vault = _reader(control_port=_FakeControlPort({}))

    await reader.read("some-other-code", _RUN_ID)

    assert await vault.get(_RUN_ID) is None


@pytest.mark.unit
async def test_read_with_no_roles_declared_for_the_code_is_a_no_op() -> None:
    reader, vault = _reader(control_port=_FakeControlPort({}), experiment_identity_pvs={_CODE: {}})

    await reader.read(_CODE, _RUN_ID)

    assert await vault.get(_RUN_ID) is None


@pytest.mark.unit
async def test_a_partially_declared_code_reads_only_its_declared_roles() -> None:
    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading("12345")})
    reader, vault = _reader(
        control_port=port,
        experiment_identity_pvs={_CODE: {ROLE_PROPOSAL_NUMBER: "2bmb:TomoScan:ProposalNumber"}},
    )

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number == "12345"
    assert row.esaf_number is None
    assert row.esaf_doi_number is None


@pytest.mark.unit
async def test_unknown_literal_is_treated_as_absent_but_the_rest_of_the_sweep_survives() -> None:
    """Trap 1: the substrate's own default reads as a plausible string
    unless explicitly rejected."""
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading("Unknown"),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number is None
    assert row.esaf_number == "67890"
    assert row.esaf_doi_number is None


@pytest.mark.unit
async def test_empty_string_is_treated_as_absent() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading(""),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading(""),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number is None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_reading_with_no_substrate_time_is_skipped_not_synthesized() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading("12345", produced_at=None),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number is None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_every_role_absent_writes_nothing() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": _reading("Unknown"),
            "2bmb:TomoScan:ESAFNumber": _reading(""),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    assert await vault.get(_RUN_ID) is None


@pytest.mark.unit
async def test_a_dead_pv_does_not_abort_the_sweep_over_the_rest() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": ControlNotConnectedError(
                "2bmb:TomoScan:ProposalNumber"
            ),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.proposal_number is None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_a_timed_out_pv_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": ControlTimeoutError(
                "2bmb:TomoScan:ProposalNumber", 5.0
            ),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_an_access_denied_pv_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": ControlAccessDeniedError(
                "2bmb:TomoScan:ProposalNumber"
            ),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_a_value_coercion_error_is_skipped() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": ControlValueCoercionError(
                "2bmb:TomoScan:ProposalNumber", "structured", "Scalar"
            ),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_an_unexpected_read_exception_is_caught_and_the_sweep_survives() -> None:
    port = _FakeControlPort(
        {
            "2bmb:TomoScan:ProposalNumber": RuntimeError("boom"),
            "2bmb:TomoScan:ESAFNumber": _reading("67890"),
            "2bmb:TomoScan:ESAFDOINumber": _reading("Unknown"),
        }
    )
    reader, vault = _reader(control_port=port)

    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert row is not None
    assert row.esaf_number == "67890"


@pytest.mark.unit
async def test_vault_write_failure_is_caught_and_does_not_raise() -> None:
    class _FailingStore(InMemoryExperimentIdentityStore):
        async def upsert(self, **kwargs: object) -> None:  # type: ignore[override]
            msg = "boom"
            raise RuntimeError(msg)

    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading("12345")})
    reader, _vault = _reader(
        control_port=port,
        store=_FailingStore(),
        experiment_identity_pvs={_CODE: {ROLE_PROPOSAL_NUMBER: "2bmb:TomoScan:ProposalNumber"}},
    )

    await reader.read(_CODE, _RUN_ID)  # must not raise


@pytest.mark.unit
async def test_read_is_idempotent_on_run_id() -> None:
    """A retry (e.g. after a transient promotion-adjacent failure)
    overwrites rather than duplicating: mirrors the vault's own PK
    contract, exercised here through the reader's own call shape."""
    port = _FakeControlPort({"2bmb:TomoScan:ProposalNumber": _reading("12345")})
    reader, vault = _reader(
        control_port=port,
        experiment_identity_pvs={_CODE: {ROLE_PROPOSAL_NUMBER: "2bmb:TomoScan:ProposalNumber"}},
    )

    await reader.read(_CODE, _RUN_ID)
    await reader.read(_CODE, _RUN_ID)

    row = await vault.get(_RUN_ID)
    assert isinstance(row, ExperimentIdentity)
    assert row.proposal_number == "12345"
