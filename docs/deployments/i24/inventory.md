# Inventory

*The CORA Asset model for the operational core of i24 modelled today: the planned device tree and what still needs confirming.*

This cut models the `BL24I` optics and the serial-crystallography endstation; the simulated devices and the GDA-side collection software are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i24/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. i24, the first serial / fixed-target deployment, introduces **no new Family**: every device reuses existing catalog or loose vocabulary. The novelty is the serial-collection Capability and the fixed-target chip Fixture, both carried as questions (see [Model](model.md#deliberately-not-here-yet)). Control handles are filled from dodal; no vendor Models are bound.

## The Asset tree

Root Asset `I24` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `I24` | `Unit` | (root) | - | bound to the Diamond Site; sector 24 |
| `Synchrotron` | `Device` | StorageRing (loose) | - | machine source state, observe-only (MACHINE-1) |
| `Monochromator` | `Device` | Monochromator | i24-optics | double-crystal monochromator (MONO-1) |
| `FocusingMirrors` | `Device` | Mirror | i24-optics | focusing mirrors with selectable mode (OPT-1) |
| `Attenuator` | `Device` | Filter | i24-optics | filter-based attenuator (ATTN-1) |
| `Aperture` | `Device` | Aperture | i24-optics | beam-defining aperture (OPT-2) |
| `Goniometer` | `Device` | Goniometer | i24-experiment | vertical pin goniometer; reuses the I03-graduated Family (GONIO-1) |
| `ChipStage` | `Device` | LinearStage | i24-experiment | fixed-target chip XYZ stage (dodal PMAC); chip-as-Fixture is CHIP-1, the raster seam is SSX-1 |
| `Backlight` | `Device` | Backlight (loose) | i24-experiment | dual sample backlight; reused from I03 (BACKLIGHT-1) |
| `OnAxisViewer` | `Device` | Camera | i24-experiment | on-axis-view alignment camera + beam-centre (CTRL-1) |
| `Beamstop` | `Device` | BeamStop | i24-experiment | positioned beamstop (OPT-2) |
| `SampleShutter` | `Device` | Shutter | i24-experiment | fast Zebra-controlled sample shutter (SSX-1) |
| `EigerDetector` | `Device` | Camera | i24-experiment | Eiger area detector, production (DET-1) |
| `JungfrauDetector` | `Device` | Camera | i24-experiment | Jungfrau area detector, commissioning (DET-1) |
| `DetectorStage` | `Device` | LinearStage | i24-experiment | detector translation (Y/Z) (OPT-2) |
| `Timing` | `Device` | TimingController | i24-experiment | Zebra FPGA triggering of detector + shutter (SSX-1) |
| `HutchShutter` | `Device` | Shutter | i24-optics | interlocked hutch photon shutter (PSS-1) |

Families reused from the catalog: `Monochromator`, `Mirror`, `Filter`, `Aperture`, `Goniometer`, `LinearStage`, `Camera`, `BeamStop`, `Shutter`, `TimingController`. Loose families reused from siblings: `StorageRing`, `Backlight` (both from the Diamond / APS fleet). **No new family is coined**, and the catalog is unchanged.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Insertion-device source detail | the source | `unknown-pending-confirmation` | (SRC-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Machine source-state read | `Synchrotron` | `unknown-pending-confirmation` | (MACHINE-1) |
| DCM cut, d-spacing, energy range | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and focus modes | `FocusingMirrors` | `unknown-pending-confirmation` | (OPT-1) |
| Attenuator filter set | `Attenuator` | `unknown-pending-confirmation` | (ATTN-1) |
| Aperture / beamstop / detector-stage axes | the optics and stages | `unknown-pending-confirmation` | (OPT-2) |
| Goniometer circle and pin axes | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Fixed-target chip addressing and grid map | `ChipStage` | `unknown-pending-confirmation` | (CHIP-1) |
| Serial-collection sequence and triggers | `ChipStage`, `SampleShutter`, `Timing` | `unknown-pending-confirmation` | (SSX-1) |
| PMAC laser model vs hazard | `ChipStage` | `unknown-pending-confirmation` | (LASER-1) |
| Backlight PV root and positions | `Backlight` | `unknown-pending-confirmation` | (BACKLIGHT-1) |
| Detector config (Eiger / Jungfrau / beam-centre) | `EigerDetector`, `JungfrauDetector` | `unknown-pending-confirmation` | (DET-1) |
| PSS permit signals | the enclosures, `HutchShutter` | `unknown-pending-confirmation` | (PSS-1) |
| Vacuum extent and supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
