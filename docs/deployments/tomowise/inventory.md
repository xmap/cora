# Inventory

*The CORA Asset model for TomoWISE: the planned device tree and what still needs confirming.*

TomoWISE is in the design phase, so this is the planned Asset shape, not a registered inventory. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [endstation](equipment/endstations.md) and [detector](equipment/detector.md) pages. The shape is generated-honest: it is authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tomowise/beamline.yaml) descriptor that the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md). Only one vendor Model is bound: the Optique Peter microscope optics (`optique_peter_micrx080`, reused from 2-BM, pending confirmation); the remaining "(target)" models named in the TDR are carried as open questions, not bindings, because part numbers are not yet procured. Control handles are omitted because MAX IV runs Tango/Sardana and the names are not yet assigned.

## The Asset tree

Root Asset `TomoWISE` (`tier = Unit`, `facility_code = maxiv`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Design spec (TDR) |
| --- | --- | --- | --- |
| `TomoWISE` | `Unit` | (root) | bound to the MAX IV Site |
| `CPMU14` | `Device` | InsertionDevice | cryo-undulator, 14 mm period, 3.8 mm min gap, 11.1 kW |
| `3T3PW` | `Device` | InsertionDevice | three-pole wiggler, 3 T, 1.6 kW |
| `FM1` / `FM2` | `Device` | Mask | fixed masks, 1.1 mrad apertures |
| `MSM` | `Device` | Mask | movable safety mask |
| `HeatAbsorber` | `Device` | HeatAbsorber | 4 kW budget; front-end, protects the safety shutter |
| `CVD` | `Device` | Filter | 0.35 mm CVD diamond |
| `PFU` | `Device` | Filter | two Si wedges, 0.2 to 25 mm effective |
| `MLM` | `Device` | Monochromator | 20 to 65 keV, dE/E ~ 1.8% |
| `MF` | `Device` | Filter | metal filter, transmission 1e-4 to 1 |
| `WhiteBeamSlit` / `MonochromaticBeamSlit` | `Device` | Slit | beam-defining slits |
| `SS1` / `SS2` | `Device` | Shutter | safety shutters (SU) |
| `SampleTable` | `Component` | Table | micro endstation, ~45 m, fixed |
| `Rotary` | `Device` | RotaryStage | 1200 rpm, TTL 3600 pulses/rev |
| `SamplePositioning` | `Device` | LinearStage | Xs/Zs, +/-6 mm, 0.1 um |
| `LaminographyTilt` | `Device` | TiltStage | 25 deg travel |
| `SampleSlit` | `Device` | Slit | 50 x 5 mm |
| `FastShutter` | `Device` | Shutter | <5 ms / <10 ms reference designs |
| `SlipRing` | `Device` | SlipRing | 30 to 40 channels, up to 1000 rpm |
| `KB` | `Device` | Mirror | KB pair, 205 x 196 nm focus @ 30 keV |
| `NanoGranite` | `Component` | Table | granite support for the nano manipulator |
| `NanoTilt` | `Device` | TiltStage | Tilt X, 2 deg, target Huber 5202.80 |
| `NanoCoarseX` / `NanoCoarseY` | `Device` | LinearStage | Xt/Yt coarse, target Huber 5101.20 / 5103.A20-90 |
| `NanoCoarseZ` | `Device` | LinearStage | Zt long-travel (250-300 mm), target Zaber X-LDQ-AE |
| `NanoRotary` | `Device` | RotaryStage | Rot y, continuous, Abbe < 100 nm, target RT100AS |
| `NanoSamplePositioning` | `Device` | LinearStage | Xs/Zs centring, +/-6 mm, target XY150B-12 |
| `DetectorGantry` | `Component` | Table | 7 m floor rails, 45 to 52 m (the shared propagation rail) |
| `MicLFOV` / `MicHR` | `Component` | Housing | Microscope Assemblies; Housing model `optique_peter_micrx080` |
| `MicLFOV` / `MicHR` constituents | `Device` | LinearStage / Objective / PseudoAxis / Scintillator | turret + objectives (1-2x / 4-20x) + selector + scintillator |
| `CameraI` ... `CameraIV` | `Device` | Camera | 16-25 / 4 / 4 / 150 Mpix; shared across both microscopes |

`Mask` is now a shared catalog Family (earned in once both 2-BM and TomoWISE used it). The two microscopes compose the shared `Microscope` / `Optics` catalog Assemblies (Housing-anchored), so there is no loose `Microscope` family any more. The remaining families not yet in the catalog (`HeatAbsorber`, `SlipRing`) are bound loosely by design intent; they are earned into the catalog when a confirmed device needs them (the beam-path stop tier is tracked below). The nano manipulator reuses the same `TiltStage`, `LinearStage`, `RotaryStage`, and `Table` Families as the micro endstation, so it needs no nano-specific Family.

## Pending confirmations

Every value below is a TDR design specification awaiting the beamline team. Each is tracked by an [open question](questions.md); the answer lands in the descriptor and the row is removed.

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Control handles (Tango/Sardana device/attribute names) | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Nanotomography stage model bindings (TDR Table 9.5 names a target per axis) | the nano `*` stages | `unknown-pending-confirmation` | (NANO-1) |
| Rotary stage model (RT100AX target) | `Rotary` | `unknown-pending-confirmation` | (STAGE-1) |
| Sample positioning model (XY150B-12 target) | `SamplePositioning` | `unknown-pending-confirmation` | (STAGE-2) |
| Camera models I to IV | `CameraI`..`CameraIV` | `unknown-pending-confirmation` | (DET-1) |
| Microscope optics model (Optique Peter `optique_peter_micrx080` bound, from 2-BM) | `MicLFOV`, `MicHR` | bound, pending confirmation | (DET-2) |
| Trigger conditioner (direct TTL vs FPGA) | `Triggering` | `unknown-pending-confirmation` | (TRIG-1) |
| MLM coating (W/SiC vs W/B4C per TDR text; Table 8.3 lists W/Si) | `MLM` | `unknown-pending-confirmation` | (OPT-1) |
| Layout z reference (source vs straight-section centre) | all devices | `unknown-pending-confirmation` | (LAYOUT-1) |
