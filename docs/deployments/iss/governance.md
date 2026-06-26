# Governance

*Who may act at ISS and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An ISS beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may load an energy trajectory, sweep the energy, start an acquisition, move the emission-spectrometer crystals, run an in-situ program, override a caution, or commit an energy calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## The energy-scan under custody

ISS's defining operation is the trajectory energy fly-scan, which couples the monochromator, the encoder, and the streaming detectors as one timed sweep. CORA's Campaign and Trust shapes are where that resolves: loading and starting a trajectory is a command the trust boundary gates, and the per-scan energy calibration (the reference foil read on the reference ion chamber) is a committed fact under custody, not an ad-hoc adjustment. If an autonomous Agent were added to drive the EXAFS / HERFD program (a common pattern at high-throughput XAS beamlines), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
