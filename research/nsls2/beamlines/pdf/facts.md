# Extracted facts: PDF (28-ID)

Candidate device facts for `pdf` (NSLS-II 28-ID, high-energy powder diffraction and total scattering / pair distribution function). Candidates only; confirm every row before modeling. Source: the public `NSLS2/pdf-profile-collection` (`startup/*.py`, read 2026-06; modules `10-machine`, `11-motors`, `12-optics`, `13-gas_handling`, `14-lakeshore_cryostat`, `15-cs800crystream`, `16-eurotherm_HAB`, `17-linkam`, `20-prosilica`, `72-two-detector`, `80-areadetector2`, `81-pilatus`). Every value is carried `confirm` until PDF staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Rich in-situ sample environment"
    PDF's signature for total-scattering is a deep in-situ sample-environment stack: Lakeshore 336 cryostat, Oxford CS800 cryostream, Eurotherm furnace, two Linkam stages, gas handling (RGA, NOx, OCM), and humidity. These are settable-setpoint thermal/flow actuators (the Regulator family lineage) and are the densest temperature-controller set in the NSLS-II fleet so far.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| ExperimentShutter | Shutter | `XF:28IDC-ES:1{Sh:Exp}` | Cmd-Cmd (exposure shutter) | 28-ID-C | source | yes |
| FastShutter | Shutter | `XF:28IDC-ES:1{Sh2:Exp-Ax:` | motorized fast shutter | 28-ID-C | source | yes |
| Monochromator | Monochromator | `XF:28ID1A-OP{Mono:SBM-Ax:` | sagittal bent mono axes | 28-ID-1-A | source | yes |
| VerticalFocusingMirror | Mirror | `XF:28ID1A-OP{Mir:VFM-Ax:` | VFM jack/bend axes | 28-ID-1-A | source | yes |
| WhiteBeamSlit0 | Slit | `XF:28ID1A-OP{Slt:0-Ax:` | blade axes | 28-ID-1-A | source | yes |
| WhiteBeamSlit1 | Slit | `XF:28ID1A-OP{Slt:1-Ax:` | blade axes | 28-ID-1-A | source | yes |
| EndstationSlit2 | Slit | `XF:28ID1B-OP{Slt:2-Ax:` | blade axes | 28-ID-1-B | source | yes |
| AntiScatterSlit | Slit | `XF:28ID1B-OP{Slt:AS-Ax:` | anti-scatter slit | 28-ID-1-B | source | yes |
| Filter | Filter | `XF:28ID1B-OP{Fltr:` | filter/attenuator | 28-ID-1-B | source | yes |
| SampleStage | LinearStage | `XF:28ID1B-ES{Stg:Smpl-Ax:` | x/y/z/ry | 28-ID-1-B | sample | yes |
| SampleTable | Table | `XF:28ID1B-ES:1{Sample:Tbl-Ax:` | y1 + table axes | 28-ID-1-B | sample | yes |
| SampleChanger | Positioner (?) | `XF:28ID1B-ES{Smpl:Chngr-Ax:` | yrot (robot/changer) | 28-ID-1-B | sample | yes |
| SampleArray | LinearStage | `XF:28ID1B-ES{Smpl:Array-Ax:` | horiz (multi-sample array) | 28-ID-1-B | sample | yes |
| DetectorStage1 | LinearStage | `XF:28ID1B-ES{Det:1-Ax:` | x/y | 28-ID-1-B | detection | yes |
| DetectorStage2 | LinearStage | `XF:28ID1B-ES{Det:2-Ax:` | x/y | 28-ID-1-B | detection | yes |
| BeamStop1 | BeamStop | `XF:28ID1B-ES{BS:1-Ax:` | beamstop axes | 28-ID-1-B | detection | yes |
| BeamStop2 | BeamStop | `XF:28ID1B-ES{BS:2-Ax:` | beamstop axes | 28-ID-1-B | detection | yes |
| PerkinElmer1 | Camera | `XF:28ID1-ES{Det:PE1}` | Perkin-Elmer flat-panel (powder) | 28-ID-1 | detection | yes |
| PerkinElmer2 | Camera | `XF:28ID1-ES{Det:PE2}` | second Perkin-Elmer | 28-ID-1 | detection | yes |
| PilatusDetector | Camera | `XF:28ID1-ES{Det:Pilatus}` | Pilatus (energy/threshold settable) | 28-ID-1 | detection | yes |
| IonMonitor | FluxMonitor | `XF:28IDC-BI:1{IM:1}` | ion monitor currents (C4 channels) | 28-ID-C | detection | yes |
| LakeshoreCryostat | TemperatureController | `XF:28ID1-ES{LS336:1` | LS336 loops; Out:3 Man-SP/Man-RB | 28-ID-1 | sample | yes |
| LinkamStage | TemperatureController | `XF:28ID1-ES{LINKAM:T96}:` | T96 controller setpoint/ramp | 28-ID-1 | sample | yes |
| EurothermFurnace | TemperatureController | `XF:28ID1-ES{ET:05}LOOP1:` | Eurotherm HAB furnace loop | 28-ID-1 | sample | yes |
| EnvController1 | TemperatureController (?) | `XF:28ID1-ES:1{Env:01}` | environment controller | 28-ID-1 | sample | yes |
| EnvController5 | TemperatureController (?) | `XF:28ID1-ES:1{Env:05}LOOP1:` | environment controller loop | 28-ID-1 | sample | yes |
| ResidualGasAnalyzer | GenericProbe (?) | `XF:28ID1-ES{RGA:1}` | residual gas analyzer | 28-ID-1 | sample | yes |
| WebCam | GenericProbe (?) | `XF:28ID1-BI{Cam:2}` | sample-viewing camera | 28-ID-1 | sample | yes |

Device-level prefixes read verbatim from source (`Mono:SBM`, `Mir:VFM`, the PE1/PE2/Pilatus detectors, the `LS336`/`LINKAM:T96`/`ET:05`/`Env:01`/`Env:05` controller blocks, the sample changer/array/stage).

## Role hints

- **Positioner**: mono, VFM, all slits, sample stage/table/changer/array, detector stages, beamstops.
- **Sensor**: ion monitor (flux), RGA, webcam.
- **Detector**: PE1, PE2, Pilatus (all area detectors for powder rings).
- **Regulator (dense)**: Lakeshore LS336 (Out:3 Man-SP setpoint), Linkam T96, Eurotherm ET:05 (LOOP1), Env:01/05 (LOOP1) are all settable-setpoint thermal actuators, the TemperatureController/Regulator signature. This is the strongest Regulator-consumer cluster in the fleet.

## Trust hints

`startup/user_group_permissions.yaml` present (xpdacq-patched); queue-server orchestration, the layer CORA would replace. PDF runs the `xpdacq` acquisition layer on top of bluesky, a beamline-specific orchestration to note at the seam.

## New-family watch

No new coining. The signal here is strong reinforcement of the Regulator lineage:
- **LakeshoreCryostat / LinkamStage / EurothermFurnace -> TemperatureController** (graduated, presents Regulator): PDF gives the graduated TemperatureController family THREE more distinct-mechanism consumers (Lakeshore, Linkam, Eurotherm) on one beamline. Bind directly; this is the canonical multi-mechanism Regulator deployment. Confirm Env:01/05 also present Regulator (vs read-only).
- **SampleChanger -> Positioner (?)**: per the established pattern (i03/19-BM/32-ID), a robot/changer folds to Positioner + Clearance + Subject custody, NOT a new SampleChanger Family. Confirm.
- **IonMonitor -> FluxMonitor** (graduated): another consumer.
- **PerkinElmer x2 + Pilatus -> Camera**: powder area detectors; bind directly.

## Deferred / absent

- **Gas handling** (`13-gas_handling.py` RGA/NOx/OCM), **humidity** (`26-humidity.py`), and the second `27-linkam.py` are partly mapped; the gas/flow devices may include FlowController candidates, read before a deployment scaffold (`FLOW-1`).
- **CS800 cryostream** (`15-cs800crystream.py`) is in source but its exact PV root was not isolated in this pass; it is another TemperatureController consumer, confirm root (`TEMP-2`).
- The **insertion-device source** referenced via `10-machine.py`; no standalone InsertionDevice instantiated; carry `SRC-1`.
