# Governance

*Who may act at CDI and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A CDI beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may align the KB nanofocus, change the incident energy, arm a ptychographic scan, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## Long unattended scans

A ptychographic map or a Bragg-CDI rocking series can run long and unattended, which is where CORA's trust shape earns its keep: the engine holds the scan while the trust boundary bounds what may change mid-acquisition and who may intervene. If an autonomous Agent were added to steer acquisition (choose the next scan region, decide when the diffraction signal is sufficient, trigger a reconstruction to check convergence), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
