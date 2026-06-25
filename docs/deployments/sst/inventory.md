# Inventory

*The CORA Asset model for the operational core of SST modelled today: the planned device tree across both branches and what still needs confirming.*

This cut models the shared front end, the SST-1 soft branch + RSoXS endstation, and the SST-2 tender branch + HAXPES endstation; the UCAL TES microcalorimeter and the VPPEM microscope are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/sst/beamline.yaml) descriptor.

Every device binds an existing catalog [Family](../../catalog/families.md): SST reuses `GratingMonochromator` (soft, its 4th), `Monochromator` (tender Si DCM), and `Manipulator` (its 3rd / 4th), and **graduates** `ElectronAnalyzer` (the HAXPES Scienta SES, the 2nd after ESM). Control handles are filled from the config-driven profile; no vendor Models are bound.

## The Asset tree

Root Asset `SST` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `SST` | `Unit` | (root) | - | bound to the NSLS-II Site; soft + tender, two branches |
| `Undulator_Soft` | `Device` | InsertionDevice | 7-ID-A | EPU60 feeding SST-1 soft (SRC-1) |
| `Undulator_Tender` | `Device` | InsertionDevice | 7-ID-A | U42 feeding SST-2 tender (SRC-1) |
| `Mirror_1` | `Device` | Mirror | 7-ID-A | shared FOE FMB hexapod mirror (OPT-1) |
| `FrontEndSlit` | `Device` | Slit | 7-ID-A | FOE quad slit (OPT-2) |
| `FrontEndShutter` / `PhotonShutter` | `Device` | Shutter | 7-ID-A | front-end + photon shutters |
| `Monochromator_Soft` | `Device` | GratingMonochromator | SST-1 | plane-grating mono, 71-2250 eV (MONO-1) |
| `Monochromator_Tender` | `Device` | Monochromator | SST-2 | Si double-crystal mono (MONO-1) |
| `Mirror_L1` / `Mirror_L2AB` | `Device` | Mirror | SST-2 | tender FMB hexapod mirrors (OPT-1) |
| `RSoXSManipulator` | `Device` | Manipulator | SST-1 | RSoXS UHV manipulator x/y/z/yaw (SAMPLE-1) |
| `HAXPESManipulator` | `Device` | Manipulator | SST-2 | HAXPES UHV manipulator x/y/z/theta (SAMPLE-1) |
| `HAXPESSlit` | `Device` | Slit | SST-2 | HAXPES analyzed-spot quad slit (OPT-2) |
| `WAXSDetector` | `Device` | Camera | SST-1 | Greateyes GE 4k4k WAXS CCD (DET-1) |
| `AuMeshMonitor` / `IzeroPhotodiode` | `Device` | FluxMonitor | SST-1 | RSoXS I0 monitors (DET-1) |
| `ElectronAnalyzer` | `Device` | ElectronAnalyzer | SST-2 | Scienta SES; graduates the Family (PES-1) |
| `IonChamber` | `Device` | FluxMonitor | SST-2 | I400 ion-chamber channel (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `Slit`, `Shutter`, `GratingMonochromator`, `Monochromator`, `Manipulator`, `Camera`, `FluxMonitor`. Graduated with this deployment: `ElectronAnalyzer` (the HAXPES Scienta SES, the 2nd after ESM). SST introduces **no loose family of its own**.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| EPU types, periods, polarization, dual-EPU coupling | `Undulator_Soft/Tender` | `unknown-pending-confirmation` | (SRC-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Control handles (config-driven PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Soft PGM grating set + tender DCM crystal/range | the monochromators | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | `Mirror_1`, `Mirror_L1/L2AB` | `unknown-pending-confirmation` | (OPT-1) |
| Slit axis maps | `FrontEndSlit`, `HAXPESSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Manipulator axes + UHV / cryo spec | `RSoXSManipulator`, `HAXPESManipulator` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Scienta SES analyzer model + lens / pass-energy controls | `ElectronAnalyzer` | `unknown-pending-confirmation` | (PES-1) |
| Detector models + ion-chamber channel set | `WAXSDetector`, `IonChamber`, the flux monitors | `unknown-pending-confirmation` | (DET-1) |
