# Extracted facts: SSRL DeNovX

Candidate device facts for `denovx` (SSRL DeNovX endstation, transmission X-ray diffraction). Candidates only; confirm every row before modeling. Source: the public `tangkong/SSRL-DeNovX` bluesky profile (`profile_bluesky/startup/instrument/devices/*.py`, read 2026-06). Every value is carried `confirm` until SSRL staff verify it: the profile is strong evidence, not a CORA-owned fact.

!!! note "Well-customized profile; real TXRD PVs"
    DeNovX (a transmission-XRD endstation, used for high-throughput materials / drug-discovery screening) has a properly customized profile with real **`TXRD:`** (transmission X-ray diffraction) and **`DETZ:`** PV prefixes. It is the simplest of the SSRL set: a cassette sample stage, a detector-Z stage, and a Dexela area detector. DeNovX is an endstation name rather than a numbered beamline; confirm which SSRL beamline hosts it (DENOVX-1).

## Device inventory

| Device | Suggested family | PV (verbatim) | ophyd class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| CassetteStage | LinearStage | `TXRD:IMS:MOTOR1` (cx), `TXRD:IMS:MOTOR2` (cy) | cassetteStage(MotorBundle) of EpicsMotor | sample | yes |
| DetectorZStage | LinearStage | `DETZ:IMS:MOTOR1` (detz) | EpicsMotor | detection | yes |
| DexelaDetector | Camera | `SSRL:DEX2923:` | Dexela | detection | yes |
| RIOAnalogIO | GenericProbe (?) | `TXRD:RIO.AI0-3`, `TXRD:RIO.AO0`, `TXRD:RIO.DO01/08-11` | EpicsSignal (NI RIO crate) | diagnostics | yes |

Device-level handles read verbatim from source: `cassetteStage` (`TXRD:IMS:MOTOR1/2`), the detector-Z motor (`DETZ:IMS:MOTOR1`), `Dexela("SSRL:DEX2923:")`, the `TXRD:RIO` crate channels.

## Role hints

- **Positioner**: the cassette sample stage (cx/cy, rastering a sample cassette through the beam) + the detector-Z stage.
- **Sensor**: the TXRD RIO crate analog/digital IO (shutter / intensity).
- **Detector**: Dexela flat panel (transmission diffraction patterns).

The "cassette" stage confirms the high-throughput transmission-XRD screening mode: a cassette of many samples stepped through the beam, each shot a transmission diffraction pattern on the Dexela.

## Trust hints

bluesky profile (ipython + `instrument` package + `happi/db.json`); no queue-server permission file. bluesky RunEngine is the orchestration CORA would conduct over.

## New-family watch

No new coining:
- **Dexela -> Camera** (graduated): the transmission-XRD area detector; bind directly.
- **CassetteStage / DetectorZStage -> LinearStage** (graduated): sample cassette + detector Z; bind directly. The cassette is a sample-delivery stage (a Subject-custody thread at modeling time), not a new family.
- **TXRD:RIO crate -> GenericProbe (loose)**: DIAG-1 cluster.

This is the leanest SSRL profile, pure reuse, no signal toward any new family.

## Deferred / absent

- **DENOVX-1:** confirm which SSRL beamline/sector hosts the DeNovX endstation (the profile is named by endstation, not beamline number).
- **MONO-1 / OPTICS-1:** the monochromator, mirrors, slits, and beam optics are not in the profile (endstation-only); open questions.
- The Dexela `SSRL:DEX2923:` root is the same shared Dexela seen at 2-1 / 1-5 (a movable detector shared across the combinatorial endstations); confirm.
- PSS / hutch safety and passive beam-path tier not in the profile (SCOPE-1).
