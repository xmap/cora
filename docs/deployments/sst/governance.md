# Governance

*Who may act at SST and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An SST beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may select the active branch and endstation, start an acquisition, sweep energy, run an in-situ program, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## Two branches under one custody

SST's defining governance wrinkle is that two branches and several endstations share one sector and one beamtime allocation. CORA's Campaign and Trust shapes are where that resolves: the endstation in control is a beamline-state fact the trust boundary reads, so a command valid for the soft RSoXS endstation is not automatically valid when the tender HAXPES endstation is live. If an autonomous Agent were added to drive an endstation, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.
