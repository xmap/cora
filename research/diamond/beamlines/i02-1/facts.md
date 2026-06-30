# Extracted facts: I02-1 (VMXm)

Candidate device facts for `i02-1` (Diamond Light Source I02-1, also known as VMXm / I02J: versatile macromolecular crystallography, microfocus). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/i02_1.py`, read 2026-06). Every value is carried `confirm` until VMXm staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "VMXm = I02J; microfocus MX"
    I02-1 (VMXm) is the microfocus branch of the versatile-MX I02 straight. It does rotation MX with a constrained-omega sample stage (small angular window, vacuum-compatible microfocus). dodal PVs are `{beamline_prefix}-...` with `beamline_prefix` = **BL02J** (env-resolved via `BeamlinePrefix(BL, suffix="J")`), insertion prefix = SR02J.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix, dodal class as sub-detail.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Goniometer | Goniometer (?) | `BL02J-MO-` (x=`SAMP-01:X`, y=`GONJK-01:HEIGHT`, z=`SAMP-01:Z`, omega=`SAMP-01:OMEGA`) | XYZWrappedOmegaStage | sample | yes |
| DCM | Monochromator | `BL02J-MO-DCM-01:` | DoubleCrystalMonochromatorBase | optics | yes |
| Attenuator | Filter | `BL02J-OP-ATTN-01:` | EnumFilterAttenuator | optics | yes |
| Slits | Slit | (Slits) | Slits | optics | yes |
| EigerDetector | Camera | `BL02J-EA-EIGER-01:` | EigerDetector | detection | yes |
| Flux | FluxMonitor | `BL02J-EA-FLUX-01:` | Flux | detection | yes |
| Zebra | TimingController (?) | `BL02J-EA-ZEBRA-01:` | Zebra (+ ZebraFastGridScanTwoD) | detection | yes |
| Undulator | InsertionDevice | `SR02J-MO-SERVC-01:` | UndulatorInKeV | source | yes |
| FastGridScanController | TimingController (?) | `BL02J-MO-STEP-11:` (motion controller) | ZebraFastGridScanTwoD | detection | yes |
| Synchrotron | GenericProbe (?) | (machine status) | Synchrotron | source | yes |

Device-level prefixes read verbatim from source: `XYZWrappedOmegaStage("{beamline_prefix}-MO-", x_infix="SAMP-01:X", ..., omega_infix="SAMP-01:OMEGA")`, `DoubleCrystalMonochromatorBase("{beamline_prefix}-MO-DCM-01:")`, `EnumFilterAttenuator("{beamline_prefix}-OP-ATTN-01:")`, `Flux("{beamline_prefix}-EA-FLUX-01:")`, `EigerDetector(prefix="{beamline_prefix}-EA-EIGER-01:")`, `Zebra(prefix="{beamline_prefix}-EA-ZEBRA-01:")`, the `motion_controller_prefix="BL02J-MO-STEP-11:"` for the 2D fast grid scan.

## Role hints

- **Positioner**: goniometer (x/y/z + constrained omega), DCM, attenuator, slits.
- **Sensor**: Flux.
- **Detector**: Eiger.
- **Timing**: Zebra + 2D fast grid scan (the microfocus raster/grid acquisition).

## Trust hints

dodal controls library; bluesky/GDA MX orchestration. Trust modeled CORA-native.

## New-family watch

No new coining. MX reuse with one discrimination to confirm:
- **XYZWrappedOmegaStage -> Goniometer (?)**: VMXm's sample stage is x/y/z + a constrained-omega rotation, NOT a full Smargon six-axis. It is still an MX sample-orientation device, so Goniometer is the likely family, but confirm whether a constrained-omega + xyz stage is the Goniometer family or a LinearStage + RotaryStage composition. This is a genuine variant-vs-family question for the recurrence.
- **DCM -> Monochromator**, **Eiger -> Camera**, **EnumFilterAttenuator -> Filter**, **Slits -> Slit**, **Flux -> FluxMonitor**, **Undulator -> InsertionDevice** (all graduated): bind directly.
- **Zebra -> TimingController (?)**: the fleet-wide gating question.

## Deferred / absent

- The microfocus KB / focusing optics, sample-loading robot, and OAV viewing are not in the read module; `OPTICS-1` / `ROBOT-1`.
- The vacuum microfocus sample environment (VMXm's distinguishing feature) is not exposed as devices; `VAC-1`.
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).
