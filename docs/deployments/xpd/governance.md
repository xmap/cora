# Governance

*Who may act at XPD and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An XPD beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start an acquisition, change the detector distance, run a temperature program, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## High-throughput and the sample robot

XPD's strength is throughput: a sample-array stage and a sample-changing robot let it run many powders unattended, often across temperature ramps. That is where CORA's custody and trust shapes earn their keep. CORA would model the autonomous exchange as a Procedure over the spine, threaded through the `Subject` aggregate so each sample's identity and provenance is tracked, and gated by a Clearance, the same shape as the I03 macromolecular-crystallography loop and the I15-1 powder exchange (ROBOT-1). If an autonomous Agent were added to choose the next sample or decide when a pattern is good enough, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
