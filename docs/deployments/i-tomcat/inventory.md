# Inventory

*The CORA Asset model for I-TOMCAT: the planned device tree and what still needs confirming.*

I-TOMCAT is a modelling exercise, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i-tomcat/beamline.yaml) descriptor that the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md). No vendor Model is bound: the part numbers read from PSI's public pages (Aerotech ABRX150, the pco.edge / pco.dimax cameras, the PSI GigaFRoST) are carried as "(target)" pending confirmation, not bindings. Control handles are omitted because the SLS EPICS PV prefix for TOMCAT is not public and the BEC ophyd device manifest is internal.

## The Asset tree

Root Asset `I-TOMCAT` (`tier = Unit`, `facility_code = psi`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Design spec (public pages / design reports) |
| --- | --- | --- | --- |
| `I-TOMCAT` | `Unit` | (root) | bound to the PSI Site (SLS storage ring); sector `X02SA` |
| `StorageRing` | `Device` | StorageRing | SLS 2.0 ring state; observe-only |
| `Undulator` | `Device` | InsertionDevice | U15 undulator (planned HTSU10 upgrade 2027) |
| `Monochromator` | `Device` | Monochromator | fixed-exit DCMM, 8-50 keV (8-30 keV recommended); legacy multilayer + Si(111) |
| `DiamondWindow` | `Device` | Window | 100 um CVD diamond (legacy spec) |
| `BeamFilter` | `Device` | Filter | filter batteries (legacy: 10 um Cu to 400 um Al) |
| `FocusingMirror` | `Device` | Mirror | hard X-ray focusing / harmonic-rejection mirror(s) |
| `BeamSlit` | `Device` | Slit | beam-defining slits ahead of the endstation |
| `SafetyShutter` | `Device` | Shutter | optics-to-experiment safety shutter |
| `Rotary` | `Device` | RotaryStage | air-bearing rotation at ES2 (~33 m), ~1500 deg/s; trigger master clock; target Aerotech ABRX150 |
| `SamplePositioning` | `Device` | LinearStage | sample centring / translation on the rotation stage |
| `SlipRing` | `Device` | SlipRing | continuous-rotation feedthrough for endless acquisition |
| `FastShutter` | `Device` | Shutter | sample-side fast shutter, dose limiting |
| `Microscope` | `Component` | Housing | visible-light microscope, 1x-40x (six optical, legacy) |
| `Microscope` constituents | `Device` | Objective / Scintillator | interchangeable objectives over an LSO:Tb / LuAG:Ce scintillator |
| `HighSpeedCamera` | `Device` | Camera | 2016x2016, 11 um, up to 1255 fps; target pco.dimax |
| `StreamingCamera` | `Device` | Camera | GigaFRoST (PSI in-house), continuous ~8 GB/s streaming |
| `ScienceCamera` | `Device` | Camera | general-throughput sCMOS; target pco.edge family |
| `Triggering` | (controls) | TimingController | rotary-master trigger / sync scheme |

No new catalog Family is earned: every device reuses an existing Family or an allowlisted loose family (`StorageRing`, `SlipRing`). The microscope is carried as a `Housing` with `Objective` and `Scintillator` constituents pending confirmation of whether it composes the cross-facility `Microscope` Assembly the way 2-BM does (DET-2).

## Pending confirmations

Every value below is read from PSI's public pages or a design report and awaits the beamline team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The U15 undulator period / gap range, and the HTSU10 upgrade timing | `Undulator` | `unknown-pending-confirmation` (SRC-1) | (SRC-1) |
| Storage-ring state handles (current, fill) | `StorageRing` | `unknown-pending-confirmation` (MACHINE-1) | (MACHINE-1) |
| The rebuilt-beamline monochromator optics (legacy DCMM specs may not hold) | `Monochromator`, `DiamondWindow`, `BeamFilter` | `unknown-pending-confirmation` (MONO-1) | (MONO-1) |
| The focusing mirror coatings and handles (not on the public pages) | `FocusingMirror` | `unknown-pending-confirmation` (OPT-1) | (OPT-1) |
| The beam-defining slit blade-axis map and handles | `BeamSlit` | `unknown-pending-confirmation` (OPT-2) | (OPT-2) |
| Hutch PSS permit signals and interlock names | both enclosures | `unknown-pending-confirmation` (PSS-1) | (PSS-1) |
| The hutch grouping and the X02SA code reassignment to the rebuilt I-TOMCAT | both enclosures | `unknown-pending-confirmation` (ENC-1) | (ENC-1) |
| The rotation stage model (Aerotech ABRX150 target) and its specs | `Rotary` | `unknown-pending-confirmation` (STAGE-1) | (STAGE-1) |
| The sample positioning / slip-ring axis set and handles | `SamplePositioning`, `SlipRing`, `FastShutter` | `unknown-pending-confirmation` (SAMPLE-1) | (SAMPLE-1) |
| The camera models I to III (pco.edge family, pco.dimax, GigaFRoST) | `HighSpeedCamera`, `StreamingCamera`, `ScienceCamera` | `unknown-pending-confirmation` (DET-1) | (DET-1) |
| The microscope optics model and the `Microscope` Assembly composition | `Microscope` | `unknown-pending-confirmation` (DET-2) | (DET-2) |
| The trigger / sync hardware (rotary TTL vs a conditioner) | `Triggering` | `unknown-pending-confirmation` (TRIG-1) | (TRIG-1) |
| The EPICS PV prefix scheme and BEC ophyd device handles | all devices | `unknown-pending-confirmation` (CTRL-1) | (CTRL-1) |
| The BEC replace-vs-drive-through seam boundary | controls | `unknown-pending-confirmation` (SEAM-1) | (SEAM-1) |
| Which tomography Practices the rebuilt beamline offers (e.g. grating interferometry) | techniques | `unknown-pending-confirmation` (TECH-1) | (TECH-1) |
