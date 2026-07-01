# Extracted facts: SSRL 2-2

Candidate device facts for `2-2` (SSRL beamline 2-2, continuous X-ray absorption spectroscopy: fly-scan XAS / EXAFS). Candidates only; confirm every row before modeling. Source: the public `tangkong/SSRL-2-2` bluesky profile (`profile_bluesky/startup/instrument/devices/*.py`, read 2026-06). Every value is carried `confirm` until SSRL staff verify it: the profile is strong evidence, not a CORA-owned fact.

!!! note "Properly customized profile; real BL22 PVs"
    Unlike the 2-1 profile (BL00 placeholders), the SSRL-2-2 profile carries **real `BL22:` PV prefixes** (`BL22:IMS:MOTOR1`, `BL22:SCAN:MASTER`), so its device topology is directly bindable. The signature is continuous (fly-scan) XAS: a SCAN:MASTER controller sweeps the mono energy while an FPGA box gates acquisition and DXP / Xspress3 read the absorption + fluorescence. This is the SSRL analog of NSLS-II ISS / QAS quick-EXAFS.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (verbatim from source), ophyd class as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (verbatim) | ophyd class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| SampleStage | LinearStage | `BL22:IMS:MOTOR1` (px), `BL22:IMS:MOTOR2` (py) | HiTpStage(MotorBundle) of EpicsMotor | sample | yes |
| ScanMaster | TimingController (?) | `BL22:SCAN:MASTER` | EpicsSignal (CXAS energy-trajectory master) | source | yes |
| FPGABox | TimingController (?) | (FPGABox; trigger_base_rate, trigger_width, dout1_width) | FPGABox / FPGABoxMotors | detection | yes |
| DXP1 | EnergyDispersiveSpectrometer | `DXP1:DXP` | Dxp (XIA DXP) | detection | yes |
| DXP2 | EnergyDispersiveSpectrometer | `DXP2:DXP` | Dxp | detection | yes |
| DXP3 | EnergyDispersiveSpectrometer | `DXP3:DXP` | Dxp | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | (Xspress3) | Xspress3 | detection | yes |
| ContinuousFlyer | TimingController (?) | (CXASFlyer / CXAS100EFlyer / DXP_100E) | CXASFlyer | detection | yes |
| RIOAnalogIO | GenericProbe (?) | `BL00:RIO.AI0-3`, `BL00:RIO.AO1-4`, `BL00:RIO.DO00-01` | EpicsSignal (NI RIO crate) | source | yes (BL00 shared crate) |

Device-level handles read verbatim from source: `HiTpStage` (`BL22:IMS:MOTOR1/2`), `BL22:SCAN:MASTER` (the continuous-scan master), `DXP1/2/3:DXP` (three XIA DXP spectroscopy channels), the FPGA box (`FPGABox` with trigger-rate/width signals), the `CXASFlyer` / `CXAS100EFlyer` continuous-acquisition flyers. A `BL93:SCAN:MASTER` also appears (a second/shared scan master, confirm).

## Role hints

- **Positioner**: the HiTp sample stage (px/py), FPGA box motors.
- **Detector**: three DXP channels + Xspress3 (fluorescence / absorption spectroscopy).
- **Timing / fly-scan**: SCAN:MASTER (energy-trajectory master) + FPGABox (hardware trigger/gate) + the CXAS flyers, the continuous-XAS engine. This is the fly-scan shape (mono sweeps a trajectory while hardware gates the readout), the SSRL counterpart of NSLS-II ISS's AnalogPizzaBox + trajectory.

## Trust hints

bluesky profile (ipython startup + `instrument` package + `happi/db.json`); no queue-server permission file. The bluesky RunEngine + the CXAS fly-scan plans are the orchestration layer CORA would conduct over.

## New-family watch

No new coining:
- **DXP1/2/3 + Xspress3 -> EnergyDispersiveSpectrometer** (graduated): four spectroscopy channels (three XIA DXP + one Xspress3); bind directly. Strong reinforcement of the family.
- **ScanMaster / FPGABox / CXASFlyer -> TimingController (?)**: the continuous-XAS fly-scan controllers. TimingController is the catalog family for fly-scan gating (the Zebra/PandA question fleet-wide); confirm SCAN:MASTER + FPGABox bind it vs a bare probe. This is SSRL's distinctive fly-scan engine and worth confirming carefully.
- **HiTp stage -> LinearStage** (graduated), **RIO crate -> GenericProbe (loose)**: bind directly.

## Deferred / absent

- **MONO-1:** the scanning monochromator itself is driven via `SCAN:MASTER` (an energy-trajectory abstraction) rather than a named DCM device in the profile; the physical mono / its crystal axes are not a distinct device here. Confirm the mono device (the energy_scan Capability question: SSRL 2-2 IS a live continuous-XAS beamline, so its scanning-mono path is a candidate for the pending energy_scan Capability, unlike Diamond b18's stub, worth flagging for that graduation).
- **OPTICS-1:** mirrors, slits, ion chambers (transmission I0/I1) beyond the RIO analog inputs are not clearly a named device; confirm.
- The `BL00:RIO` crate is shared/generic (same as 2-1); confirm whether it is a real shared utility crate or a template carryover (PV-1).
- PSS / hutch safety and passive beam-path tier not in the profile (SCOPE-1).
