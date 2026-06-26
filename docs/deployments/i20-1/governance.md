# Governance

*Who may act at I20-1 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [Diamond Site](../diamond/index.md); on the beamline they surface through the actions they take. The human roster is not in the dodal module (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Diamond Site. An I20-1 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may arm the detector, drive the turbo-slit fly-scan, change the energy selection, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

## Time-resolved collection

EDE's reason for existing is speed: a full absorption spectrum in sub-second time, so a reaction can be followed as it runs. That makes the unattended, repeated, fast acquisition the place CORA's custody and trust shapes earn their keep, the engine holds the fly-scan and the detector arming while the trust boundary bounds what may change mid-series. If an autonomous Agent were added to trigger collections on a sample-environment cue or decide when a kinetic series is complete, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; with the dispersive detector still an open question (STRIP-1), this stays design intent.
