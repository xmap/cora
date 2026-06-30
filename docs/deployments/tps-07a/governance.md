# Governance

*Who may act at TPS 07A and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSRRC Site](../nsrrc/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not in the public control trees (GOV-1), so the principals are the design shape, not a registered list. The trees do expose two governance facts CORA maps onto its own model: LDAP-backed authentication (`ldap://10.7.1.1`) and a mandatory radiation-safety-training portal (`safetytraining.nsrrc.org.tw`).

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSRRC Site. A TPS 07A beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. This is the same role kernel CORA seeds at every Site; NSRRC being a new Site is exactly the test that the Federation / Access kernel ports unchanged.

The NSRRC mandatory training portal maps to CORA's **worldwide-invariant training axis**: a fact carried on the Access principals (has-this-person-completed-the-required-training), not a separate Clearance kind. CORA records it as a property of the principal rather than coining a new facility form (GOV-1).

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a collection, move the robot, change the energy, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer or its LDAP groups. It holds across the seam: a command CORA's EdgeConductor issues in place of DCSS (start an oscillation, drive a motor, arm the detector) is gated exactly as any spine command is. The facility proposal and cycle are a fact CORA's Campaign uses for custody.

## Unattended autonomous collection

TPS 07A's throughput model is unattended: the ISARA robot mounts a crystal, the MD3 centres it (mesh scan + Dozor scoring), the EIGER2 collects, the robot unmounts, repeat. That loop is where CORA's custody and trust shapes earn their keep, each crystal threaded through the `Subject` aggregate so its identity and provenance is tracked, the exchange a Procedure gated by a Clearance (ROBOT-1). If an autonomous Agent were added to choose which crystal to collect or when a dataset is good enough (the CHiMP crystal-detection output is the natural input), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## The detector safety interlock

The control tree exposes a hard detector minimum-distance interlock (139 mm): the detector stage may not approach the sample closer than that. This is a floor-level hardware safety limit, not a CORA-owned gate; CORA's conduct path respects it as a constraint on the detector-distance command, the same way it respects an EPICS soft limit. The PSS search-and-secure permit leaves that gate the hutch are not in the public source (PSS-1) and are carried as a confirm.
