# Governance

*Who may act at AMX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An AMX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may set the energy, move the goniometer, start a rotation data collection or a grid scan, drive the robot, override a caution, or commit a beam-centre calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer (the LSDC Governor). The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## The autonomous loop under custody

AMX is "highly automated": its defining governance wrinkle is the unattended EMBL-robot sample-exchange loop. CORA's Campaign, Trust, and Subject shapes are where that resolves: the robot loading a crystal is a command the trust boundary gates, and the crystal is a `Subject` whose custody (Received to mounted-on-goniometer to measured to Returned / Stored) is the record of record. The autonomous loop is gated by a `Clearance` issued after a safety review, the same pattern as i03 and FMX. An autonomous Agent driving the load-centre-collect-unmount cycle would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; the autonomous-loop lifecycle is deferred (ROBOT-1).
