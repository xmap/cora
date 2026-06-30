# Inventory

*The CORA Asset model for the operational core of i19 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared `BL19I` optics and the two experiment hutches (EH1 and EH2); the simulated devices and the centring image-recognition behaviour are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i19/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. i19, CORA's first chemical (small-molecule) crystallography beamline, coins **no new Family and changes nothing in the catalog**: the Newport kappa four-circle binds the catalog `Goniometer` (kappa is a setting) inside the named-not-built `Assembly(Diffractometer)`, and the MAPT pinhole and collimator bind the catalog `Aperture` (the i03 precedent). The genuine novelty is the dual-hutch shared-optics access-control seam, a governance concern, not a device family (see [Model](model.md#the-dual-hutch-access-control-seam)). Control handles are filled from dodal; no vendor Models are bound.

## The Asset tree

Root Asset `I19` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `I19` | `Unit` | (root) | - | bound to the Diamond Site; Sector 19 |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `Undulator` | `Device` | InsertionDevice | i19-optics | the undulator, `SR19I-MO-SERVC-01` (SRC-1) |
| `Monochromator` | `Device` | Monochromator | i19-optics | double-crystal mono, `BL19I-MO-DCM-01` (MONO-1, ACCESS-1) |
| `HorizontalFocusingMirror` | `Device` | Mirror | i19-optics | HFM with piezo + coating stripe, `BL19I-OP-HFM-01` (OPT-1) |
| `VerticalFocusingMirror` | `Device` | Mirror | i19-optics | VFM with piezo + coating stripe, `BL19I-OP-VFM-01` (OPT-1) |
| `Attenuator` | `Device` | Filter | i19-optics | absorber-wedge attenuator, `BL19I-OP-ATTN-04/05` (ATTN-1) |
| `BeamEnergy` | `Device` | PseudoAxis | i19-optics | incident-energy axis over the DCM + undulator (MONO-1, ACCESS-1) |
| `OpticsShutter` | `Device` | Shutter | i19-optics | PSS-interlocked experiment shutter, `BL19I-PS-SHTR-01` (PSS-1, ACCESS-1) |
| `SampleViewerOnAxis` | `Device` | Camera | i19-1 | on-axis OAV viewing camera with zoom, `BL19I-EA-OAV-01` (DET-1) |
| `SampleViewerDiagonal` | `Device` | Camera | i19-1 | diagonal OAV viewing camera, `BL19I-EA-OAV-02` (DET-1) |
| `TriggerControllerEH1` | `Device` | TimingController | i19-1 | EH1 Zebra trigger box, `BL19I-EA-ZEBRA-02` (DET-1) |
| `BeamstopEH1` | `Device` | BeamStop | i19-1 | EH1 beamstop with homing, `BL19I-RS-ABSB-01` (DET-1) |
| `Diffractometer` | `Device` | Goniometer | i19-2 | Newport kappa four-circle (phi/omega/kappa + 2theta arm + det_z), `BL19I-MO-CIRC-02` (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | i19-2 | reciprocal-space axis over the four-circle (DIFF-2) |
| `Detector` | `Device` | Camera | i19-2 | Eiger area detector, `BL19I-EA-EIGER-01` (DET-1) |
| `SerialStage` | `Device` | Goniometer | i19-2 | serial / microfocus fixed-target arm (x/y/z/phi), `BL19I-MO-SRL-01` (SERIAL-1) |
| `Aperture` | `Device` | Aperture | i19-2 | MAPT pinhole + collimator microfocus aperture, `BL19I-OP-PCOL-01` (APERTURE-1) |
| `BeamstopEH2` | `Device` | BeamStop | i19-2 | EH2 beamstop with homing, `BL19I-OP-ABSB-02` (DET-1) |
| `Backlight` | `Device` | Backlight (loose) | i19-2 | sample backlight (in/out), `BL19I-EA-IOC-12`; 4th sighting, held (DET-1) |
| `TriggerControllerEH2` | `Device` | TimingController | i19-2 | EH2 Zebra trigger box, `BL19I-EA-ZEBRA-03` (DET-1) |
| `TriggerSequencer` | `Device` | TimingController | i19-2 | EH2 PandA hardware sequencer, `BL19I-EA-PANDA-01` (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Filter`, `PseudoAxis`, `Shutter`, `Camera`, `TimingController`, `Goniometer`, `BeamStop`, `Aperture`. Loose families reused from siblings: `StorageRing` (supply), `Backlight` (i03 / i24 / fmx; fourth sighting, held under review DET-1). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| EH1 / EH2 grouping and which hutch holds the four-circle | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Dual-hutch shared-optics access-control permit + arbiter | the shared optics | `unknown-pending-confirmation` | (ACCESS-1) |
| Undulator period and type | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| DCM cut, energy / wavelength range, partition rule | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and stripe bands | the focusing mirrors | `unknown-pending-confirmation` | (OPT-1) |
| Attenuator catalog home | `Attenuator` | `unknown-pending-confirmation` | (ATTN-1) |
| Four-circle circle roles and Assembly | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space partition rule | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| Serial / microfocus arm and raster sub-mode | `SerialStage` | `unknown-pending-confirmation` | (SERIAL-1) |
| MAPT pinhole + collimator Aperture binding | `Aperture` | `unknown-pending-confirmation` | (APERTURE-1) |
| Eiger model, OAV roles, beamstops, backlight | `Detector`, the viewers, the beamstops, `Backlight` | `unknown-pending-confirmation` | (DET-1) |
| Vacuum extent | `resources` | `unknown-pending-confirmation` | (SUP-1) |
