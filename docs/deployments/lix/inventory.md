# Inventory

*The CORA Asset model for the operational core of LIX modelled today: the planned device tree and what still needs confirming.*

This cut models the XF:16IDA / XF:16IDB optics and the XF:16IDC solution / scanning endstation; the fluidic-delivery valves, the SEC column, the flow cell, the sample robot, and the disabled attenuator and temperature controllers are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/lix/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. LIX coins **no new Family and changes nothing in the catalog**: the optics and detectors reuse the existing `InsertionDevice` / `Monochromator` / `Mirror` / `Slit` / `Transfocator` / `Camera` / `EnergyDispersiveSpectrometer` / `FluxMonitor` vocabulary, and the one reuse worth naming is the HPLC delivery pump, which binds the existing loose `FlowController` Family (its third consumer; see [Model](model.md#the-flowcontroller-rule-of-three)). The genuinely-new parts, the solution Subject and the fluidic delivery chain, land on Subject / Supply / Procedure and the seam, not on devices. Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `LIX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `LIX` | `Unit` | (root) | - | bound to the NSLS-II Site; 16-ID |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `Undulator` | `Device` | InsertionDevice | lix-optics | in-vacuum undulator gap, `SR:C16-ID:G1{IVU:1}` (SRC-1) |
| `Monochromator` | `Device` | Monochromator | lix-optics | double-crystal monochromator (DCM), `XF:16IDA-OP{Mono:DCM-Ax:Bragg}` (MONO-1) |
| `BeamEnergy` | `Device` | PseudoAxis | lix-optics | incident-energy axis over the DCM Bragg angle and the undulator gap (MONO-1) |
| `WhiteBeamMirror` | `Device` | Mirror | lix-optics | white-beam heat-load / harmonic-rejection mirror, `XF:16IDA-OP{Mir:WBM}` (OPT-1) |
| `KbMirror` | `Device` | Mirror | lix-optics | Kirkpatrick-Baez focusing pair (KBH + KBV), `XF:16IDA-OP{Mir:KBH/KBV}` (OPT-1) |
| `MonoSlit` | `Device` | Slit | lix-optics | mono four-blade defining slit, `XF:16IDA-OP{Slt:1}` (OPT-2) |
| `SecondarySourceAperture` | `Device` | Slit | lix-optics | secondary-source aperture, `XF:16IDB-OP{Slt:SSA1}` (OPT-2) |
| `PhotonShutter` | `Device` | Shutter | lix-optics | personnel-protection photon shutter, `XF:16IDA-PPS{PSh}` (PSS-1) |
| `FastShutter` | `Device` | Shutter | lix-optics | millisecond fast shutter, `XF:16IDB-BI{shutter:1}` (TRIG-1) |
| `Transfocator` | `Device` | Transfocator | lix-endstation | compound refractive lens (nine groups), `XF:16IDC-OP{CRL}`; reuses the graduated Family (CRL-1) |
| `DivergenceAperture` | `Device` | Slit | lix-endstation | divergence-defining aperture, `XF:16IDC-OP{Slt:DDA}` (OPT-2) |
| `GuardSlit` | `Device` | Slit | lix-endstation | endstation guard slit, `XF:16IDC-OP{Slt:G2}` (OPT-2) |
| `SampleStage` | `Device` | Manipulator | lix-endstation | solution positioning stack (x / z + XPS scan x / y), `XF:16IDC-ES:Scan` (SAMPLE-1) |
| `ScanningGoniometer` | `Device` | Goniometer | lix-endstation | scanning-microbeam SmarAct gonio + tomo rotation, `XF:16IDC-ES:Scan2-Gonio` (SCAN-1) |
| `DeliveryPump` | `Device` | FlowController (loose) | lix-endstation | HPLC sample-delivery pump, `XF:16IDC-ES{HPLC}REGEN`; third consumer of the loose Family, rule-of-three trigger (FLUID-1, FLOW-1) |
| `SaxsDetector` | `Device` | Camera | lix-endstation | Pilatus 1M small-angle detector, `XF:16IDC-DT{Det:SAXS}` (DET-1) |
| `WaxsDetector` | `Device` | Camera | lix-endstation | Pilatus 900K wide-angle detector, `XF:16IDC-DT{Det:WAXS2}` (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | lix-endstation | Xspress3 fluorescence detector (scanning mode), `XF:16IDC-ES{Xsp:1}` (DET-1) |
| `DetectorStage` | `Device` | LinearStage | lix-endstation | SAXS / WAXS detector translations + distance, `XF:16IDC-ES{Stg:SAXS}` (DET-1) |
| `Beamstop` | `Device` | BeamStop | lix-endstation | SAXS beamstop (x / y), `XF:16IDC-ES{BS:SAXS}` (DET-1) |
| `EndstationFluxMonitor` | `Device` | FluxMonitor | lix-endstation | TetrAMM electrometers, `XF:16IDC-BI{BPM:1-2}` (DET-1) |
| `BeamPositionMonitor` | `Device` | BeamPositionMonitor (loose) | lix-endstation | Best aggregator over the TetrAMM quadrants, `XF:16IDB-CT{Best}` (DIAG-1) |
| `Trigger` | `Device` | TimingController | lix-endstation | Zebra trigger / position capture, `XF:16IDC-ES{Zeb:1}` (TRIG-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `PseudoAxis`, `Mirror`, `Slit`, `Shutter`, `Transfocator`, `Manipulator`, `Goniometer`, `Camera`, `EnergyDispersiveSpectrometer`, `LinearStage`, `BeamStop`, `FluxMonitor`, `TimingController`. Loose families reused from siblings: `StorageRing` (supply), `FlowController` (the HPLC pump, n=3, graduation candidate), `BeamPositionMonitor` (held under review, DIAG-1). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-transport-vs-endstation hutch grouping | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator model, period, length | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) and data plane | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| DCM crystal cut, energy range, partition rule | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings, bimorph, bend | `WhiteBeamMirror`, `KbMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Transfocator lens-group configuration | `Transfocator` | `unknown-pending-confirmation` | (CRL-1) |
| Whether an attenuator is live | the optics | `unknown-pending-confirmation` | (ATTN-1) |
| Solution stack axes and flow-cell mount | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Scanning gonio axes, raster, tomo rotation | `ScanningGoniometer` | `unknown-pending-confirmation` | (SCAN-1) |
| Fluidic-delivery chain and pump / valve Family | `DeliveryPump` | `unknown-pending-confirmation` | (FLUID-1) |
| SEC column, buffers, flow cell | `resources` | `unknown-pending-confirmation` | (SEC-1) |
| Sample robot and autosampler | the sample handling | `unknown-pending-confirmation` | (ROBOT-1) |
| The solution Subject | the sample | `unknown-pending-confirmation` | (SUBJECT-1) |
| Cell temperature control | the sample environment | `unknown-pending-confirmation` | (TEMP-1) |
| Detector models, Xspress3 availability, distances, channel map | `SaxsDetector`, `WaxsDetector`, `FluorescenceDetector`, `EndstationFluxMonitor` | `unknown-pending-confirmation` | (DET-1) |
| Beam-position-monitor position-vs-intensity split | `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Triggering (Zebra, XPS gate, fast-shutter TTL) | `Trigger`, `FastShutter` | `unknown-pending-confirmation` | (TRIG-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
