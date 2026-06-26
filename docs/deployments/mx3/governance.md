# Governance

*Who may act at MX3 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [Australian Synchrotron Site](../as/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not in the device library (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Australian Synchrotron Site. An MX3 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. This is the same role kernel CORA seeds at every Site; MX3 being a new Site is exactly the test that the Federation / Access kernel ports unchanged.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a collection, move the robot, change the energy, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer, and it holds the same across all four control planes (a command to the Eiger over REST or the robot over TCP is gated exactly as an EPICS motor move is). The facility proposal and cycle are a fact CORA's Campaign uses for custody.

## Unattended autonomous collection

MX3's throughput model is unattended: the ISARA robot mounts a crystal, the MD3 centres it, the Eiger collects, the robot unmounts, repeat. That loop is where CORA's custody and trust shapes earn their keep, each crystal threaded through the `Subject` aggregate so its identity and provenance is tracked, the exchange a Procedure gated by a Clearance (ROBOT-1). If an autonomous Agent were added to choose which crystal to collect or when a dataset is good enough, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
