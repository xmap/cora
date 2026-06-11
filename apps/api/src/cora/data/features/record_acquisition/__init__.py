"""Vertical slice for the `RecordAcquisition` command.

Module-as-namespace surface:

    from cora.data.features import record_acquisition

    cmd = record_acquisition.RecordAcquisition(
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        captured_at=datetime.now(UTC),
        producing_run_id=run_id,
        settings={"exposure_ms": 200},
        evidence={},
    )
    handler = record_acquisition.bind(deps)
    acquisition_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.record_acquisition import tool
from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.context import AcquisitionRecordingContext
from cora.data.features.record_acquisition.decider import decide
from cora.data.features.record_acquisition.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.record_acquisition.route import router

__all__ = [
    "AcquisitionRecordingContext",
    "Handler",
    "IdempotentHandler",
    "RecordAcquisition",
    "bind",
    "decide",
    "router",
    "tool",
]
