# Extracted facts: IMBL

Candidate device facts for `imbl` (Australian Synchrotron IMBL, Imaging and Medical Beam Line: large-field imaging, micro-CT, and Microbeam Radiation Therapy / MRT). Candidates only; confirm every row before modeling. Source: the public `AustralianSynchrotron/imbl` controls repo (C++ Qt beamline-control application, read 2026-07). Every value is carried `confirm` until IMBL staff verify it: the controls source is strong evidence, not a CORA-owned fact.

!!! note "Source idiom: C++ Qt control, not a Python profile"
    Unlike the bluesky / ophyd / dodal profiles mined elsewhere, IMBL's public source is a **C++ Qt control application** (`qimbl` over `qtpv`/`QEpicsPv`/`QCaMotor`). Device PVs are built from a per-subsystem `pvBaseName` + literal axis suffix, read verbatim from the `*.cpp` sources. The facility is the Australian Synchrotron (SPEAR-style `SR08ID01` prefix = storage ring, sector 08, insertion-device beamline 01). IMBL is a wiggler beamline (very large beam for medical imaging + MRT). Repo last pushed 2021; carry everything `confirm`.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix (verbatim from source), C++ class / subsystem as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix (verbatim) | Axes / detail | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| InsertionDevice | InsertionDevice | `SR08ID01:GAP_MONITOR` | superconducting wiggler gap | source | yes |
| Monochromator | Monochromator | `SR08ID01DCM01:` | bent-Laue DCM: BRAGG1/2, X, Z1/Z2, TILT1/2, BENDER1IB/OB, BENDER2IB/OB; encoders BRAGG1/2:ENCODER, X:ENCODER | source | yes |
| Filters | Filter | `SR08ID01FR01:` | filter paddles (PDL0...) | source | yes |
| MRTShutter | Shutter | `SR08ID01MRT01:` | Microbeam Radiation Therapy fast shutter: CYCLEPERIOD, EXPOSUREPERIOD, EXPOSUREINPROGRESS, PSSENABLE | source | yes |
| FrontEndShutter | Shutter | `SR08ID01PSS01:FES...` (FES_EPS, via PSS) | front-end shutter (PSS-interlocked) | source | yes |
| Shutter1A | Shutter (?) | (shutter1A subsystem; base via PSS/EPS) | 1A photon shutter | source | yes |
| Valves | GenericProbe (?) | `SR08ID01EPS01:IGV%1_OpenCloseCmd` / `IGV%1_STS` | EPS isolation/gate valves (vacuum) | source | yes |
| PSS | SafetyStack (?) | `SR08ID01PSS01:` | personnel safety: BL_ENABLE/DISABLE_STS, FES_EPS_ENABLE/DISABLE_STS | source | yes |

Device-level prefixes read verbatim from source: `Mono::pvBaseName = "SR08ID01DCM01:"` with `QCaMotor(pvBaseName + "BRAGG1" / "BRAGG2" / "X" / "Z1" / "Z2" / "TILT1" / "TILT2" / "BENDER1IB" / "BENDER1OB" / "BENDER2IB" / "BENDER2OB")`; `filters pvBaseName = "SR08ID01FR01:PDL0"`; `mrtShutter pvBaseName = "SR08ID01MRT01:"`; valve `"SR08ID01EPS01:IGV%1_OpenCloseCmd"`; `"SR08ID01:GAP_MONITOR"` (wiggler); `"SR08ID01PSS01:BL_ENABLE_STS"` (PSS).

## Role hints

- **Source**: superconducting wiggler (gap monitor); IMBL's large-field source for medical imaging.
- **Positioner**: the bent-Laue DCM is a rich monochromator with two Bragg crystals, four bender axes (IB/OB per crystal, for the bent-Laue geometry), two tilts, X translation, Z1/Z2; all `QCaMotor`.
- **Shutter**: the MRT fast shutter (the defining device, chops the beam into microbeams for radiation therapy), the front-end shutter, the 1A shutter.
- **Filter**: the filter paddle assembly.
- **Safety / utility**: PSS (personnel safety system), EPS isolation/gate valves.

## Trust hints

C++ Qt control application; no queue-server / bluesky permission model. The PSS (`SR08ID01PSS01:`) is the personnel-safety interlock layer, the floor CORA's safety BC models around (the Clearance / Enclosure permit pattern), not a CORA-owned device. No data-catalog evidence in this repo.

## New-family watch

No new coining. Notes:
- **Monochromator** (graduated): the bent-Laue DCM is a Monochromator variant (Laue rather than Bragg-flat, with bender axes for the bent-crystal geometry); bind Monochromator. The four bender axes are components of the one mono Asset, not separate devices.
- **MRTShutter -> Shutter** (graduated): the MRT fast shutter is a Shutter with timing parameters (CYCLEPERIOD/EXPOSUREPERIOD). It is functionally close to a TimingController (it gates exposure in cycles), confirm whether it binds Shutter or TimingController, IMBL's distinctive device.
- **Filters -> Filter**, **InsertionDevice** (catalog): bind directly.
- **Valves / PSS -> GenericProbe / SafetyStack (loose)**: the EPS valves and PSS are utility/safety; PSS maps to CORA's safety-BC seam (Enclosure permit), not a device Family.

## Deferred / absent

- **DET-1**: the imaging detectors (IMBL runs large-area flat panels / the "Ruby" + Hamamatsu detectors and a CT stage) are NOT in this controls repo, which is the optics/shutter/safety front end; the detector + sample/CT stage are open questions (the `imblScripts` / `imblproc` repos cover CT *processing*, not device control).
- **SAMPLE-1**: the sample-manipulation / CT rotation stage and the medical-imaging patient/sample positioning are not in this repo.
- **HUTCH-1**: the `hutch` subsystem was present but no distinct device PVs were isolated in this pass; confirm.
- The FE / 1A shutter exact PVs are built through the PSS/EPS layer; recorded at subsystem level, confirm the precise handles with staff.
- IMBL has multiple hutches (1A, 2A/2B, 3A/3B over a ~140 m beamline incl. a satellite building); the enclosure topology is a staff question.
