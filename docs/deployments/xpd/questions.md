# Open questions

*What CORA needs the XPD team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/xpd-profile-collection`](https://github.com/NSLS2/xpd-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the source and endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The source: 28-ID is a damping-wiggler beamline, but no source PV or parameters are in the profile collection. | An insertion-device (damping wiggler), identity-only, no PV. | The Source Asset PV and settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the endstation exposure shutter (`XF:28IDC-ES:1{Sh:Exp}`) is in source, not the front-end PPS leaves. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENDSTATION-1 | Nice-to-have | The high-resolution channel: the high-resolution monochromator (`Mono:HRM`, in the 28-ID-C hutch) and the downstream high-resolution endstation (28-ID-D) with its own sample stack (the `Stg:Stack` fine axes) and a third flat panel (`Det:PE3`). | The main PDF channel (DLM mono + 28-ID-C endstation) is modelled; the high-resolution channel is noted, deferred. | The HRM and 28-ID-D Assets. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-Laue monochromator crystal and energy range, and the high-resolution monochromator crystal. Both (`Mono:DLM`, `Mono:HRM`) are in source. | Two Monochromator Assets, settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Does XPD ever scan energy as the measurement, or is it always fixed-energy per experiment? | Fixed-energy; energy_scan not modelled. | The energy Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full diffractometer axis set behind `Dif:1`, and whether the goniometric axes warrant a `Goniometer` plus a Diffractometer Assembly (the 8-ID / i11 precedent). | A `LinearStage` sample stack, rotation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which flat panels are live (PerkinElmer pe1 / pe2, Dexela, the 28-ID-D pe3) vs the spare set, and the detector distance range. | pe1 primary, Dexela secondary; all Cameras; distance range blank. | The detector roster and Q-range. |
| TEMP-1 | Nice-to-have | Which sample-environment units are live (Cryostream cs700 / cs800, Eurotherm, hot-air blower, Lakeshore cryostat, Linkam furnace)? | One `TemperatureController` Asset (the Cryostream); the others noted. | The sample-environment Assets. |
| DIAG-1 | Nice-to-have | The ion-chamber and quad-electrometer channel map (which channel is I0), and the `BeamPositionMonitor` sensor fold-vs-promote hold shared across deployments. | Read-only flux counters (`FluxMonitor`), BPM loose; channel map blank. | The IonChamber / QuadElectrometer bindings and the BPM promotion decision. |
| CALIB-1 | Nice-to-have | The energy / wavelength calibration: the calibration diffractometer (`Dif:2`: `th_cal`, `tth_cal`, `ecal_x`, `ecal_y`) and the Ecal routine that scans a standard to fit the beam wavelength, plus the dormant multi-analyzer stage (`MAD:DMS`) and the mono beam-defining slits (`Slt:MB1` / `Slt:MB2`). | A Procedure over the spine; these support devices deferred at this design phase. | The calibration Procedure and its devices. |
| OPERANDO-1 | Nice-to-have | The in-situ / operando accessories: the QEPro UV-Vis spectrometer read in parallel with the diffraction pattern (a distinct optical-spectroscopy modality, not a `Camera`), the gas switcher (`Env:02`), and the flash-sintering / electrochemistry power system. | Deferred; the UV-Vis channel needs its own family decision when it lands. | The operando detector and sample-environment Assets. |
| ROBOT-1 | Nice-to-have | The sample-changing robot (`XF:28IDC-ES:1{SM}`): CORA would model autonomous powder / capillary exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the I03 MX loop and the I15-1 powder exchange. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-handling Procedure and Subject custody thread. |

## Controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the powder-diffraction and total-scattering / PDF Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i11 and i15-1 opened. | Capabilities deferred (rendered unlinked), no Practice recorded. | The powder / PDF Capability scope. |
