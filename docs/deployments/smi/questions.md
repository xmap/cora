# Open questions

*What CORA needs the SMI team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/smi-profile-collection`](https://github.com/NSLS2/smi-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector and in-situ-cell configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The in-vacuum undulator period, gap range, and harmonic usage. The device (`SR:C12-ID:G1{IVU:1}`) is confirmed; working gap range is about 6200-15100. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the front-end photon shutter (`XF:12IDA-PPS:2{PSh}`) is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-crystal monochromator energy range (the crystal is Si(111) per the source energy math, on bare motor records `XF:12ID:m65`-`m68`, driven by the coupled energy pseudopositioner). | One Monochromator Asset, Si(111) recorded, range blank. | The Monochromator settings. |
| CRL-1 | Blocks-go-live | The transfocator (`XF:12IDC-OP:2{Lens:CRL}`) lens material and count (twelve elements). The cross-deployment abstraction is resolved: the compound refractive lens reuses the graduated `Transfocator` catalog Family (a CRL focusing optic), bound at 4-ID, 8-ID, 9-ID, i22, and CHX too; only the per-Asset lens spec is still open. | The graduated `Transfocator` Family is bound; lens material and count blank. | The transfocator lens specification. |
| ENERGY-1 | Nice-to-have | Does SMI ever scan energy as the measurement, or is it always fixed-energy per experiment? | Fixed-energy; energy_scan not modelled. | The energy Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full HUB sample-stack axis set (x / y / z / theta / phi / chi) and the SmarAct piezo, and whether the grazing-incidence orientation axes warrant a `Goniometer` plus an Assembly. | A `LinearStage` sample stack, orientation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which Pilatus detectors are live (the SAXS 2M, the WAXS 900KW) versus the retired set (a 1M, a 300KW), and the SAXS camera-length range. | 2M (SAXS) and 900KW (WAXS) live; all Cameras; camera-length range blank. | The detector roster and Q-range. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live (the Linkam thermal / tensile stages, the LakeShore controller)? | One `TemperatureController` Asset (the Linkam); the others noted. | The sample-environment Assets. |
| INSITU-1 | Nice-to-have | The in-situ soft-matter cells: the humidity cell (driven via Moxa analog IO, no dedicated PV) and the blade coater (a SmarAct stage plus a syringe pump). How does CORA model these in-situ environments? | Deferred; they would need their own family / Procedure decisions when they land. | The in-situ cell Assets and Procedures. |
| VAC-1 | Nice-to-have | The WAXS / SAXS in-vacuum sample chamber (`Sample_Chamber`: pressure gauges, gate valves, a turbo pump, and pump / vent automation, used to set the in-vacuum vs in-air measurement mode). Does the active chamber enter CORA as a device, or stay a facility Supply? | Vacuum carried as a facility Supply (the i22 precedent); the active chamber deferred. | The vacuum-chamber Asset boundary. |
| DIAG-1 | Nice-to-have | The flux-monitor and beam-position channel maps, and the `BeamPositionMonitor` sensor fold-vs-promote hold shared across deployments. | Read-only flux (`FluxMonitor`) and beam-position (loose `BeamPositionMonitor`) probes; channel maps blank. | The FluxMonitor and BeamPositionMonitor bindings and the BPM promotion decision. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CAM-1 | Nice-to-have | Which beam-viewing cameras (the SAM / HEX sample cameras, the FOE FS / WBStop / VFM cameras) are live. | The on-axis SAM camera modelled; others noted. | The beam-viewing camera set. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs (SmarAct MCS, MDrive, Thorlabs are named). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the SAXS / WAXS / GISAXS Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i22 opened. Simultaneous SAXS+WAXS would be coordinated Runs, not a new technique. | Capabilities deferred (rendered unlinked), no Practice recorded. | The scattering Capability scope. |
