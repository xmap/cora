"""Unit tests for the shared L2 edge-runtime module.

Covers the cancel-orphan-abort context manager (abort-then-reraise,
pass-through on success, failing-abort suppression) and confirms the two
shipped edge-runtime result types structurally satisfy the
`ConductOutcome` contract (the family marker the slice-6 merge collapses
onto).
"""

import asyncio
from uuid import uuid4

import pytest

from cora.api._edge_conductor import RunConductOutcome
from cora.infrastructure.edge_runtime import ConductOutcome, abort_orphan_on_cancel
from cora.operation.conductor import ConductorResult


@pytest.mark.unit
async def test_abort_orphan_on_cancel_aborts_then_reraises() -> None:
    aborted: list[bool] = []

    async def _abort() -> None:
        aborted.append(True)

    with pytest.raises(asyncio.CancelledError):
        async with abort_orphan_on_cancel(_abort):
            raise asyncio.CancelledError

    assert aborted == [True]


@pytest.mark.unit
async def test_abort_orphan_on_cancel_passes_through_on_success() -> None:
    aborted: list[bool] = []

    async def _abort() -> None:
        aborted.append(True)

    async with abort_orphan_on_cancel(_abort):
        pass

    assert aborted == []


@pytest.mark.unit
async def test_abort_orphan_on_cancel_suppresses_a_failing_abort() -> None:
    async def _abort() -> None:
        raise RuntimeError("Run already terminal")

    # The failing abort is swallowed; the CancelledError still propagates.
    with pytest.raises(asyncio.CancelledError):
        async with abort_orphan_on_cancel(_abort):
            raise asyncio.CancelledError


@pytest.mark.unit
async def test_abort_orphan_on_cancel_passes_through_a_noncancel_exception() -> None:
    aborted: list[bool] = []

    async def _abort() -> None:
        aborted.append(True)

    # A non-cancel exception propagates untouched and does NOT trigger the
    # abort. This is the property ComputeRunDriver's try/except nesting relies on
    # to route ComputeTimeoutError / ComputeJobFailedError to its own arms.
    with pytest.raises(RuntimeError, match="boom"):
        async with abort_orphan_on_cancel(_abort):
            raise RuntimeError("boom")

    assert aborted == []


@pytest.mark.unit
def test_edge_runtime_results_satisfy_conduct_outcome() -> None:
    conductor_result = ConductorResult(procedure_id=uuid4(), completed_count=0)
    run_outcome = RunConductOutcome(run_id=uuid4(), status=None)

    assert isinstance(conductor_result, ConductOutcome)
    assert isinstance(run_outcome, ConductOutcome)
