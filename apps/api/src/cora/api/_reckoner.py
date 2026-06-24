"""Compatibility shim: the Reckoner CLASS dissolved into `EdgeConductor`.

The compute-Run conduct runtime once lived here as a standalone
`Reckoner` class, peer to the Procedure `Conductor`. The slice-6
dissolution merged the two near-identical `conduct()` spines into one
edge-runtime shell (`EdgeConductor`) with an injected per-FSM
terminalize pair + reraise policy; the compute-Run path is now
`ComputeRunDriver` over that shell.

`Reckoner` / `ReckonerResult` survive ONLY as aliases so existing
callers (the parity scenario + the unit tests) keep importing the old
names while the behaviour is the merged engine's. Production wiring (the
conduct route, the MCP tool, the lifespan) names `ComputeRunDriver` /
`RunConductOutcome` directly. Drop these aliases once those callers
migrate; nothing new should import them.
"""

from __future__ import annotations

from cora.api._edge_conductor import ComputeRunDriver, RunConductOutcome

Reckoner = ComputeRunDriver
ReckonerResult = RunConductOutcome

__all__ = ["Reckoner", "ReckonerResult"]
