"""Unit tests for the `withdraw_edition` pure decider.

Covers the decider-tier firing order via direct decider calls: the
WithdrawalReason VO validation (empty / whitespace / too-long), the
status guard (EditionCannotWithdrawError on non-Published sources),
and the happy-path EditionWithdrawn carrying the trimmed reason.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotWithdrawError,
    EditionKind,
    EditionStatus,
    EditionTitle,
    EditionWithdrawn,
    InvalidEditionWithdrawalReasonError,
)
from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.context import WithdrawEditionContext
from cora.data.features.withdraw_edition.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000ed01")
_DATASET_A = UUID("01900000-0000-7000-8000-00000000da01")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac70"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac71"))
_MINTED_PID = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.DOI,
    value="10.0000/cora-stub/ed01",
)


def _edition(*, status: EditionStatus = EditionStatus.PUBLISHED) -> Edition:
    return Edition(
        id=_EDITION_ID,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("Pilot"),
        dataset_ids=frozenset({_DATASET_A}),
        creators=(Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        registered_at=_NOW,
        registered_by=_PRINCIPAL_ID,
        status=status,
        publisher_facility_code=FacilityCode("cora"),
        publication_year=2026,
        content_hash="deadbeef" * 8,
        external_pid=_MINTED_PID,
        sealed_at=_NOW,
        sealed_by=_PRINCIPAL_ID,
        published_at=_NOW,
        published_by=_PRINCIPAL_ID,
    )


def _decide(*, state: Edition, reason: str) -> list[EditionWithdrawn]:
    return decide(
        state=state,
        command=WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason=reason),
        context=WithdrawEditionContext(),
        now=_NOW,
        withdrawn_by=_PRINCIPAL_ID,
    )


@pytest.mark.unit
def test_decider_emits_edition_withdrawn_on_happy_path() -> None:
    events = _decide(state=_edition(), reason="superseded by v2")
    assert len(events) == 1
    withdrawn = events[0]
    assert isinstance(withdrawn, EditionWithdrawn)
    assert withdrawn.edition_id == _EDITION_ID
    assert withdrawn.withdrawal_reason == "superseded by v2"
    assert withdrawn.occurred_at == _NOW
    assert withdrawn.withdrawn_by == _PRINCIPAL_ID


@pytest.mark.unit
def test_decider_trims_withdrawal_reason() -> None:
    events = _decide(state=_edition(), reason="  retracted for error  ")
    assert events[0].withdrawal_reason == "retracted for error"


@pytest.mark.unit
def test_decider_rejects_registered_source_status() -> None:
    with pytest.raises(EditionCannotWithdrawError) as exc:
        _decide(state=_edition(status=EditionStatus.REGISTERED), reason="x")
    assert exc.value.current_status is EditionStatus.REGISTERED


@pytest.mark.unit
def test_decider_rejects_sealed_source_status() -> None:
    with pytest.raises(EditionCannotWithdrawError) as exc:
        _decide(state=_edition(status=EditionStatus.SEALED), reason="x")
    assert exc.value.current_status is EditionStatus.SEALED


@pytest.mark.unit
def test_decider_rejects_withdrawn_source_status() -> None:
    with pytest.raises(EditionCannotWithdrawError) as exc:
        _decide(state=_edition(status=EditionStatus.WITHDRAWN), reason="x")
    assert exc.value.current_status is EditionStatus.WITHDRAWN


@pytest.mark.unit
def test_decider_rejects_empty_reason() -> None:
    with pytest.raises(InvalidEditionWithdrawalReasonError):
        _decide(state=_edition(), reason="")


@pytest.mark.unit
def test_decider_rejects_whitespace_only_reason() -> None:
    with pytest.raises(InvalidEditionWithdrawalReasonError):
        _decide(state=_edition(), reason="   ")


@pytest.mark.unit
def test_decider_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidEditionWithdrawalReasonError):
        _decide(state=_edition(), reason="x" * (REASON_MAX_LENGTH + 1))
