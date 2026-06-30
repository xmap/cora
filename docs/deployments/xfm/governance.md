# Governance

*Who may act at XFM and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An XFM beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may set the energy, start a raster map, run the Maia fly-scan, change the focusing optic, override a caution, or commit an energy calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## The scanning map under custody

XFM's defining operation is the raster XRF map: the UTS stage sweeps the sample through the focused spot while the detectors count per pixel. CORA's Campaign and Trust shapes are where that resolves: starting a map (step or Maia fly) is a command the trust boundary gates, and the per-map energy and flux normalization are facts under custody. If an autonomous Agent were added to drive a mapping survey (a common pattern at high-throughput microprobes), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
