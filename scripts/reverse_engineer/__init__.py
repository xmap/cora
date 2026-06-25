"""Reverse-engineer APS *-bits Bluesky repos into candidate CORA deployment facts.

Pure-Python, zero cora.* imports, consistent with the rest of scripts/. The
package reads a *-bits repo (Guarneri devices.yml + ophyd device classes +
user_group_permissions.yaml) and emits CANDIDATE deployment facts: a per-beamline
facts report, a draft beamline.yaml fragment (every value that cannot be resolved
statically is flagged confirm), and a cross-fleet recurrence report ranking
catalog Family graduation candidates.

The tool stops at candidates by design. It never writes to deployments/ or
catalog/; the modeling judgment (Family graduation, naming, what to deploy) stays
with a person. See research/aps-reverse-engineering/ for the framing.
"""

from __future__ import annotations
