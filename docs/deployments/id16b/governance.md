# Governance

*Who may act at ID16B and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the BLISS config (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as ID19 and the other beamlines.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the ESRF Site. An ID16B beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The ESRF operator pool and review structure are site-level and shared across the beamlines (ID19 and ID16B both inherit them), so they are not instantiated per beamline; they are carried pending on the [ESRF Site page](../esrf/index.md#safety-and-governance) (GOV-1).

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive the [sample rotation](sample.md) through a tomographic scan, raster the [piezo scanner](sample.md) for an XRF map, arm the [FalconX detector](detector.md) or an area detector, move the KB nanofocus or the monochromator, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The ESRF proposal and cycle are a fact CORA's Campaign uses for custody.

Because ID16B is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zones grouping the optics and endstation resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

## The Enclosures ID16B gates

This cut covers two enclosures, the grouping CORA's Zones would follow (ENC-1):

| Enclosure | Role | What it holds |
| --- | --- | --- |
| `id16b-optics` | optics hutch | the U205 undulator source, the Kohzu DCM, the primary / secondary slits, the beam monitors, and the shutters |
| `id16b-experiment` | experiment hutch | the KB nanofocus mirrors, the sample-side slits, the sample rotation / coarse / piezo-scanner stack, the FalconX XRF detector, the optical spectrometer, and the area detectors |

## The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the shutters are what those leaves gate. The shutter handles are known from the config (the front-end and `fshut` fast shutter), but the PSS permit signals behind them are not in the config, so CORA does not name them and does not invent them: the Enclosure permit signals are carried pending (PSS-1). When staff confirm the permit signal handles, they bind to the Enclosure as the permit leaves. No interlock or PSS tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the ESRF Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The ESRF PSS clearance is carried pending because its form names are not confirmed (PSS-1).

## Nano-analysis under custody

ID16B's reason for existing is nano-analysis: KB-focused nano-tomography and nano-XRF mapping. In CORA's model these are the existing `tomography` and `scanning_fluorescence_microscopy` Methods, not new techniques (TECH-1, METHOD-1); the devices they gate are `RotaryStage`, `LinearStage`, `Mirror`, `EnergyDispersiveSpectrometer`, and `Camera` Assets (SAMPLE-1, DET-1), and the reconstructions (the tomographic volume and the XRF map fitting) are `ComputePort` work, not beamline devices. That makes the repeated nano-acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the nanofocus and arm the detectors, and the Campaign and Subject shapes carry the sample's custody and the data record.

The governance shape is the same CORA brings to every beamline; what is different at ID16B is the control floor (BLISS / Tango, not EPICS, see [Controls](controls.md)) and the nanoprobe device set. The trust boundary is control-floor-agnostic and device-agnostic: it gates commands by Actor and state regardless.

If an autonomous Agent were added (for example to centre the sample on the nanoprobe or decide when an XRF map is complete), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; this stays design intent.

## What is deliberately not modelled

- **The PSS permit signals (PSS-1).** The shutter handles are known; the permit signals behind them are not in the config, carried pending, not invented.
- **The ESRF operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the ESRF Site.
- **The sample environments (ENV-1).** The cryostream, furnace, and xeol environments are noted, not modelled in this cut.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](questions.md); where each device and Method lands is on [Model](model.md).
