# Extracted facts: ID06

Candidate device facts for `id06` (ESRF ID06, hard X-ray microscopy / dark-field X-ray microscopy (DFXM) + X-ray optics testing + large-volume press (LVP)). Candidates only; confirm every row before modeling. Source: the public ID06 BLISS Beacon config (`gitlab.esrf.fr/ID06/beamline_configuration`, commit `19bad8a`). Every value is carried `confirm` until ID06 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! note "Fresh, multi-technique, not yet a deployment"
    Unlike ID28 / ID32, ID06 is NOT a shipped deployment, so this is a net-new device pass feeding a future scaffold, not a retrospective alignment. ID06 is a multi-technique beamline: its config carries distinct BLISS sessions for hard X-ray / dark-field microscopy (DEG, XOG), a large-volume press (LVP), and general diffraction endstations (EH1, EH2). This pass maps the shared optics plus the device set the sessions actually instantiate; the press mechanism itself is absent from the public config and is recorded as an open question, not invented.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding. The Enclosure column carries the config zone (optics `oh`, experiment `eh1` / `eh2`).

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| StorageRing | StorageRing | `//acs.esrf.fr:10000/fe/master/id06` (BLISS `machinfo`, MachInfo); `acs:10000/id/power/all` (max_srcurr) | (observe-only; current/lifetime counters) | oh | source | yes |
| FrontEndShutter | Shutter | `acs:10000/fe/master/id06` (BLISS `fe`, TangoShutter, `machine/safshut.yml`) | (front-end shutter) | oh | source | yes |
| EH1Shutter | Shutter | `id06/bsh/1` (BLISS `bsh1`, TangoShutter, `eh1/bsh1.yml`) | (EH1 beam shutter) | eh1 | source | yes |
| FastShutter | Shutter | BLISS `eh1fs` (`eh1/devices/fshutter.yml`) | (EH1 fast shutter) | eh1 | source | yes |
| Undulators | InsertionDevice | `//acs.esrf.fr:10000/id/master/id06` (BLISS `ESRF_Undulator`, `machine/undulator.yml`) | cpmu18a_gap=`CPMU18a_GAP` (5.9-201 mm), cpmu18a_offset=`CPMU18a_OFFSET`; u27c_gap=`U27c_GAP` (10.9-210 mm), u27c_taper=`U27c_TAPER` | oh | source | yes |
| Monochromator | Monochromator | BLISS `cinel` (ID06mono, `oh/mono.yml`) | crystals Si111 (dspacing 3.13299) / Si311 via `mvx` change motor; reals bragg=`monofe`, xtal=`x2z`; energy calc (keV); fix_exit_offset 14.9012 | oh | source | yes |
| Transfocator | Transfocator | BLISS `tf` / `tf_connector` (TransfocatorID06, `oh/transfocator.yml`); wago `wcid06f` | layout `PXLLLLLLLLXXXXLXLLLP`; 2D + 1D Be lens banks (R=1.5/1.0/0.5/0.3/0.2 mm); piezo-driven insert | oh | source | yes |
| PrimarySlits | Slit | BLISS `s1` (`oh/s1.yml`) | real s1l/s1r/s1t/s1b; calc s1hg/s1ho/s1vg/s1vo | oh | source | yes |
| SecondarySlits | Slit | BLISS `s2` (`oh/s2.yml`) | real + calc s2hg/s2ho/s2vg/s2vo | oh | source | yes |
| EH1Slits | Slit | BLISS `s3` (`eh1/s3.yml`) + `s4` (`eh1/s4.yml`) | real s3l/s3r/s3t/s3b; calc s3hg/s3ho/s3vg/s3vo (and s4) | eh1 | source | yes |
| MonochromatorFeedback | Controller (?) | BLISS `pmoco` / `rmoco` (Moco, `oh/pmoco.yml`, `oh/rmoco.yml`) | beam-stabilization monochromator feedback (MOCO box) | oh | source | yes |
| IntensityMonitor1 | FluxMonitor (?) | BLISS `mon1` (ID06IntMon1, `oh/mon1.yml`); count card `p201_060_1`; wago `wcid06b` | quadrant inputs mon1ul/mon1dl/mon1dr/mon1ur; foil wheel `wheel1` | oh | source | yes |
| IntensityMonitor2 | FluxMonitor (?) | BLISS `mon2` (ID06IntMon2, `eh1/mon2.yml`); count card `p201_060_1`; wago `wcid06c` | quadrant inputs mon2ul/mon2dl/mon2dr/mon2ur; foil wheel `wheel2` | eh1 | source | yes |
| DFXM_SamplePiezo | LinearStage | `e727pitroth:50000` (tcp) (BLISS `e727pitrotha`, PI_E727, `motors/pie727.yml`) | pzh=`channel 1`; pzv=`channel 2` (DFXM fine sample pitch / orientation) | eh1 | sample | yes |
| DFXM_SampleStage | LinearStage | `iceid061` / `iceid062` (IcePAP hosts, `motors/iceid061.yml`, `iceid062.yml`) | sample / objective positioning stages (DEG / XOG microscopy sessions) | eh1 | sample | yes |
| LVP_Stage | LinearStage | `iceid063` (IcePAP host, `eh2/motion/iceid063.yml`) | omega, rrot, slit_th, slit_y; sample/detector translations (x1/x2/y1063/z1063, detx/dety063/detz1); cam stages camy/camz/camfoc | eh2 | sample | yes |
| DEG_BeamConditioning | (deferred) | (blank: only a `$bcdu8` reference exists in `degdevices/xiderdet.yml`, no object definition in the public config) | DFXM beam-conditioning / decoherer unit (deg_bliss package, firewalled) | eh1 | source | yes |
| DEG_FilterBox | Filter (?) | BLISS `degfilters` (FilterBoxSet, `degdevices/degfilters.yml`); wago `wcid06d` | attenuator foil box, srcur-referenced (refsrcur 200) | eh1 | source | yes |
| Maxipix | Camera | `id06/limaccds/mpxdp1` (BLISS `mpxdp1`, Lima, `detectors/maxipix.yml`); `id06/limaccds/du_maxipix2` | Maxipix photon-counting pixel detector (DFXM far-field) | eh1 | detection | yes |
| Pixirad | Camera | `id06/limaccds/pixirad` (BLISS `pixirad8`, Lima, `detectors/pixirad.yml`) | Pixirad CdTe photon-counting detector | eh1 | detection | yes |
| FrelonFarField | Camera | `id06/limaccds/frelon_farfield` (BLISS `frelon_eh1`, Lima, `detectors/frelon.yml`) | Frelon CCD (far-field DFXM) | eh1 | detection | yes |
| PCO | Camera | `id06/limaccds/pco2k1`, `id06/limaccds/pco55_eh1` (BLISS, `detectors/pco.yml`, `pco_eh1.yml`) | PCO sCMOS cameras | eh1 | detection | yes |
| Baslers | Camera | `id06/limaccds/{bas13,lvp,xrayeye,hxrayeye,barrett,snigirev,xfour,wbpm,eh1bpm,eh1sample,baseth5,bastroth}` (BLISS, `detectors/basler.yml`) | Basler video cameras (sample view, beam viewers, LVP view, optics-test imaging) | eh1/eh2 | source | yes |
| Pilatus | Camera | `id06/limaccds/pilatus-900kw` (BLISS `p900kw`, Lima, `eh2/detectors/pilatus.yml`) | Pilatus 900kw strip detector (EH2 diffraction) | eh2 | detection | yes |
| Smartpix | Camera | BLISS `smpx` (Lima, `eh2/detectors/smartpix.yml`) | Smartpix photon-counting detector (EH2) | eh2 | detection | yes |
| Sphird | Camera (?) | BLISS `sphird0` (SphirdBlissController, `degdevices/sphirddet.yml`); host `lapsphird` | DEG Sphird area detector (deg_bliss package, controller firewalled) | eh1 | detection | yes |
| Xider | Camera (?) | BLISS `xider0` (XiderBlissController, `degdevices/xiderdet.yml`); host `pcxider1` | DEG Xider area detector (deg_bliss package, controller firewalled) | eh1 | detection | yes |
| HighVoltageSupply | GenericProbe (?) | `lid063:28220` (tcp) (BLISS `nhq`, Nhq, `eh1/nhq.yml`) | iSeg NHQ HV supply (iav voltage, channel A); detector / sample bias | eh1 | detection | yes |
| AnalyzerCounters | GenericProbe (?) | `tcp://lid060:8910` / `:8909` (BLISS `p201_060_0` / `p201_060_1`, P201); `tcp://lid064:8909` (EH2) | beam-monitor / counting channels (mon1/mon2 quadrants, p201_1..4) | oh/eh2 | detection | yes |
| TimingControllers | TimingController (?) | BLISS `musst_eh2` (`eh2/devices/musst_eh2.yml`) | MUSST timing master (EH2 fly / gated scans) | eh2 | detection | yes |
| SampleTemperatureController | TemperatureController | `nanodacid06.esrf.fr` (BLISS `nanodacid06`, Nanodac, `regulation/nanodac.yml`) | Eurotherm nanodac loop (in C, output percent 0-80); SoftLoop `nanodac_power_regul` over epack | eh1 | sample | yes |

The device-level handles above are read verbatim from the cloned config (`machine/`, `oh/`, `eh1/`, `eh2/`, `motors/`, `detectors/`, `degdevices/`, `regulation/`). The LVP-station axes (`omega`/`rrot`/`slit_y`/`slit_th` and the sample/detector/cam translations) are all defined on `eh2/motion/iceid063.yml`; the LVP session (`sessions/LVP.yml`) groups them with the `lvp` Basler camera. The DFXM / dark-field microscopy sessions (`DEG`, `XOG`) share the `oh` optics and add the PI E727 sample piezo plus the Sphird / Xider / Maxipix detectors.

## Role hints

- **Positioner**: the Cinel monochromator (bragg/xtal), all slit assemblies, the transfocator lens insert, the PI E727 DFXM sample piezo (pzh/pzv), and the IcePAP sample / detector / LVP stages (iceid061/062/063). Mix of `ID06mono`, `slits`, `TransfocatorID06`, `PI_E727`, and `IcePAP`.
- **Sensor**: the two ID06 intensity monitors (mon1/mon2 quadrant + foil), the P201 counters, the NHQ high-voltage readout, and the Basler beam-viewer cameras read as monitors.
- **Detector**: the photon-counting / area detectors (Maxipix, Pixirad, Frelon far-field, PCO, Pilatus 900kw, Smartpix) and the DEG Sphird / Xider detectors.
- **Regulator** (settable continuous setpoint): the Eurotherm nanodac sample-temperature loop (TemperatureController), with a SoftLoop power regulator over the epack.
- **Controller**: the two MOCO boxes (pmoco / rmoco) are monochromator beam-stabilization feedback controllers; the MUSST card (musst_eh2) is the EH2 timing master.

## Trust hints

The ID06 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has none). The orchestration layer CORA would conduct over is the BLISS sessions (`sessions/*_setup.py`, one per technique: LVP / DEG / XOG / EH1 / EH2 / BCU). The multi-session structure is itself a seam-read input: ID06 runs several distinct experiment modes from one Beacon config, which a CORA Run / Procedure model would represent as distinct practices over shared optics. No binding here.

## New-family watch

ID06 surfaces one genuine new-family candidate and several loose / fallback bindings. Per the rules, nothing is coined here.

- **LargeVolumePress (candidate, but ABSENT from source).** ID06's headline non-tomography technique is the large-volume press (the `LVP` session, scan_saving beamline `id06-lvp`). This is a sample-environment device class no existing catalog Family covers (a multi-anvil hydraulic press applying GPa pressure, distinct from any optic or stage). However, the public config instantiates NO press / ram / anvil / load-cell controller: the `LVP` session drives only generic IcePAP stages (`omega`/`rrot`/`slit_y` on iceid063) and a Basler view camera (`lvp`). So the press mechanism is absent from public source. Per the practice, this is an open question (`PRESS-1`), NOT a coined Family and NOT an inferred device. It would need the press controller to appear in source (or staff confirmation) before it is even a watch with one sighting; right now it is a technique without a device in the public config.
- **DEG detectors (Sphird / Xider) and bcdu8 beam-conditioning -> firewalled.** The DFXM-specific detectors (`SphirdBlissController`, `XiderBlissController`) and the `bcdu8` beam-conditioning unit are instantiated by name but their controller classes live in the private `deg_bliss` package, not the public config. They bind `Camera (?)` by role (area detectors) but the device contract is firewalled; carry as `DEG-1`, do not infer the family from the class name alone.
- **MOCO feedback -> Controller (?).** The pmoco / rmoco MOCO boxes are monochromator beam-position feedback controllers. `Controller` is a catalog Role, not a Family; confirm whether this binds an existing Family or stays a loose feedback-controller class. MonoFeedback-style devices recur fleet-wide (the APS recurrence `MonoFeedback`), a watch but not coined from ID06.
- **IntensityMonitor (mon1/mon2) -> FluxMonitor (?).** The ID06 quadrant intensity monitors with foil wheels read beam flux; FluxMonitor covers them by what they measure, but the foil-wheel + quadrant composition is richer than a bare ion chamber; confirm before binding (vs a composed Assembly).
- **DEG_FilterBox -> Filter (?).** The `FilterBoxSet` attenuator binds the graduated `Filter` family by role; confirm the contract.
- **StorageRing / TimingController / GenericProbe / HighVoltageSupply.** Same loose / fallback bindings as the other ESRF beamlines; the NHQ HV supply has no catalog home (a detector / sample bias supply), stays loose GenericProbe pending its own rule-of-three.

## Deferred / absent

- **The large-volume press mechanism (`PRESS-1`).** As above: the headline LVP technique has no press / anvil / ram device in the public config. Named as an open question, not modeled.
- **PSS permit signals and hutch interlocks (`PSS-1`, `ENC-1`).** The config carries the shutters (`fe`, `bsh1`, `eh1fs`) but not the personnel-safety permit leaves, nor a clean hutch-zone grouping. The Enclosure column is inferred from the config directory layout (oh / eh1 / eh2).
- **The deg_bliss DFXM stack (`DEG-1`).** The Sphird / Xider detector controllers and the bcdu8 beam-conditioning unit are in the private `deg_bliss` package; only their instantiation names are public. Device contracts firewalled.
- **WAGO / opiom / simulation / BCU devices.** The wago crates (`wcid06b..f`), the simulation motors / counters, and the `BCU` (beamline-control-unit) maintenance session are infrastructure / test scaffolding, not beamline Assets; deferred (`INFRA-1`).
- **Undulator detail (`SRC-1`).** The CPMU18a (cryogenic permanent-magnet undulator, 18 mm) and U27c are the active source set; several other undulator axes (u27b, u20c) are commented out in `machine/undulator.yml`. The operative source set and energy reach need confirm.
