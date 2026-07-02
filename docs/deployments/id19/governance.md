# Governance

*Who may act at ID19 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the BLISS config (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as the other beamlines.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the ESRF Site. An ID19 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The ESRF operator pool and review structure are site-level and shared across the beamlines, so they are not instantiated per beamline; they are carried pending on the [ESRF Site page](../esrf/index.md#safety-and-governance) (GOV-1). None of this is in the BLISS config, which is a controls device database, not an organizational record.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive a [rotation stage](sample.md) through a tomographic scan, arm a [detector](detector.md) to record the projection stack, move the monochromator or open a shutter, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The ESRF proposal and cycle are a fact CORA's Campaign uses for custody.

Because ID19 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zones grouping the optics and endstation resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

## The Enclosures ID19 gates

This cut covers two enclosures, the grouping CORA's Zones would follow (ENC-1):

| Enclosure | Role | What it holds |
| --- | --- | --- |
| `id19-optics` | optics hutch | the insertion-device source, the TripleMono, the primary / secondary slits, the transfocator, the attenuators, and the front-end / beam shutters |
| `id19-experiment` | experiment hutch | the MR and HR tomographic rotation stages, their sample positioning stacks, the Lima area detectors, and the detector propagation stages |

A shared optics hutch feeding two tomography endstations in one experiment hutch is the governance shape: which endstation is taking beam, and who may drive the shared optics, is the kind of question the Zone and Policy answer.

## The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the shutters are what those leaves gate. The shutter handles are known from the config (`frontend`, `id19/bsh/1`, `id19/bsh/2`, all TangoShutters), but the PSS permit signals behind them are not in the config, so CORA does not name them and does not invent them: the Enclosure permit signals are carried pending (PSS-1). When staff confirm the permit signal handles, they bind to the Enclosure as the permit leaves the way the operating siblings carry theirs. No interlock or PSS tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the ESRF Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The ESRF PSS clearance is carried pending because its form names are not confirmed (PSS-1).

## Microtomography under custody

ID19's reason for existing is microtomography: a tomographic acquisition spins the sample through the beam and records a stack of projection radiographs, and a real-space volume is reconstructed from that stack. In CORA's model this is the existing `tomography` Method, not a new technique (TECH-1); the devices it gates are `RotaryStage`, `LinearStage`, and `Camera` Assets (SAMPLE-1, DET-1), and the reconstruction is `ComputePort` work, not a beamline device. That makes the repeated tomographic acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the rotation and arm the detector, and the Campaign and Subject shapes carry the sample's custody and the projection record.

The governance shape is the same CORA brings to every beamline; what is different at ID19 is one layer down, in the control floor (BLISS / Tango, not EPICS, see [Controls](controls.md)). The trust boundary is control-floor-agnostic: it gates commands by Actor and state regardless of whether the floor underneath is EPICS or BLISS.

If an autonomous Agent were added (for example to centre the sample or decide when a scan is complete), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; this stays design intent.

## What is deliberately not modelled

- **The PSS permit signals (PSS-1).** The shutter handles are known; the permit signals behind them are not in the config, carried pending, not invented.
- **The ESRF operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the ESRF Site, not instantiated per beamline.
- **The further endstations (ENDSTATION-1).** MH, MED, laminography, radiography, and PCO are noted, not modelled in this cut.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](questions.md); where each device and Method lands is on [Model](model.md).
