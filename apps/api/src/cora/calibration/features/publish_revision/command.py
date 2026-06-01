"""The `PublishCalibrationRevision` command: intent for the publish slice.

Caller-controlled inputs for publishing a named revision of an
existing Calibration to a peer facility under an Active outbound
Permit:

  - `calibration_id`: target Calibration aggregate.
  - `revision_id`: the revision on this Calibration to publish; the
    decider raises `CalibrationRevisionNotFoundError` on miss and
    `CalibrationRevisionMissingContentHashError` on legacy revisions
    without a kernel-fused content_hash.
  - `peer_facility_id`: opaque string id of the peer the publish is
    intended for; resolved at the handler tier via PermitLookup to
    locate the matching outbound Permit.

Server-side concerns (signature envelope, receipt id, published_at
timestamp, published_by_actor_id) are injected by the handler from
infrastructure ports + the request envelope; the decider takes them
as separate parameters so the command DTO stays narrow.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PublishCalibrationRevision:
    """Publish an existing revision of a Calibration to a peer facility."""

    calibration_id: UUID
    revision_id: UUID
    peer_facility_id: str


__all__ = ["PublishCalibrationRevision"]
