# Governance

*Who may act at I13-1 and the trust shape CORA applies. This is CORA's governance design landing on the coherence-branch endstation, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not in the `i13_1` dodal module (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as the other Diamond beamlines, and the same partial-first-cut posture as the I13-1 scaffold overall: only the coherence-branch endstation is in this cut, and the shared I13 source and optics are deferred (SRC-1, OPT-1).

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Diamond Site. An I13-1 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#who-acts-here) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive the [sample stage](equipment/sample.md) through a ptychography raster, arm the [Merlin detector](equipment/detector.md) to record the far-field coherent-diffraction pattern, view the sample on the side camera, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

Because I13-1 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zone grouping the coherence-branch resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

## The Enclosure I13-1 gates

This cut covers a single enclosure, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| `i13-1` | `BL13J` | the coherence-branch experiment hutch: the PI piezo sample-scanning stage, the Aravis / GenICam side camera, and the Merlin / Medipix3 detector |

The shared I13 source and the I13-2 imaging branch are out of this cut and not part of the Zone here (SRC-1, OPT-1).

## The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from the `i13_1` dodal module, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The Diamond PSS clearance is carried pending because its form names are not confirmed (PSS-1).

## Coherent imaging under custody

I13-1's reason for existing is coherent lensless imaging: a ptychography or coherent-diffraction-imaging acquisition raster-scans the coherent beam across the sample and records the far-field diffraction, and a real-space image is reconstructed from that diffraction stack. In CORA's model this novelty is an acquisition shape and a reconstruction, a Method, not a new device class (TECH-1); the devices it gates are a raster LinearStage and Cameras (SAMPLE-1, DET-1), and the reconstruction is ComputePort work, not a beamline device. That makes the repeated raster acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the raster and arm the Merlin detector, and the Campaign and Subject shapes carry the sample's custody and the diffraction record.

If an autonomous Agent were added (for example to step the raster or decide when a diffraction stack is complete enough to reconstruct), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; with the shared source and optics deferred and the ptychography Method carried pending (SRC-1, OPT-1, TECH-1), this stays design intent.

## What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from the `i13_1` dodal module, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The shared I13 source and optics (SRC-1, OPT-1).** Upstream and absent from the module; deferred, not invented. No monochromator, mirror, slit, or undulator Asset is coined.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](questions.md); where each device and Method lands is on [Model](model.md).
