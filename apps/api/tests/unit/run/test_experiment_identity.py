"""Unit tests for the `run_experiment_identity` vault's InMemory adapter
and the `load_run_experiment_identity` helper (slice 14a).

Mirrors `test_capture_path.py`'s shape: exercise the store contract
directly, no reader or recorder involved.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InMemoryExperimentIdentityStore,
    load_run_experiment_identity,
)

_T0 = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


@pytest.mark.unit
async def test_upsert_then_get_roundtrips_all_three_fields() -> None:
    store = InMemoryExperimentIdentityStore()
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_at(0),
        esaf_number="67890",
        esaf_number_observed_at=_at(1),
        esaf_doi_number="10.1234/esaf.67890",
        esaf_doi_number_observed_at=_at(2),
        created_at=_at(3),
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.run_id == run_id
    assert row.proposal_number == "12345"
    assert row.proposal_number_observed_at == _at(0)
    assert row.esaf_number == "67890"
    assert row.esaf_number_observed_at == _at(1)
    assert row.esaf_doi_number == "10.1234/esaf.67890"
    assert row.esaf_doi_number_observed_at == _at(2)
    assert row.created_at == _at(3)
    assert row.updated_at == _at(3)


@pytest.mark.unit
async def test_upsert_accepts_a_partial_reading() -> None:
    """Only ProposalNumber was populated at genesis; ESAFNumber /
    ESAFDOINumber still read the substrate's own "Unknown" placeholder
    (already resolved to None upstream, before this store ever sees
    it). Each pair is independently nullable for exactly this reason."""
    store = InMemoryExperimentIdentityStore()
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_at(0),
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_at(0),
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.proposal_number == "12345"
    assert row.esaf_number is None
    assert row.esaf_number_observed_at is None
    assert row.esaf_doi_number is None
    assert row.esaf_doi_number_observed_at is None


@pytest.mark.unit
async def test_get_absent_run_id_returns_none() -> None:
    store = InMemoryExperimentIdentityStore()
    assert await store.get(uuid4()) is None


@pytest.mark.unit
async def test_upsert_overwrites_and_preserves_created_at() -> None:
    """A second upsert for the same run_id (a retry) overwrites every
    value column but keeps the ORIGINAL created_at, mirroring the
    Postgres adapter's `ON CONFLICT DO UPDATE` (which never touches the
    column). `updated_at` on the UPDATE branch is the STORE's own clock,
    mirroring `InMemoryCapturePathStore`'s identical convention."""
    store = InMemoryExperimentIdentityStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        proposal_number="111",
        proposal_number_observed_at=_at(0),
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_at(0),
    )
    before_second_upsert = datetime.now(tz=UTC)

    await store.upsert(
        run_id=run_id,
        proposal_number="222",
        proposal_number_observed_at=_at(5),
        esaf_number="333",
        esaf_number_observed_at=_at(5),
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_at(5),
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.proposal_number == "222"
    assert row.esaf_number == "333"
    assert row.created_at == _at(0)
    assert row.updated_at >= before_second_upsert


@pytest.mark.unit
async def test_load_run_experiment_identity_returns_the_row_when_present() -> None:
    store = InMemoryExperimentIdentityStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_at(0),
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_at(0),
    )

    identity = await load_run_experiment_identity(store, run_id)
    assert identity is not None
    assert identity.proposal_number == "12345"


@pytest.mark.unit
async def test_load_run_experiment_identity_returns_none_when_absent() -> None:
    """Unlike `load_run_capture_path`, no tombstone placeholder: none of
    these three values is personal data, so a plain `None` is the
    honest "nothing recorded" signal."""
    store = InMemoryExperimentIdentityStore()
    assert await load_run_experiment_identity(store, uuid4()) is None
