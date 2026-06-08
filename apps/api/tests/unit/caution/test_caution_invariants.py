"""Pure-predicate tests for `cora.caution.aggregates.caution.invariants`.

The deciders that already call these predicates have their own
end-to-end coverage; this module just pins each predicate's contract
in isolation so future callers (cross-BC writers in particular) can
rely on a stable shape.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionCannotSupersedeError,
    CautionCategory,
    CautionSeverity,
    CautionStatus,
    CautionText,
    CautionWorkaround,
    InvalidCautionExpiresAtError,
    InvalidCautionSupersedeTargetError,
    ProcedureTarget,
    ensure_expires_at_future,
    ensure_supersedable,
    ensure_target_preserved,
)
from cora.shared.identity import ActorId


def _active_caution(target: AssetTarget | ProcedureTarget | None = None) -> Caution:
    return Caution(
        id=uuid4(),
        target=target or AssetTarget(asset_id=uuid4()),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.NOTICE,
        text=CautionText("x"),
        workaround=CautionWorkaround("y"),
        authored_by=ActorId(uuid4()),
    )


# ---------- ensure_supersedable ----------


@pytest.mark.unit
def test_ensure_supersedable_passes_for_active() -> None:
    parent = _active_caution()
    ensure_supersedable(parent)


@pytest.mark.unit
@pytest.mark.parametrize("status", [CautionStatus.SUPERSEDED, CautionStatus.RETIRED])
def test_ensure_supersedable_raises_for_terminal(status: CautionStatus) -> None:
    parent = replace(_active_caution(), status=status)
    with pytest.raises(CautionCannotSupersedeError) as exc:
        ensure_supersedable(parent)
    assert exc.value.current_status is status


# ---------- ensure_target_preserved ----------


@pytest.mark.unit
def test_ensure_target_preserved_passes_when_identical() -> None:
    target = AssetTarget(asset_id=uuid4())
    ensure_target_preserved(target, target)


@pytest.mark.unit
def test_ensure_target_preserved_raises_when_id_differs() -> None:
    a = AssetTarget(asset_id=uuid4())
    b = AssetTarget(asset_id=uuid4())
    with pytest.raises(InvalidCautionSupersedeTargetError):
        ensure_target_preserved(a, b)


@pytest.mark.unit
def test_ensure_target_preserved_raises_when_kind_differs() -> None:
    asset = AssetTarget(asset_id=uuid4())
    procedure = ProcedureTarget(procedure_id=uuid4())
    with pytest.raises(InvalidCautionSupersedeTargetError):
        ensure_target_preserved(asset, procedure)


# ---------- ensure_expires_at_future ----------


@pytest.mark.unit
def test_ensure_expires_at_future_passes_when_none() -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    ensure_expires_at_future(None, now)


@pytest.mark.unit
def test_ensure_expires_at_future_passes_when_strictly_future() -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    ensure_expires_at_future(now + timedelta(seconds=1), now)


@pytest.mark.unit
def test_ensure_expires_at_future_raises_when_equal_to_now() -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    with pytest.raises(InvalidCautionExpiresAtError):
        ensure_expires_at_future(now, now)


@pytest.mark.unit
def test_ensure_expires_at_future_raises_when_past() -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    with pytest.raises(InvalidCautionExpiresAtError):
        ensure_expires_at_future(now - timedelta(seconds=1), now)
