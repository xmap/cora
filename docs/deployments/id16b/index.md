# ID16B

*Hard X-ray nano-analysis and nano-imaging on the ESRF nanoprobe beamline: Kirkpatrick-Baez-focused nano-tomography and nano-XRF (X-ray fluorescence) mapping, including fluorescence-tomography. This page describes how CORA would model and run ID16B, reverse-engineered from the beamline's own public BLISS control configuration; it is not yet confirmed by ESRF staff. ID16B is CORA's third non-EPICS deployment and the fleet's first nanoprobe on a BLISS floor.*

| Property | Value |
| --- | --- |
| Asset | `ID16B` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ESRF](../esrf/index.md) (bound via `facility_code = "esrf"`, `FacilityKind = Site`) |
| Sector | ID16B, the nano-analysis branch (control Tango domain `id16b` / `id16na`) |
| Status | Reverse-engineered from the public ID16B BLISS config; source, optics, KB nanofocus, sample stack, and detection modelled; sample environments noted (ENV-1) |
| Source | ESRF-EBS U205 undulator (SRC-1) |
| Control stack | **ESRF BLISS (Tango-based), not EPICS** (CTRL-1) |

!!! warning "How CORA would land on ID16B, and the confirm-pending posture"
    These pages describe how CORA would model, govern, and conduct ID16B. They are not a survey of the beamline's current software. The hardware facts (devices, BLISS objects, Tango handles) are read from ID16B's own public Beacon device database ([`gitlab.esrf.fr/id16b/beamline_configuration`](https://gitlab.esrf.fr/id16b/beamline_configuration)). Device names and control handles are real; vendor part numbers, serials, energy ranges, and focal-spot sizes are not in the config and are open questions. Every value is carried `confirm` until ID16B staff verify it. This cut models the source, the optics (including the KB nanofocus), the sample-scanning stack, and the two detection chains; the sample environments (cryostream, furnace, xeol) are noted, not modelled (ENV-1).

## What makes ID16B different

ID16B is the fleet's **first KB nanoprobe with XRF** and CORA's **third non-EPICS deployment** after [ID32](../id32/index.md) and [ID19](../id19/index.md). It earns its place on two axes at once, while staying vocabulary-neutral.

- **It deepens the BLISS / Tango floor evidence.** Like ID19, ID16B runs ESRF BLISS (Tango-based), not EPICS. A second beamline on the same non-EPICS floor confirms the seam pattern from ID19 is not a one-off: motion stages are BLISS axes, detectors are Lima / MOSCA Tango device servers, and CORA's edge conducts over the `ControlPort` against that floor (CTRL-1).
- **It is the first KB nanoprobe with XRF in the fleet.** The Kirkpatrick-Baez mirror pair focuses the beam to a nanoprobe, and the beamline runs nano-XRF mapping (raster the sample through the nanofocus, read a fluorescence spectrum per point) alongside nano-tomography. This is the first time a KB nanofocus and an energy-dispersive fluorescence detector appear at an ESRF deployment.
- **Yet it coins nothing new.** Nano-tomography is plain `tomography` Method reuse (ID19, 2-BM, TomoWise). Nano-XRF mapping reuses the pending `scanning_fluorescence_microscopy` Method that APS 2-ID, NSLS-II XFM, and LIX already carry. The KB mirrors bind `Mirror`, the fluorescence detector binds `EnergyDispersiveSpectrometer` (the 2-ID / SRX / XFM precedent), the area detectors bind `Camera`, the stages bind `RotaryStage` / `LinearStage`. ID16B coins no new Family and changes nothing in the catalog.

The net: ID16B reuses every device family and both Methods, and its contribution is a further beamline on the BLISS floor plus the first nanoprobe-and-XRF combination, landing on existing vocabulary.

## Scope: what is and is not modelled

| In this cut | Noted, not modelled |
| --- | --- |
| The U205 undulator source (SRC-1) | the cryostream / furnace / xeol sample environments (no `Cryostat` Family yet; ENV-1) |
| The optics: Kohzu DCM, primary / secondary slits, beam monitors (OPT-1) | the `mapping` / `oda` / `taurus` / `webui` software layers (not beamline devices) |
| The KB nanofocus mirrors and sample-side slits (OPT-1) | the simulation sessions |
| The sample stack: rotation, coarse positioning, PI piezo raster scanner (SAMPLE-1) | vendor models, serials, focal-spot sizes (carried confirm) |
| The detection: FalconX XRF detector, optical spectrometer, PCO / Zyla area detectors, detector stage (DET-1, DET-2) | |

Two enclosures are modelled: the optics hutch `id16b-optics` and the experiment hutch `id16b-experiment` (ENC-1).

## Key modelling decisions

- **Zero new families.** The KB mirrors bind `Mirror`, the fluorescence detector binds `EnergyDispersiveSpectrometer`, the area detectors bind `Camera`, the stages bind `RotaryStage` / `LinearStage`, and the optics bind `Monochromator` / `Slit` / `FluxMonitor` / `Shutter` / `InsertionDevice`. Nothing graduates.
- **Two Methods, both reused.** Nano-tomography is the existing `tomography` Method; nano-XRF mapping is the pending `scanning_fluorescence_microscopy` Method (2-ID / XFM / LIX), here a further consumer (TECH-1, METHOD-1).
- **The fluorescence detector binds `EnergyDispersiveSpectrometer`.** ID16B's FalconX silicon-drift detector is the same shape as the XFM Xspress3 and the 2-ID / SRX detectors: a per-point energy spectrum, a Sensor, not a 2D Frame (DET-1).
- **The sample environments are deferred (ENV-1).** A `Cryostat` Family is not yet in the catalog; the cryostream / furnace / xeol environments are noted, not modelled, to keep this cut vocabulary-neutral.
- **The control floor is BLISS / Tango, with real handles.** The descriptor `pv` field carries the real BLISS object and Tango device names read from the config. See [Controls](equipment/controls.md) (CTRL-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the U205 undulator and the conditioning optics (Kohzu DCM, slits, beam monitors) and the shutters (SRC-1, OPT-1, PSS-1).
- [Sample](equipment/sample.md): the KB nanofocus mirrors and the sample-scanning stack (rotation, coarse positioning, PI piezo raster scanner) (OPT-1, SAMPLE-1).
- [Detector](equipment/detector.md): the FalconX XRF detector and optical spectrometer, the PCO / Zyla area detectors, and the detector stage (DET-1, DET-2).

Cutting across:

- [Controls](equipment/controls.md): the ESRF BLISS (Tango-based) control stack, a further beamline on the BLISS floor, with the real handles read from the config (CTRL-1). The PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).

The cross-cutting reference view is the [Inventory](inventory.md), authored from the same descriptor as the generated [Source](beamline.md) walk.

## Techniques

[Techniques](techniques.md): KB-focused nano-tomography (the `tomography` Method) and nano-XRF mapping including fluorescence-tomography (the pending `scanning_fluorescence_microscopy` Method), bound through pending [ESRF Practices](../esrf/index.md#the-techniques-adapted-here) (TECH-1, METHOD-1). ID16B coins no new Method.

## Governance

[Governance](governance.md): who may act at ID16B and the trust shape CORA applies. People and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#who-acts-here), gated by a trust shape (Zone + Conduit + Policy). Clearances are issued at the ESRF Site; the operator pool and review are carried pending (GOV-1).

## Model

[Model](model.md): the developer's by-kind index into where each ID16B aggregate's content lives, why this nanoprobe deployment coins no new vocabulary, and the record of what is deliberately deferred.

## Not yet documented

ID16B is not yet driven by CORA, so the operations runbook (procedures, recipes, cautions, enclosure permits) and the live experiment view are deliberately not written yet: a runbook for a beamline CORA does not yet drive would be invention, not record. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The sample environments (cryostream, furnace, xeol) are noted, not modelled (ENV-1); the PSS permit signals behind the shutters are not in the config and carried pending (PSS-1).
