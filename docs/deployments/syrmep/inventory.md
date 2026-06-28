# Inventory

*The CORA Asset model for the operational core of SYRMEP modelled today: the planned device tree and what still needs confirming.*

This cut models the source and white-beam optics, the sample stage, and the detector. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/syrmep/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. SYRMEP, CORA's first Elettra deployment, **coins no new Family and changes nothing in the catalog**: it is a tomography beamline and reuses the imaging spine the 2-BM, FXI, and 7-BM beamlines already share. Control handles are **not** filled from source (SYRMEP's control plane is not public); they are confirm-pending placeholders, and no vendor Models are bound (see [Model](model.md#the-tango-donkiorchestra-control-plane)).

## The Asset tree

Root Asset `SYRMEP` (`tier = Unit`, `facility_code = elettra`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `SYRMEP` | `Unit` | (root) | - | bound to the Elettra Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | Elettra ring state (2.0 / 2.4 GeV), observe-only (MACHINE-1) |
| `source` | (Supply) | Beam (PhotonBeam) | syrmep-optics | bending-magnet beam, provenance only (SRC-1) |
| `FrontEndShutter` | `Device` | Shutter | syrmep-optics | front-end safety shutter, PSS-gated; handle not in public source (PSS-1) |
| `BeamDefiningMask` | `Device` | Mask | syrmep-optics | fixed white-beam-defining aperture; dimensions not in public source (OPT-1) |
| `Monochromator` | `Device` | Monochromator | syrmep-optics | double-crystal Si(111) DCM; mono / white beam is a setting; 10-40 keV mono (MONO-1, MODE-1) |
| `BeamEnergy` | `Device` | PseudoAxis | syrmep-optics | incident-energy axis over the DCM (MONO-1) |
| `BeamSlit` | `Device` | Slit | syrmep-optics | laminar-beam-defining slits (~120-160 x 4-5 mm at 7 mrad); handles not in public source (OPT-2) |
| `Filter` | `Device` | Filter | syrmep-optics | absorption / beam-hardening filters; foils not in public source (FOIL-1) |
| `Rotary` | `Device` | RotaryStage | syrmep-experiment | heavy-payload rotator (up to 120 kg, 1-20 deg/s, 0.02 deg) (STAGE-1) |
| `SampleStage` | `Device` | LinearStage | syrmep-experiment | five-axis sample positioner; vendors / resolution / axis map pending (SAMPLE-1) |
| `PropagationRail` | `Device` | LinearStage | syrmep-experiment | sample-to-detector propagation rail (3-160 cm) (DET-2) |
| `Scintillator` | `Device` | Scintillator | syrmep-experiment | scintillator screen (published configs cite GGG:Eu) (DET-3) |
| `TomographyCamera` | `Device` | Camera | syrmep-experiment | 16-bit sCMOS (2048x2048, 0.9-5.7 um); a routine-camera candidate (DET-1) |
| `CCDCamera` | `Device` | Camera | syrmep-experiment | 12/16-bit CCD (4008x2672, 4.5 um, PSF ~13 um); a routine-camera candidate (DET-1) |
| `PhotonCountingCamera` | `Device` | Camera | syrmep-experiment | XC Hydra photon-counting (Direct Conversion AB), large-specimen / helical CT (DET-4) |

Families reused from the catalog: `Shutter`, `Mask`, `Monochromator`, `PseudoAxis`, `Slit`, `Filter`, `RotaryStage`, `LinearStage`, `Scintillator`, `Camera`. Loose family reused from siblings: `StorageRing` (machine-state supply). The bending-magnet `source` is a Supply (`PhotonBeam`), not an Asset. No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Every Tango / DonkiOrchestra control handle | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| The DCM energy bound (10-40 vs 9-40 keV) and Bragg / offset handles | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| The mono / white (pink) beam switch mechanism | `Monochromator` | `unknown-pending-confirmation` | (MODE-1) |
| The laminar-beam slit handles and beam dimensions | `BeamSlit` | `unknown-pending-confirmation` | (OPT-2) |
| The upstream white-beam-defining mask dimensions | `BeamDefiningMask` | `unknown-pending-confirmation` | (OPT-1) |
| The absorption / beam-hardening filter foils and selector | `Filter` | `unknown-pending-confirmation` | (FOIL-1) |
| The storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| The standard rotation stage (beyond the heavy rotator) | `Rotary` | `unknown-pending-confirmation` | (STAGE-1) |
| The five-axis sample-positioner motor vendors, resolution, axis map | `SampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| The propagation rail and detector rail handles | `PropagationRail` | `unknown-pending-confirmation` | (DET-2) |
| The routine scintillator screen type and thickness | `Scintillator` | `unknown-pending-confirmation` | (DET-3) |
| The default routine camera, pixel size, FOV | `TomographyCamera` / `CCDCamera` | `unknown-pending-confirmation` | (DET-1) |
| The XC Hydra photon-counting detector pixel size and configuration | `PhotonCountingCamera` | `unknown-pending-confirmation` | (DET-4) |
| The PSS permit signals and shutters | `FrontEndShutter`, enclosures | `unknown-pending-confirmation` | (PSS-1) |
