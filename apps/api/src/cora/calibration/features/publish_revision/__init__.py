"""publish_revision slice: publish a Calibration revision to a peer.

Cross-BC publish slice that emits an atomic event pair (
CalibrationRevisionPublished on the Calibration stream +
PublicationReceiptRecorded on the matching outbound Permit stream)
via EventStore.append_streams. The handler canonicalizes the
artifact, calls SignaturePort.sign, calls PublishPort.publish, then
appends both events atomically.
"""

from cora.calibration.features.publish_revision import tool
from cora.calibration.features.publish_revision.command import (
    PublishCalibrationRevision,
)
from cora.calibration.features.publish_revision.decider import (
    PublishRevisionEvents,
    decide,
)
from cora.calibration.features.publish_revision.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.calibration.features.publish_revision.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "PublishCalibrationRevision",
    "PublishRevisionEvents",
    "bind",
    "decide",
    "router",
    "tool",
]
