"""Cross-BC seam tests for the ActuationKind provenance gate.

The gate spans two bounded contexts: the Operation BC observes the
actuation kind during a conduct (`ConductorResult.actuation_kind`, an
`ActuationKind` enum) and the Data BC blocks promoting simulator-origin
Datasets (raw-string match against its local `ACTUATION_KIND_*`
constants). The two never share a type: Operation owns the enum, Data
stores the foreign value as a string, mirroring the
`producing_run_end_state` snapshot pattern.

That decoupling buys forward-compat but creates one drift risk: if the
enum's string values and the Data constants ever disagree, the gate
silently stops blocking. These tests pin the two vocabularies together
and prove the register -> fold -> promote chain composes with the value
the Operation BC actually emits.

The Conductor's production of the kind is pinned in
`tests/unit/operation/test_conductor.py`; this file only pins the seam.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    ACTUATION_KIND_HYBRID,
    ACTUATION_KIND_PHYSICAL,
    ACTUATION_KIND_SIMULATED,
    DatasetCannotPromoteError,
    DatasetPromoted,
)
from cora.data.aggregates.dataset.evolver import fold
from cora.data.features import promote_dataset, register_dataset
from cora.data.features.promote_dataset import DatasetPromotionContext, PromoteDataset
from cora.data.features.register_dataset import DatasetRegistrationContext, RegisterDataset
from cora.operation.ports.control_port import ActuationKind
from cora.run.aggregates.run import Run, RunName, RunStatus
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
_ACTOR = ActorId(UUID("01900000-0000-7000-8000-0000000000aa"))
_GOOD_SHA256 = "a" * 64


@pytest.mark.unit
def test_operation_actuation_kind_values_match_data_gate_constants() -> None:
    """The enum the Operation BC emits and the constants the Data gate
    blocks are the same strings. If this fails the gate silently stops
    catching rehearsal data."""
    assert ActuationKind.PHYSICAL.value == ACTUATION_KIND_PHYSICAL
    assert ActuationKind.SIMULATED.value == ACTUATION_KIND_SIMULATED
    assert ActuationKind.HYBRID.value == ACTUATION_KIND_HYBRID


@pytest.mark.unit
def test_every_actuation_kind_is_classified_by_the_data_gate() -> None:
    """Every ActuationKind member must be either blocked or explicitly
    allowed by the Data gate. The promote guard is exact-membership, so a
    future enum member added without a matching block constant would
    silently become promotable. This forces a conscious classify-it
    decision when the enum grows."""
    blocked = {ACTUATION_KIND_SIMULATED, ACTUATION_KIND_HYBRID}
    allowed = {ACTUATION_KIND_PHYSICAL}
    for kind in ActuationKind:
        assert kind.value in blocked | allowed, (
            f"ActuationKind.{kind.name} is neither blocked nor allowed by the "
            "Data promote gate; classify it (add to promote_dataset guard 6, or "
            "to the allowed set with rationale) before shipping the new kind"
        )


def _completed_run() -> Run:
    return Run(
        id=uuid4(),
        name=RunName("seed-run"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=RunStatus.COMPLETED,
    )


def _register_then_promote(actuation_kind: str | None) -> list[DatasetPromoted]:
    """Register a Dataset carrying `actuation_kind` from a Completed Run,
    fold to state, then attempt promotion. Returns the promote events or
    raises whatever the promote decider raises."""
    run = _completed_run()
    registered = register_dataset.decide(
        state=None,
        command=RegisterDataset(
            name="recon",
            uri="s3://b/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            producing_run_id=run.id,
            actuation_kind=actuation_kind,
        ),
        context=DatasetRegistrationContext(producing_run=run),
        now=_NOW,
        new_id=uuid4(),
        registered_by=_ACTOR,
    )
    # The orchestrator-supplied kind is snapshotted onto the event verbatim.
    assert registered[0].producing_actuation_kind == actuation_kind
    dataset = fold(registered)
    assert dataset is not None
    return promote_dataset.decide(
        state=dataset,
        command=PromoteDataset(dataset_id=dataset.id, reason="passed peer review"),
        context=DatasetPromotionContext(derived_from={}),
        now=_NOW,
        promoted_by=_ACTOR,
    )


@pytest.mark.unit
def test_simulated_origin_dataset_is_non_promotable_end_to_end() -> None:
    """A conduct that observed Simulated actuation yields a Dataset that
    register -> fold -> promote refuses to promote, using the exact value
    the Operation BC emits."""
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        _register_then_promote(ActuationKind.SIMULATED.value)
    assert "Simulated" in exc_info.value.reason


@pytest.mark.unit
def test_hybrid_origin_dataset_is_non_promotable_end_to_end() -> None:
    """Hybrid (some real, some simulated) is disqualifying too."""
    with pytest.raises(DatasetCannotPromoteError):
        _register_then_promote(ActuationKind.HYBRID.value)


@pytest.mark.unit
def test_physical_origin_dataset_promotes_end_to_end() -> None:
    """Real-hardware data flows all the way through to a DatasetPromoted."""
    events = _register_then_promote(ActuationKind.PHYSICAL.value)
    assert len(events) == 1
    assert isinstance(events[0], DatasetPromoted)
