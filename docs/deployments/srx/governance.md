# Governance

*Who may act at SRX and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An SRX beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a scan, switch technique, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## Multi-technique and agents

SRX's breadth (a user may map, then scan an edge, then take a tomogram in one beamtime) is a place where an autonomous Agent could choose the next technique or region. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each choice would be a [Decision](../../architecture/modules/decision/index.md). SRX also carries an auto-alignment routine in source; conducted by CORA, that is the engine's, with any agent-proposed corrections recorded as Decisions. None is declared yet.
