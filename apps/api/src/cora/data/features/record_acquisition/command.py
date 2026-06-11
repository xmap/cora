"""The `RecordAcquisition` command for this slice.

Carries everything the caller controls: the three cross-aggregate
bindings (dataset_id, producing_asset_id, the optional
producing_run_id), the instrument wall-clock `captured_at`, and the
two carrier dicts (settings, evidence). The new Acquisition id is
server-allocated by the handler from the IdGenerator port (matches
every other create-style slice in the codebase); the request body
does NOT carry it.

`occurred_at` (the CORA-side recording time) is stamped by the
handler via the Clock port, not supplied by the caller.

"Record" rather than "register" or "define": an Acquisition is a
fact-chain entry, not an instance template. The same verb serves
operator-initiated and future capture-port-driven recordings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RecordAcquisition:
    """Record a new capture fact with the given metadata."""

    dataset_id: UUID
    producing_asset_id: UUID
    captured_at: datetime
    producing_run_id: UUID | None = None
    settings: dict[str, Any] = field(default_factory=dict[str, Any])
    evidence: dict[str, Any] = field(default_factory=dict[str, Any])
