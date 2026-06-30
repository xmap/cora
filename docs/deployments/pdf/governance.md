# Governance

*Who may act at PDF and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A PDF beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may change the incident energy, move a detector tower to a new distance, set a sample-environment temperature ramp, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## In-situ and high-throughput runs

A variable-temperature total-scattering series or a high-throughput sample queue can run long and unattended, which is where CORA's trust shape earns its keep: the engine holds the temperature ramp and the acquisition while the trust boundary bounds what may change mid-series and who may intervene. If an autonomous Agent were added to steer acquisition (choose the next temperature point, decide when the pattern statistics are sufficient, trigger a PDF reduction to check the result), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
