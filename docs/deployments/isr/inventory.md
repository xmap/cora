# Inventory

*The CORA Asset model for the operational core of ISR modelled today: the planned device tree and what still needs confirming. A deliberately partial cut.*

This cut models the XF:04ID optics chain and the partial XF:04IDD-ES endstation; the multi-circle diffractometer, the in-situ sample environment, the resonant energy axis, the polarization analysis, and the commented-out flux monitors are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/isr/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. ISR coins **no new Family and changes nothing in the catalog**: the optics reuse the existing `InsertionDevice` / `Monochromator` / `Mirror` / `Slit` / `Filter` vocabulary, the endstation reuses `RotaryStage` / `Camera`, and the beam-position monitor reuses the loose `BeamPositionMonitor`. The devices ISR's mission implies are absent from the source and are open questions, not Assets. Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `ISR` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `ISR` | `Unit` | (root) | - | bound to the NSLS-II Site; 4-ID |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring current, observe-only, `SR:OPS-BI{DCCT:1}` (MACHINE-1) |
| `Undulator` | `Device` | InsertionDevice | isr-optics | in-vacuum undulator, read-only gap, `SR:C04-ID:G1{IVU:1}` (SRC-1) |
| `Monochromator` | `Device` | Monochromator | isr-optics | double-crystal monochromator (DCM), `XF:04IDA-OP:1{Mono:DCM}` (MONO-1) |
| `FocusingMirror` | `Device` | Mirror | isr-optics | bendable HFM + VFM focusing pair, `XF:04IDA-OP:1{Mir:HFM/VFM}` (OPT-1) |
| `HarmonicRejectionMirror` | `Device` | Mirror | isr-optics | harmonic-rejection mirror (DHRM), `XF:04IDB-OP:1{Mir:DHRM}` (OPT-1) |
| `FrontEndSlit` | `Device` | Slit | isr-optics | front-end defining slit, `FE:C04A-OP{Slt:12}` (OPT-2) |
| `AttenuatorBank` | `Device` | Filter | isr-endstation | four-foil pneumatic attenuator, `XF:04IDD-ES{Fil:1-4}` (ATTN-1) |
| `SampleStage` | `Device` | RotaryStage | isr-endstation | the two bound Dif:ISD axes (`th` + `zeta`); the full diffractometer is absent (DIFF-1) |
| `AreaDetector` | `Device` | Camera | isr-endstation | Eiger 1M, the primary scattering detector, `XF:04IDD-ES{Det:Eig1M}` (DET-1) |
| `DiagnosticCamera` | `Device` | Camera | isr-endstation | Prosilica YAG-screen beam-viewing cameras, `XF:04IDC-BI:1{Scr:3}` (DIAG-1) |
| `BeamPositionMonitor` | `Device` | BeamPositionMonitor (loose) | isr-optics | motorized BPM stage (electrometers commented out), `XF:04IDB-BI:1{BPM:3}` (DIAG-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `Filter`, `RotaryStage`, `Camera`. Loose families reused from siblings: `StorageRing` (supply), `BeamPositionMonitor` (held under review, DIAG-1). No new family is coined and nothing graduates.

## Deliberately absent from this cut

These devices give ISR its name but are not in the public source, so they are open questions, not Assets:

- the multi-circle **diffractometer** (orientation circles, detector two-theta arm, reciprocal-space engine) (`DIFF-1`);
- the **in-situ sample environment** (electrochemistry, gas, temperature, cryostat) (`INSITU-1`);
- a wired **resonant energy axis** and **polarization analysis** (`RESONANT-1`);
- the **flux-monitor electrometers** (defined but commented out) (`DET-1`).

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-endstation hutch grouping | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator model and energy range | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) and data plane | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| DCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and bend | `FocusingMirror`, `HarmonicRejectionMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Front-end slit map and the commented-out SSA slit | `FrontEndSlit` | `unknown-pending-confirmation` | (OPT-2) |
| Attenuator bank calibration | `AttenuatorBank` | `unknown-pending-confirmation` | (ATTN-1) |
| The multi-circle diffractometer | `SampleStage` | `unknown-pending-confirmation` | (DIFF-1) |
| The in-situ sample environment | the sample | `unknown-pending-confirmation` | (INSITU-1) |
| The resonant energy axis and polarization | the optics / sample | `unknown-pending-confirmation` | (RESONANT-1) |
| Eiger model, write path, and the commented-out flux monitors | `AreaDetector` | `unknown-pending-confirmation` | (DET-1) |
| BPM electrometers and position-vs-intensity split | `BeamPositionMonitor`, `DiagnosticCamera` | `unknown-pending-confirmation` | (DIAG-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
