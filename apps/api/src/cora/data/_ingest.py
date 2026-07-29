"""The ingest composition core: three sibling deciders, one plan.

This module exists for the same reason `cora.operation.conductor` does:
slices are independent units and MUST NOT import each other
(tests/architecture/test_cross_slice_independence.py), so the one place
that composes several slices' deciders lives at the BC root, and the
`ingest_scan` slice handler delegates here. Everything that touches a
sibling slice's modules is confined to this file.

`decide_ingest` is pure: resolved inputs in, three stream plans out.
The distribution and acquisition deciders receive the in-flight Dataset
folded from the just-decided genesis events, not a store load; the
Dataset exists nowhere else yet. Any decider rejection propagates
before anything is appended, which is what lets the handler promise
zero events on every failure path.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.data.aggregates.acquisition import event_type_name as acquisition_event_type_name
from cora.data.aggregates.acquisition import to_payload as acquisition_to_payload
from cora.data.aggregates.dataset import event_type_name as dataset_event_type_name
from cora.data.aggregates.dataset import to_payload as dataset_to_payload
from cora.data.aggregates.dataset.evolver import fold as fold_dataset
from cora.data.aggregates.distribution import event_type_name as distribution_event_type_name
from cora.data.aggregates.distribution import to_payload as distribution_to_payload
from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.context import AcquisitionRecordingContext
from cora.data.features.record_acquisition.decider import decide as decide_acquisition
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.context import DatasetRegistrationContext
from cora.data.features.register_dataset.decider import decide as decide_dataset
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.context import DistributionRegistrationContext
from cora.data.features.register_distribution.decider import decide as decide_distribution
from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.shared.identity import ActorId


@dataclass(frozen=True)
class StreamPlan:
    """One genesis stream the ingest will append: the stream identity
    plus (event_type, payload, occurred_at) triples ready for
    enveloping. Domain event classes stay behind this boundary."""

    stream_type: str
    stream_id: UUID
    events: tuple[tuple[str, dict[str, Any], datetime], ...]


def decide_ingest(
    *,
    name: str,
    locator: str,
    checksum_algorithm: str,
    checksum_value: str,
    byte_size: int,
    media_type: str,
    conforms_to: frozenset[str],
    access_protocol: str,
    producing_run_id: UUID | None,
    run: Any | None,
    asset: AssetLookupResult,
    supply: SupplyLookupResult,
    supply_id: UUID,
    captured_at: datetime,
    evidence: dict[str, Any],
    now: datetime,
    dataset_id: UUID,
    distribution_id: UUID,
    acquisition_id: UUID,
    actor: ActorId,
) -> tuple[StreamPlan, StreamPlan, StreamPlan]:
    """Run the three deciders in memory and return their stream plans.

    Raises whatever the deciders raise; the caller appends nothing
    unless all three succeeded.
    """
    dataset_events = decide_dataset(
        state=None,
        command=RegisterDataset(
            name=name,
            uri=locator,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            producing_run_id=producing_run_id,
        ),
        context=DatasetRegistrationContext(
            producing_run=run,
            producing_procedure=None,
            subject=None,
            derived_from={},
        ),
        now=now,
        new_id=dataset_id,
        registered_by=actor,
    )
    dataset_state = fold_dataset(dataset_events)
    if dataset_state is None:
        raise AssertionError("register_dataset decider emitted no genesis event")

    distribution_events = decide_distribution(
        state=None,
        command=RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=locator,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            access_protocol=access_protocol,
            conforms_to=conforms_to,
        ),
        context=DistributionRegistrationContext(dataset=dataset_state, supply=supply),
        now=now,
        new_id=distribution_id,
        registered_by=actor,
    )

    acquisition_events = decide_acquisition(
        state=None,
        command=RecordAcquisition(
            dataset_id=dataset_id,
            producing_asset_id=asset.id,
            captured_at=captured_at,
            producing_run_id=producing_run_id,
            settings={},
            evidence=evidence,
        ),
        context=AcquisitionRecordingContext(dataset=dataset_state, asset=asset, run=run),
        now=now,
        new_id=acquisition_id,
        recorded_by=actor,
    )

    return (
        StreamPlan(
            stream_type="Dataset",
            stream_id=dataset_id,
            events=tuple(
                (dataset_event_type_name(e), dataset_to_payload(e), e.occurred_at)
                for e in dataset_events
            ),
        ),
        StreamPlan(
            stream_type="Distribution",
            stream_id=distribution_id,
            events=tuple(
                (distribution_event_type_name(e), distribution_to_payload(e), e.occurred_at)
                for e in distribution_events
            ),
        ),
        StreamPlan(
            stream_type="Acquisition",
            stream_id=acquisition_id,
            events=tuple(
                (acquisition_event_type_name(e), acquisition_to_payload(e), e.occurred_at)
                for e in acquisition_events
            ),
        ),
    )


__all__ = ["StreamPlan", "decide_ingest"]
