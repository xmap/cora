"""Unit tests for Edition aggregate state, VOs, enums, and error classes."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cora.data.aggregates.edition.state import (
    EDITION_AFFILIATION_MAX_LENGTH,
    EDITION_LICENSE_MAX_LENGTH,
    EDITION_PUBLICATION_YEAR_FUTURE_BUDGET,
    EDITION_PUBLICATION_YEAR_MIN,
    EDITION_TITLE_MAX_LENGTH,
    LICENSE_REQUIRED_KINDS,
    Creator,
    EditionKind,
    EditionStatus,
    EditionTitle,
    InvalidCreatorsError,
    InvalidEditionTitleError,
    InvalidEditionWithdrawalReasonError,
    InvalidPublicationYearError,
    InvalidSpdxIdentifierError,
    SpdxIdentifier,
    WithdrawalReason,
    validate_creators,
    validate_publication_year,
)
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH


def test_edition_kind_has_six_values() -> None:
    assert {k.value for k in EditionKind} == {
        "ROCrate",
        "DataCite",
        "Croissant",
        "OAIS_AIP",
        "OAIS_DIP",
        "NeXus",
    }


def test_edition_status_has_four_values() -> None:
    assert {s.value for s in EditionStatus} == {
        "Registered",
        "Sealed",
        "Published",
        "Withdrawn",
    }


def test_license_required_kinds_covers_datacite_and_croissant() -> None:
    assert frozenset({EditionKind.DATACITE, EditionKind.CROISSANT}) == LICENSE_REQUIRED_KINDS


def test_edition_title_trims_and_accepts_bounded() -> None:
    title = EditionTitle("  My Edition  ")
    assert title.value == "My Edition"


def test_edition_title_rejects_empty() -> None:
    with pytest.raises(InvalidEditionTitleError):
        EditionTitle("   ")


def test_edition_title_rejects_oversize() -> None:
    with pytest.raises(InvalidEditionTitleError):
        EditionTitle("x" * (EDITION_TITLE_MAX_LENGTH + 1))


def test_spdx_identifier_accepts_canonical_id() -> None:
    sid = SpdxIdentifier("CC-BY-4.0")
    assert sid.value == "CC-BY-4.0"


def test_spdx_identifier_accepts_plus_dot() -> None:
    SpdxIdentifier("Apache-2.0")
    SpdxIdentifier("GPL-3.0+")


def test_spdx_identifier_rejects_whitespace() -> None:
    with pytest.raises(InvalidSpdxIdentifierError):
        SpdxIdentifier("CC BY 4.0")


def test_spdx_identifier_rejects_empty() -> None:
    with pytest.raises(InvalidSpdxIdentifierError):
        SpdxIdentifier("   ")


def test_spdx_identifier_rejects_oversize() -> None:
    with pytest.raises(InvalidSpdxIdentifierError):
        SpdxIdentifier("x" * (EDITION_LICENSE_MAX_LENGTH + 1))


def test_withdrawal_reason_trims_and_accepts_bounded() -> None:
    reason = WithdrawalReason("  audit-found duplicate  ")
    assert reason.value == "audit-found duplicate"


def test_withdrawal_reason_rejects_empty() -> None:
    with pytest.raises(InvalidEditionWithdrawalReasonError):
        WithdrawalReason("")


def test_withdrawal_reason_rejects_oversize() -> None:
    with pytest.raises(InvalidEditionWithdrawalReasonError):
        WithdrawalReason("x" * (REASON_MAX_LENGTH + 1))


def test_creator_accepts_no_affiliation() -> None:
    actor = ActorId(uuid4())
    creator = Creator(actor_id=actor, affiliation=None)
    assert creator.actor_id == actor
    assert creator.affiliation is None


def test_creator_trims_affiliation() -> None:
    creator = Creator(actor_id=ActorId(uuid4()), affiliation="  ANL  ")
    assert creator.affiliation == "ANL"


def test_creator_rejects_empty_affiliation() -> None:
    with pytest.raises(InvalidCreatorsError):
        Creator(actor_id=ActorId(uuid4()), affiliation="   ")


def test_creator_rejects_oversize_affiliation() -> None:
    with pytest.raises(InvalidCreatorsError):
        Creator(
            actor_id=ActorId(uuid4()),
            affiliation="x" * (EDITION_AFFILIATION_MAX_LENGTH + 1),
        )


def test_validate_creators_rejects_empty() -> None:
    with pytest.raises(InvalidCreatorsError):
        validate_creators(())


def test_validate_creators_rejects_duplicate_actor_ids() -> None:
    actor = ActorId(uuid4())
    with pytest.raises(InvalidCreatorsError):
        validate_creators((Creator(actor_id=actor), Creator(actor_id=actor)))


def test_validate_creators_accepts_unique_set() -> None:
    creators = (
        Creator(actor_id=ActorId(uuid4()), affiliation="ANL"),
        Creator(actor_id=ActorId(uuid4()), affiliation=None),
    )
    assert validate_creators(creators) == creators


def test_validate_publication_year_accepts_within_window() -> None:
    assert validate_publication_year(2024, current_year=2026) == 2024


def test_validate_publication_year_rejects_too_old() -> None:
    with pytest.raises(InvalidPublicationYearError):
        validate_publication_year(EDITION_PUBLICATION_YEAR_MIN - 1, current_year=2026)


def test_validate_publication_year_rejects_too_new() -> None:
    with pytest.raises(InvalidPublicationYearError):
        validate_publication_year(
            2026 + EDITION_PUBLICATION_YEAR_FUTURE_BUDGET + 1,
            current_year=2026,
        )
