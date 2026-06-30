"""Evolver: replay events to reconstruct Distribution state.

Mirror of the Dataset evolver and other aggregate evolvers. The
terminal ``assert_never`` case forces pyright (and the runtime) to
error if a new event type is added to ``DistributionEvent`` without
a matching match arm here.

Status mapping per event type (current):
  - ``DistributionRegistered`` -> ``REGISTERED`` (genesis)
  - ``DistributionDiscarded``  -> ``DISCARDED``  (terminal transition)

Future-slice mappings (NAMED only):
  - ``DistributionVerified`` -> ``VERIFIED``
  - ``DistributionMarkedStale`` -> ``STALE``

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as Dataset.

**Critical invariant** for transition arms: every transition arm
MUST carry every Distribution field through from prior state.
Constructing ``Distribution(id=..., dataset_id=..., ...)`` without
explicitly passing the 9 core + 7 nullable attribution fields would
silently WIPE them to defaults. The ``DistributionDiscarded`` arm uses
``dataclasses.replace`` over the prior state so all 17 fields carry
forward and only the four discard-related fields change. Use
``require_state`` per the Dataset pattern to guard against a transition
event applied to an empty stream (a malformed stream).
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
)
from cora.data.aggregates.distribution.events import (
    DistributionDiscarded,
    DistributionEvent,
    DistributionRegistered,
)
from cora.data.aggregates.distribution.state import (
    AccessProtocol,
    Distribution,
    DistributionStatus,
    DistributionUri,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Distribution | None, event: DistributionEvent) -> Distribution:
    """Apply one event to the current Distribution state."""
    match event:
        case DistributionRegistered(
            distribution_id=distribution_id,
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            access_protocol=access_protocol,
            occurred_at=occurred_at,
            registered_by=registered_by,
        ):
            _ = state  # DistributionRegistered is the genesis event; prior state ignored.
            return Distribution(
                id=distribution_id,
                dataset_id=dataset_id,
                supply_id=supply_id,
                uri=DistributionUri(uri),
                checksum=DatasetChecksum(algorithm=checksum_algorithm, value=checksum_value),
                byte_size=byte_size,
                encoding=DatasetEncoding(media_type=media_type, conforms_to=conforms_to),
                access_protocol=AccessProtocol(access_protocol),
                registered_at=occurred_at,
                registered_by=registered_by,
                status=DistributionStatus.REGISTERED,
                # Nullable transition attribution fields default to None;
                # future-slice arms populate them. Explicit defaults here for
                # documentation clarity.
                verified_at=None,
                verified_by=None,
                marked_stale_at=None,
                marked_stale_by=None,
                discarded_at=None,
                discarded_by=None,
                discard_reason=None,
            )
        case DistributionDiscarded(
            reason=reason,
            occurred_at=occurred_at,
            discarded_by=discarded_by,
        ):
            prior = require_state(state, "DistributionDiscarded")
            return replace(
                prior,
                status=DistributionStatus.DISCARDED,
                discarded_at=occurred_at,
                discarded_by=discarded_by,
                discard_reason=reason,
            )
        case _:  # pragma: no cover  # exhaustiveness guard for future arms
            assert_never(event)


def fold(events: Sequence[DistributionEvent]) -> Distribution | None:
    """Replay a stream of events from the empty initial state."""
    state: Distribution | None = None
    for event in events:
        state = evolve(state, event)
    return state
