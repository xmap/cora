# pyright: reportPrivateUsage=false

"""Architecture fitness: keep `_AccessProtocolLiteral` synced with `AccessProtocol`.

`cora.infrastructure.capture_scan_ingestor_binding` defines a private
`_AccessProtocolLiteral` local mirror of
`cora.data.aggregates.distribution.state.AccessProtocol` to avoid
`cora.infrastructure` importing `cora.data`, which `tach check`
forbids (infrastructure sits below every BC in the dependency
layering).

The local mirror IS load-bearing, not decorative: the alternative
(importing the real enum) would cross the module boundary tach
enforces. But mirrors drift. This fitness pins the value-set equality
so a PR that widens `AccessProtocol` (adds a transport family) without
also widening `_AccessProtocolLiteral` fails CI at PR time, rather than
at the first sweep tick when a validly-configured binding is rejected
by `Settings`.

Per the cross-BC fitness convention: AST-adjacent comparison via
`typing.get_args` and the enum's own value set, not a runtime import
cycle (there is no cycle here, but the pattern is otherwise identical
to `test_auth_principal_kind_sync.py`).
"""

from typing import get_args

import pytest

from cora.data.aggregates.distribution.state import AccessProtocol
from cora.infrastructure.capture_scan_ingestor_binding import _AccessProtocolLiteral


@pytest.mark.architecture
def test_capture_scan_ingestor_access_protocol_literal_matches_enum() -> None:
    """The mirror and the real enum MUST share the same value set.

    Drift here means `CaptureScanIngestorLocation.access_protocol`
    would accept (or reject) a string the Data BC's own
    `IngestScan` decider rejects (or accepts). Either direction is a
    silent bug: boot-time validation passes but the sweep's ingest
    fails downstream, or a valid deployment configuration is refused
    at boot for no real reason.
    """
    literal_values = set(get_args(_AccessProtocolLiteral))
    enum_values = {member.value for member in AccessProtocol}
    assert literal_values == enum_values, (
        f"_AccessProtocolLiteral and AccessProtocol have drifted: "
        f"mirror has {literal_values}, enum has {enum_values}. "
        "Update both together -- the mirror exists only to break the "
        "cora.infrastructure / cora.data tach boundary, not as an "
        "intentional value-set distinction."
    )
