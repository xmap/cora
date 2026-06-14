"""Property-based tests for `promote_dataset.decide` (Data BC).

Complements the example-based `test_promote_dataset_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider validating loaded peer-Dataset lineage from a context:

    (state, command, context, now, promoted_by) -> list[DatasetPromoted]

Load-bearing properties:

  - A None state always raises `DatasetNotFoundError` regardless of the
    command (existence / genesis guard fires first).
  - A Discarded Dataset always raises `DatasetCannotPromoteError`
    regardless of its intent (status guard before intent guard).
  - A Registered Dataset whose intent is not Trial (Production or
    Retracted) always raises `DatasetAlreadyPromotedError` carrying the
    current intent (strict-not-idempotent).
  - A clean promotable Dataset (Registered + Trial + no producing Run +
    empty lineage) emits exactly one `DatasetPromoted` keyed on
    state.id with occurred_at=now and the threaded promoted_by.
  - Pure: same inputs return equal results (no clock leakage).

The full fail-fast gate matrix (Run-end-state, lineage, reason length)
is pinned by the example test; this file asserts only the universal
partitions that hold across the whole input space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetAlreadyPromotedError,
    DatasetCannotPromoteError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetPromoted,
    DatasetStatus,
    DatasetUri,
    Intent,
)
from cora.data.features import promote_dataset
from cora.data.features.promote_dataset import DatasetPromotionContext, PromoteDataset
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH

_ALREADY_PROMOTED_INTENTS = (Intent.PRODUCTION, Intent.RETRACTED)
_ANY_INTENT = (Intent.TRIAL, Intent.PRODUCTION, Intent.RETRACTED)
# Simulator-tainted kinds the one-way gate must always block.
_SIMULATOR_TAINTED = ("Simulated", "Hybrid")
# Kinds that leave the gate inactive (None = nothing recorded) or pass it
# (Physical = real hardware); both promote when otherwise clean.
_PROMOTABLE_KINDS = (None, "Physical")


def _reasons() -> st.SearchStrategy[str]:
    return printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)


def _dataset(
    *,
    dataset_id: UUID,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    intent: Intent = Intent.TRIAL,
    producing_run_id: UUID | None = None,
    producing_procedure_id: UUID | None = None,
    producing_run_end_state: str | None = None,
    producing_actuation_kind: str | None = None,
    derived_from: frozenset[UUID] = frozenset(),
) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        producing_run_id=producing_run_id,
        producing_procedure_id=producing_procedure_id,
        derived_from=derived_from,
        status=status,
        producing_run_end_state=producing_run_end_state,
        producing_actuation_kind=producing_actuation_kind,
        intent=intent,
    )


def _context() -> DatasetPromotionContext:
    return DatasetPromotionContext(derived_from={})


def _command(*, dataset_id: UUID, reason: str) -> PromoteDataset:
    return PromoteDataset(dataset_id=dataset_id, reason=reason)


@pytest.mark.unit
@given(dataset_id=st.uuids(), reason=_reasons(), now=aware_datetimes(), actor=st.uuids())
def test_decide_none_state_always_raises_not_found(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A None state raises DatasetNotFoundError before any other guard."""
    with pytest.raises(DatasetNotFoundError):
        promote_dataset.decide(
            state=None,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    intent=st.sampled_from(_ANY_INTENT),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_discarded_always_raises_cannot_promote(
    dataset_id: UUID,
    intent: Intent,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Discarded Dataset rejects promotion for any intent (status guard wins)."""
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.DISCARDED, intent=intent)
    with pytest.raises(DatasetCannotPromoteError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert "discarded" in exc.value.reason.lower()


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    intent=st.sampled_from(_ALREADY_PROMOTED_INTENTS),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_non_trial_intent_always_raises_already_promoted(
    dataset_id: UUID,
    intent: Intent,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Registered Dataset whose intent is not Trial raises with the current intent."""
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED, intent=intent)
    with pytest.raises(DatasetAlreadyPromotedError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert exc.value.current_intent is intent


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    kind=st.sampled_from(_PROMOTABLE_KINDS),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_clean_promotable_emits_one_promoted_event(
    dataset_id: UUID,
    kind: str | None,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Registered + Trial Dataset with no Run and empty lineage emits one
    DatasetPromoted, for a Physical or unrecorded (None) actuation kind."""
    promoted_by = ActorId(actor)
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.TRIAL,
        producing_run_id=None,
        producing_actuation_kind=kind,
        derived_from=frozenset(),
    )
    events = promote_dataset.decide(
        state=state,
        command=_command(dataset_id=dataset_id, reason=reason),
        context=_context(),
        now=now,
        promoted_by=promoted_by,
    )
    assert events == [
        DatasetPromoted(
            dataset_id=state.id,
            reason=reason,
            occurred_at=now,
            promoted_by=promoted_by,
        )
    ]


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    kind=st.sampled_from(_SIMULATOR_TAINTED),
    has_run=st.booleans(),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_simulator_origin_always_rejects(
    dataset_id: UUID,
    kind: str,
    has_run: bool,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """The one-way gate: a Simulated / Hybrid producing_actuation_kind never
    promotes, even when every other promotion precondition is satisfied.

    This is the single most load-bearing claim of the slice: rehearsal /
    simulator-origin data is structurally non-promotable to Production.
    intent is pinned to Trial so the actuation guard (guard 6), not the
    earlier intent guard, is necessarily the one that rejects; the
    assertion checks the exact error and that the kind names itself in the
    reason, so a regression dropping guard 6 fails here rather than being
    absorbed by an earlier guard. has_run varies to show the gate holds
    both with a Completed producing Run and with none.
    """
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.TRIAL,
        producing_run_id=actor if has_run else None,
        producing_run_end_state="Completed" if has_run else None,
        producing_actuation_kind=kind,
        derived_from=frozenset(),
    )
    with pytest.raises(DatasetCannotPromoteError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert kind in exc.value.reason


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    procedure_id=st.uuids(),
    has_run=st.booleans(),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_unprovable_procedure_provenance_always_rejects(
    dataset_id: UUID,
    procedure_id: UUID,
    has_run: bool,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """The item-6 leak-closer: a Dataset that NAMES a producing Procedure whose
    actuation kind is None has unproven provenance and never promotes, even when
    every other precondition is satisfied. Pairs with the simulator-origin
    property: between them, only Physical (or a no-procedure None) promotes.
    intent pinned to Trial so guard 7, not an earlier guard, does the rejecting.
    """
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.TRIAL,
        producing_run_id=actor if has_run else None,
        producing_run_end_state="Completed" if has_run else None,
        producing_procedure_id=procedure_id,
        producing_actuation_kind=None,
        derived_from=frozenset(),
    )
    with pytest.raises(DatasetCannotPromoteError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert str(procedure_id) in exc.value.reason


@pytest.mark.unit
@given(dataset_id=st.uuids(), reason=_reasons(), now=aware_datetimes(), actor=st.uuids())
def test_decide_is_pure_same_input_same_output(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    promoted_by = ActorId(actor)
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED, intent=Intent.TRIAL)
    command = _command(dataset_id=dataset_id, reason=reason)
    first = promote_dataset.decide(
        state=state, command=command, context=_context(), now=now, promoted_by=promoted_by
    )
    second = promote_dataset.decide(
        state=state, command=command, context=_context(), now=now, promoted_by=promoted_by
    )
    assert first == second
