"""Property-based tests for `withdraw_edition.decide`.

Universal claims across generated inputs:

  - any Published Edition + any valid reason (1-500 chars after trim)
    produces a single EditionWithdrawn whose withdrawal_reason equals
    the trimmed reason (the WithdrawalReason VO trims).
  - state.status != PUBLISHED with a valid reason always raises
    EditionCannotWithdrawError.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionCannotWithdrawError,
    EditionKind,
    EditionStatus,
    EditionTitle,
    EditionWithdrawn,
)
from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.context import WithdrawEditionContext
from cora.data.features.withdraw_edition.decider import decide
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

if TYPE_CHECKING:
    from uuid import UUID

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_NON_PUBLISHED_STATUS = st.sampled_from(
    [s for s in EditionStatus if s is not EditionStatus.PUBLISHED]
)
# Reason text may carry leading / trailing whitespace; the VO trims it.
# The non-whitespace core stays 1-500 chars so the trimmed value is
# always valid.
_VALID_REASON = st.text(min_size=1, max_size=REASON_MAX_LENGTH)


def _edition(
    edition_id: UUID,
    *,
    status: EditionStatus = EditionStatus.PUBLISHED,
) -> Edition:
    return Edition(
        id=edition_id,
        kind=EditionKind.ROCRATE,
        title=EditionTitle("E"),
        dataset_ids=frozenset({edition_id}),
        creators=(Creator(actor_id=ActorId(edition_id)),),
        registered_at=_NOW,
        registered_by=ActorId(edition_id),
        status=status,
        publisher_facility_code=FacilityCode("cora"),
        publication_year=2026,
        content_hash="f" * 64,
        external_pid=PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value="10.0/x"),
        sealed_at=_NOW,
        sealed_by=ActorId(edition_id),
        published_at=_NOW,
        published_by=ActorId(edition_id),
    )


@pytest.mark.unit
@given(edition_id=st.uuids(), reason=_VALID_REASON)
def test_decider_happy_path_emits_one_edition_withdrawn_with_trimmed_reason(
    edition_id: UUID,
    reason: str,
) -> None:
    # The VO trims and then requires 1-500 chars; skip inputs whose
    # trimmed form is empty.
    assume(reason.strip())
    events = decide(
        state=_edition(edition_id),
        command=WithdrawEdition(edition_id=edition_id, withdrawal_reason=reason),
        context=WithdrawEditionContext(),
        now=_NOW,
        withdrawn_by=ActorId(edition_id),
    )
    assert len(events) == 1
    withdrawn = events[0]
    assert isinstance(withdrawn, EditionWithdrawn)
    assert withdrawn.edition_id == edition_id
    assert withdrawn.withdrawal_reason == reason.strip()


@pytest.mark.unit
@given(edition_id=st.uuids(), status=_NON_PUBLISHED_STATUS)
def test_decider_rejects_non_published_status_for_any_input(
    edition_id: UUID,
    status: EditionStatus,
) -> None:
    with pytest.raises(EditionCannotWithdrawError):
        decide(
            state=_edition(edition_id, status=status),
            command=WithdrawEdition(edition_id=edition_id, withdrawal_reason="valid reason"),
            context=WithdrawEditionContext(),
            now=_NOW,
            withdrawn_by=ActorId(edition_id),
        )
