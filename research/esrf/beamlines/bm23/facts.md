# Extracted facts: BM23

Candidate device facts for `bm23` (ESRF BM23, X-ray absorption spectroscopy: EXAFS / XANES, plus XES on a crystal-analyzer spectrometer). Candidates only; confirm every row before modeling. Source: the public BM23 BLISS Beacon config (`gitlab.esrf.fr/bm23/beamline_configuration`, commit `8bf008c`, last activity 2022-07-07; see staleness note). Every value is carried `confirm` until BM23 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! warning "Stale config: last commit 2022-07-07"
    BM23's public Beacon config has NOT been touched since 2022-07-07 (every other ESRF beamline in this set was active in 2025 or 2026). The handles are real but four years old; the live beamline has very likely moved on (renamed devices, new detectors, EBS-rebuild changes). Treat this pass as a 2022 snapshot: stronger evidence of the device topology than of the current handles. Every value is `confirm`, and the staleness is itself the first thing to verify with BM23 staff (`STALE-1`). The config also carries cross-beamline leftovers (BM05 / BM29 / ID10 / ID24 monos and sessions, an `id19bcdu8` controller) that are NOT BM23 devices; those are excluded below as `XBL-1`.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding. The Enclosure column carries the config zone (optics hutch `oh`, experiment hutch `eh`).

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| StorageRing | StorageRing | `acs:10000/fe/master/bm23` (BLISS `tango_attr_as_counter`, MachInfo attrs, `controllers/machine.yml`) | srcur / sbcur / lifetime / automatic_mode counters | oh | source | yes |
| FrontEndShutter | Shutter | `acs:10000/fe/master/bm23` (BLISS `feshut`, TangoShutter) | (front-end shutter) | oh | source | yes |
| BeamShutter | Shutter | `d23/bsh/1` (BLISS `bsh`, TangoShutter, `controllers/safshut.yml`); `bsh_bck` BackgroundShutter wraps it | (beam shutter + background-shutter logic) | oh | source | yes |
| Monochromator | Monochromator | BLISS `dcm` (BM23Mono, `mono/bm23mono.yml`) | crystals Si111 (d 3.13467) / Si333 (1.04489) / Si311 (1.63702) / Si511 (1.04514); real bragg `mbragg` -> `cbragg` (corrected); change `mty` (iced231); energy `Emono` (keV) | oh | source | yes |
| KBMirror | Mirror | BLISS `kb` (KbController, `controllers/kb.yml`) | hfocus (benders kbh1/kbh2, offset kbho) + vfocus (benders kbv1/kbv2, offset kbvo) on iced232 / `nf8752_kb`; KbMirrorCalcMotor kbvry/kbvtz; focus feedback on diagbpm | oh | source | yes |
| PrimarySlits | Slit | BLISS slit (`slits`, `motors/slit_ps.yml`) | real psh/psr (h), calc pshg/psho; vertical pair | oh | source | yes |
| BeamViewers | Screen (?) | BLISS `wbv` / `mirrorbv` / `monobv` / `diagbpm` (EBV / BM23 viewers, `controllers/beamviewer.yml`); cameras `d23/limaccds/bas_wb` | white-beam / mirror / mono / diagnostic beam viewers; diagbpm doubles as KB focus feedback | oh | source | yes |
| IonChambers | FluxMonitor | `emeter.esrf.fr` / `emeter2.esrf.fr` (BLISS `em1` / `em2`, EMH electrometers, `counters/emmeter.yml`) | per-meter ch1-4 currents + bpmx/bpmy/bpmi (em1ch1.., em1y/em1z/em1i); the EXAFS I0/I1/I2 transmission chain | eh | detection | yes |
| MCCE_Electrometers | FluxMonitor (?) | `rfc2217://ld231-new:28214` / `:28215` (BLISS `Mcce`, `controllers/mcce.yml`); also `controllers/BM23mcce.yml` | mcceI0/mcceI1/mcceI2/mcceI3 ion-chamber current amplifiers | eh | detection | yes |
| FluorescenceMCA | EnergyDispersiveSpectrometer | `tcp://wbm231:8000` (BLISS `fx`, FalconX, `counters/falconx.yml`) | XIA FalconXn fluorescence MCA (config dir `C:\\blissadm\\falconx\\config\\BM23`) | eh | detection | yes |
| EmissionSpectrometer | EmissionSpectrometer | BLISS `spectro` (Spectrometer, `spectro/spectro.yml`) | Johann Rowland-circle, crystal Si555, surface_radius_meridional 250, bragg 60-88 deg; analysers an0/anp1.. each with xpos/zpos/pitch/yaw (mspan0y/mspan0z/mspan0t/mspan0c) on iced23spectro | eh | detection | yes |
| ScatteringDetector | Camera | `bm23/limaccds/pilatus-1M` (BLISS `pilatus`, Lima, `counters/pilatus_1M.yml`) | Pilatus 1M area detector | eh | detection | yes |
| SampleRobot | LinearStage (?) | `160.103.143.106` (robot), `160.103.143.31` (barcode) (BLISS `robot`, BM23robot, `motors/robot.yml`) | sample-changer robot axis `mrobot` (1-100); barcode reader | eh | sample | yes |
| SampleStage | LinearStage | `iced231` / `iced232` (IcePAP hosts) | sample positioning stages (session `session_bm23.yml`) | eh | sample | yes |
| SampleTemperatureController | TemperatureController | `d23-ls336-1.esrf.fr:7777` (BLISS LakeShore336, `regulation/lakeshore336.yml`); LakeShore332 (`regulation/lakeshore332.yml`); Eurotherm nanodac (`160.103.143.171`, `regulation/nanodac_sample.yml`) | LS336 inputs A/B, outputs 1/2; nanodac loop (C / percent); the XAS sample-temperature environments | eh | sample | yes |
| GasFlowController | FlowController (?) | BLISS Bronkhorst (`regulation/bronkhorst.yml`); PACE pressure controller (`regulation/pace.yml`) | gas mass-flow + pressure for in-situ XAS sample cells | eh | sample | yes |
| HighVoltageSupply | GenericProbe (?) | `ld232:28202` (BLISS `nhq`, Nhq, `controllers/nhq206l.yml`) | iSeg NHQ 206L HV supply (detector / ion-chamber bias) | eh | detection | yes |
| AnalyzerCounters | GenericProbe (?) | `tcp://ld232:8909` (BLISS `p201`, CT2 P201, `counters/p201.yml`) | beam-monitor / counting channels; calc counters for BPM / dark / energy (`counters/calccnt_*.yml`) | eh | detection | yes |
| TimingController | TimingController (?) | BLISS `musst` (`controllers/musst.yml`) | MUSST timing master (EXAFS fly / continuous-scan gating) | eh | detection | yes |

The device-level handles above are read verbatim from the cloned config. The BM23 mono real bragg is `mbragg` corrected to `cbragg` (BraggCorrectedCalcMotor) then to energy `Emono`; the change-crystal motor is `mty` (iced231). The KB benders / offsets live on iced232 and the `nf8752_kb` PicoMotor controller; the focus feedback reads `diagbpm`. The emission spectrometer (`spectro`, Si555 Johann) analyser motors are on `iced23spectro`.

## Role hints

- **Positioner**: the BM23 mono (mbragg / mty), the KB mirror benders, the primary slits, the emission-spectrometer analysers, and the IcePAP sample stages. Mix of `BM23Mono`, `KbController`, `slits`, `Spectrometer`, and `IcePAP`.
- **Sensor**: the EMH electrometers and MCCE amplifiers (the EXAFS I0/I1/I2 ion-chamber transmission chain, the core XAS measurement), the FalconX fluorescence MCA, the EBV beamviewer diodes, the P201 counters, the NHQ HV readout.
- **Detector**: the Pilatus 1M (scattering), the FalconX MCA (fluorescence XAS), and the crystal-analyzer EmissionSpectrometer (XES / HERFD).
- **Regulator** (settable continuous setpoint): the LakeShore 336 / 332 and Eurotherm nanodac sample-temperature loops (TemperatureController), and the Bronkhorst mass-flow + PACE pressure controllers (FlowController) for in-situ gas cells.
- **Controller / timing**: the MUSST card (`musst`) is the continuous-scan (QEXAFS) timing master; the two MOCO boxes (`controllers/moco.yml`) are monochromator feedback.

## Trust hints

The BM23 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has none). The orchestration layer CORA would conduct over is the BLISS sequences (`sequences/scan_exafs.yml`, `scan_diffr.yml`, `scan_mapping.yml`, `scan_temperature.yml`) and the per-user sessions. The EXAFS continuous-scan sequence (`scan_exafs.yml` + MUSST) is the signature BM23 routine a CORA edge would conduct. No binding here.

## New-family watch

Nothing to coin from BM23. All bindings reinforce already-graduated families:

- **Monochromator, Mirror, Slit, Camera, FluxMonitor, EnergyDispersiveSpectrometer, TemperatureController, FlowController (graduated).** BM23 is a further consumer of each.
- **EmissionSpectrometer (graduated), a further consumer.** The BM23 `spectro` (Si555 Johann Rowland-circle crystal-analyzer XES spectrometer) binds the graduated `EmissionSpectrometer` family (the LCLS-MFX / ISS precedent, with MAX IV Balder a near-sighting). BM23 is a further consumer, reinforcing it; whether each analyser crystal (an0 / anp1..) is a child Asset is the deferred `SPEC-1` question. Nothing to coin.
- **SampleRobot -> LinearStage (?).** The BM23 sample-changer robot (`BM23robot`, a single `mrobot` axis + barcode) binds LinearStage by role for now; a sample-exchange-robot family is a fleet-wide question (the MX robots at i03 / FMX / AMX), not coined from BM23.
- **MCCE -> FluxMonitor (?).** The MCCE current amplifiers feed the ion chambers; they bind FluxMonitor by what they measure (transmitted flux), but confirm vs a bare amplifier handle.
- **StorageRing / TimingController / GenericProbe / Screen / HighVoltageSupply.** Same loose / fallback bindings as the other ESRF beamlines; held, not coined.

## Deferred / absent

- **Staleness (`STALE-1`).** The config is a 2022 snapshot; the live beamline has likely changed. The single most important confirm.
- **Cross-beamline leftovers (`XBL-1`).** The config carries non-BM23 devices: `mono/bm05mono.yml`, `mono/bm29mono.yml`, `mono/id10mono.yml`, `mono/id10eh2mono.yml`, the `bistate/bm29_actuator.yml`, `controllers/id19bcdu8.yml`, and `sessions/session_id24.yml`. These are other beamlines' devices left in the BM23 config (shared-development cruft), NOT BM23 Assets; excluded from the inventory above. Confirm none is actually operative at BM23.
- **PSS permit signals and hutch interlocks (`PSS-1`, `ENC-1`).** The config carries the shutters (`feshut`, `bsh`) but not the personnel-safety permit leaves, nor a clean oh/eh hutch-zone grouping. The Enclosure column is inferred.
- **Bending-magnet source detail (`SRC-1`).** BM23 is a bending-magnet beamline (no insertion device in the config); the source is the bending magnet, modeled loosely (the 2-BM precedent), not InsertionDevice. The energy reach and white-beam acceptance are not in source.
- **WAGO / opiom / valves / simulation devices not mapped.** The wago / opiom / valve-manager / bistate / sim devices are infrastructure or beam-path plumbing, not beamline Assets; deferred (`INFRA-1`).
- **The energymeter / Tektronix.** `controllers/energymeter.yml` binds an `enmeterid241` energy meter and an `id24tektro64` Tektronix scope (both ID24-hosted by their names); likely XBL-1 cross-beamline, deferred.
