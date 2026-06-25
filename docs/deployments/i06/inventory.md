# Inventory

*The CORA Asset model for the operational core of i06 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared soft X-ray optics spine (the PGM and the twin APPLE-II undulators) and the two endstations: the i06-1 diffraction-dichroism endstation and the i06-2 PEEM endstation. The absent detectors (the i06-1 scattering detector and the PEEM electron-image column) and the simulated devices are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i06/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. i06, CORA's first APPLE-II (variable polarization) source, coins **no new Family and changes nothing in the catalog**: the two APPLE-II undulators reuse `InsertionDevice`, the polarization is modelled as a `PseudoAxis` (a sibling of the energy axis), the PGM reuses `GratingMonochromator`, the PEEM manipulators reuse the graduated `Manipulator`, and the Lakeshore controllers reuse the graduated `TemperatureController` (see [Model](model.md#what-makes-i06-new)). Control handles are filled from dodal; no vendor Models are bound.

## The Asset tree

Root Asset `I06` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `I06` | `Unit` | (root) | - | bound to the Diamond Site; Sector 06 |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only (MACHINE-1) |
| `UndulatorDownstream` | `Device` | InsertionDevice | i06-optics | downstream (IDD) APPLE-II undulator, `SR06I-MO-SERVC-01` (SRC-1, POL-2) |
| `UndulatorUpstream` | `Device` | InsertionDevice | i06-optics | upstream (IDU) APPLE-II undulator, `SR06I-MO-SERVC-21`; drives the energy / polarization handles (SRC-1, POL-2) |
| `Monochromator` | `Device` | GratingMonochromator | i06-optics | soft X-ray plane-grating mono, `BL06I-OP-PGM-01` (MONO-1) |
| `BeamEnergy` | `Device` | PseudoAxis | i06-optics | incident-energy axis over the PGM and the APPLE-II gap (MONO-1) |
| `Polarization` | `Device` | PseudoAxis | i06-optics | the fleet-first polarization axis over the APPLE-II phase rows (POL-1, POL-2) |
| `Diffractometer` | `Device` | Goniometer | i06-1 | diffraction-dichroism sample circles + detector arm, `BL06J-EA-DDIFF-01` (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | i06-1 | reciprocal-space axis over the diffractometer circles (DIFF-2) |
| `AbsorptionStage` | `Device` | LinearStage | i06-1 | XAS / absorption sample stage, `BL06J-EA-XABS-01` (STAGE-1) |
| `CoolingController` | `Device` | TemperatureController | i06-1 | Lakeshore 336 sample cooling, `BL06J-EA-TCTRL-02` (TEMP-1) |
| `HeatingController` | `Device` | TemperatureController | i06-1 | Lakeshore 336 sample heating, `BL06J-EA-TCTRL-03` (TEMP-1) |
| `PeemManipulator` | `Device` | Manipulator | i06-2 | PEEM UHV sample manipulator (x / y / phi + energy slit), `BL06K-MO-PEEM-01` (MANIP-1) |
| `PeemSampleStage` | `Device` | Manipulator | i06-optics | the i06-branch PEEM sample stage (x / y / phi), `BL06I-MO-PEEM-01` (MANIP-1) |

Families reused from the catalog: `InsertionDevice`, `GratingMonochromator`, `PseudoAxis`, `Goniometer`, `LinearStage`, `TemperatureController`, `Manipulator`. Loose families reused from siblings: `StorageRing`. No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the three PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| APPLE-II periods, gap range, coordination | `UndulatorDownstream`, `UndulatorUpstream` | `unknown-pending-confirmation` | (SRC-1) |
| IDD / IDU driven-handle asymmetry | the insertion devices | `unknown-pending-confirmation` | (POL-2) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| PGM gratings, cff, energy range | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Polarization domain and conversion rule | `Polarization` | `unknown-pending-confirmation` | (POL-1) |
| Diffractometer circle roles and Assembly | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space inverse-kinematics rule | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| Absorption-stage Goniometer-vs-placeholder | `AbsorptionStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Lakeshore cooling / heating ranges | `CoolingController`, `HeatingController` | `unknown-pending-confirmation` | (TEMP-1) |
| Diffraction detector and flux monitor | (absent from dodal) | `unknown-pending-confirmation` | (DET-1) |
| PEEM manipulator axis sets | `PeemManipulator`, `PeemSampleStage` | `unknown-pending-confirmation` | (MANIP-1) |
| PEEM electron-image column / detector | (absent from dodal) | `unknown-pending-confirmation` | (PEEM-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
| Diamond operator pool and review | governance | `unknown-pending-confirmation` | (GOV-1) |
