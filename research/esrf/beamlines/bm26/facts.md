# Extracted facts: BM26

Candidate device facts for `bm26` (ESRF BM26 DUBBLE, the Dutch-Belgian CRG beamline; SAXS / WAXS + XAFS). Candidates only; confirm every row before modeling. Source: the public BM26 BLISS Beacon config (`gitlab.esrf.fr/bm26/beamline_configuration`, commit `bf4899a`, last activity 2026-04-30). Every value is carried `confirm` until BM26 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! note "Fresh, CRG beamline, not yet a deployment"
    BM26 is NOT a shipped deployment, so this is a net-new device pass feeding a future scaffold. DUBBLE (BM26) is a Collaborating Research Group (CRG) beamline operated by NWO (Netherlands) and FWO/FNRS (Belgium) on an ESRF bending-magnet port. The CRG operating model is a governance wrinkle for the seam read (the beamline is ESRF-hosted but partner-operated), not a device difference. The config is compact: one Si111 monochromator, the SAXS / WAXS Pilatus detectors, a Linkam + nanodac sample environment, and the standard ESRF slits / beamviewers / counters.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding. BM26 is a bending-magnet beamline (no insertion device); the Enclosure column carries the config zone (optics hutch `oh`, experiment hutch `eh`).

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| StorageRing | StorageRing | `//acs.esrf.fr:10000/fe/master/bm26` (BLISS `machinfo`, MachInfo) | (observe-only; current/sbcurr/lifetime counters) | oh | source | yes |
| FrontEndShutter | Shutter | `//acs.esrf.fr:10000/fe/master/bm26` (BLISS `fe`, TangoShutter, `equipment/devices/safshut.yml`) | (front-end shutter) | oh | source | yes |
| BeamShutters | Shutter | `bm26/bsh/1`, `bm26/bsh/2` (BLISS `bsh1`/`bsh2`, TangoShutter); `bm26/v-rv/10` (BLISS `p1m_protection`, detector-protection shutter) | (two beam shutters + Pilatus-1M protection shutter) | oh/eh | source | yes |
| Monochromator | Monochromator | BLISS `mono` (Monochromator, `equipment/mono/mono.yml`) | crystal Si111 (`monoxtals`); real bragg on PM600 (`pmcontroller`, `tango://d26/ld263_rp1/24`); energy calc (keV) | oh | optics | yes |
| PrimarySlits | Slit | BLISS `s1slit` (`equipment/motion/slit_s1.yml`) | real s1horr/s1horl (h), s1vert/s1verb (v); calc s1horg/s1horo/s1verg/s1vero | oh | optics | yes |
| OpticsSlits | Slit | BLISS `slit_h1` / `slit_h3` / `slit_h4` / `slit_h5` / `slit_h6` (`equipment/motion/slit_h*.yml`) | per-slit horizontal / vertical gap + offset blades | oh/eh | optics | yes |
| Mirror | Mirror | `iced261` (IcePAP host) | ymirror / zmirror (mirror translation axes; reals on iced261) | oh | optics | yes |
| BeamViewers | Screen (?) | BLISS `ohbv1` / `ohbv2` / `ohbv3` (EBV, `equipment/devices/beamviewer.yml`); wago `wcd26e` / `wcd26f` | optics-hutch beam viewers; diodes ohbv1cu / ohbv2cu / ohbv3cu | oh | diagnostics | yes |
| SampleTable | LinearStage | `iced26x` (IcePAP); session axes `ztable`/`ytable`, `tab2_*` / `tab3_*` table controllers (`equipment/motion/tab2_*.yml`, `tab3_*.yml`) | experiment-table positioning (h-legs, nh, hgt, mh/mj/ms) | eh | sample | yes |
| SampleStage | LinearStage | `iced26x` (IcePAP); session axes `samplex`/`sampley`, `sx`/`sy`/`sz`, `gonio`, `xcradle`/`ycradle` | SAXS/XAFS sample positioning + goniometer cradle | eh | sample | yes |
| Beamstop | LinearStage | `iced26x` (IcePAP); session axes `bstopy`/`bstopyb` | SAXS beamstop translation | eh | detection | yes |
| SampleTemperatureController | TemperatureController | `172.29.150.57` (controller_ip) (BLISS `nanodac1_ctrl`, Nanodac, `equipment/regulation/nanodac.yml`) | loop `nanodac1`: input `nanodac1_temp` (C), output `nanodac1_heater` (percent) | eh | sample | yes |
| LinkamStage | TemperatureController (?) | `rfc2217://ld263:28301` (BLISS `linkam1`, LinkamHardwareController, `equipment/devices/linkam.yml`) | Linkam temperature-controlled sample stage (bm26.linkam package) | eh | sample | yes |
| SAXSDetector | Camera | `d26h/limaccd/1m3s` (BLISS `p1m`, Lima, `equipment/detectors/pilatus.yml`) | Pilatus 1M (SAXS) | eh | detection | yes |
| WAXSDetector | Camera | `d26h/limaccd/300k` (BLISS `p300k`, Lima); image rotation 90 | Pilatus 300k (WAXS) | eh | detection | yes |
| VideoCameras | Camera | `d26/limaccds/cam1`, `d26/limaccds/cam2`, `d26/limaccds/cam3` (BLISS `cambv1`/`cambv2`/`cambv3`, Lima, `equipment/detectors/basler.yml`) | Basler video cameras | eh | diagnostics | yes |
| Picoammeters | FluxMonitor (?) | `enet://gpibd26a.esrf.fr` pad 14 (BLISS `k_pico1` / `k_pico2`, Keithley 6485, `equipment/counters/keithleys.yml`) | pico1 (XAFS ion-chamber / diode current readout) | eh | detection | yes |
| AnalyzerCounters | GenericProbe (?) | `tcp://ld263.esrf.fr:8909` (BLISS `p201_0`, CT2 P201, `equipment/counters/p201.yml`) | beam-monitor / counting channels | eh | detection | yes |
| TimingController | TimingController (?) | `enet://gpibd26c.esrf.fr` (BLISS `mussteh1`, musst, `equipment/devices/musst.yml`) | MUSST timing master (fly / gated scans) | eh | detection | yes |

The device-level handles above are read verbatim from the cloned config (`equipment/devices/`, `equipment/mono/`, `equipment/motion/`, `equipment/detectors/`, `equipment/counters/`, `equipment/regulation/`). BM26 is a bending-magnet beamline: there is NO insertion-device file in the config (confirmed by absence of any `ESRF_Undulator` / wiggler controller), so the source is the bending magnet, modeled loosely, not an InsertionDevice (the 2-BM precedent). The sample / table / beamstop stages are session-grouped IcePAP axes (`sessions/eh.yml`); the per-axis-to-IcePAP-host map (iced261..iced266) is recorded at the Asset level here, expand only if a deployment binds individual towers.

## Role hints

- **Positioner**: the Si111 monochromator (bragg on the PM600), all slit assemblies, the mirror, and the IcePAP sample / table / beamstop stages. Mix of `Monochromator`, `slits`, `PM600`, and `IcePAP`.
- **Sensor**: the EBV beamviewer diodes, the Keithley 6485 picoammeters (XAFS ion-chamber / diode current), the P201 counters, and the Basler video cameras read as monitors.
- **Detector**: the Pilatus 1M (SAXS) and Pilatus 300k (WAXS).
- **Regulator** (settable continuous setpoint): the Eurotherm nanodac sample-temperature loop and the Linkam temperature stage (both TemperatureController lineage, presenting Regulator).
- **Controller / timing**: the MUSST card (`mussteh1`) is the fly / gated-acquisition timing master.

## Trust hints

The BM26 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has none). The CRG operating model (DUBBLE is NWO/FWO-FNRS-operated on an ESRF port) is the notable seam input: authorization and scheduling are partner-run, not ESRF-central, which a CORA Federation / Trust model would represent as a distinct operating-group scope under the ESRF Site. The orchestration layer CORA would conduct over is the BLISS sessions (`sessions/*_setup.py`: `eh` / `optics` / `linkam`). No binding here.

## New-family watch

Nothing to coin from BM26. All bindings reinforce already-graduated families:

- **Monochromator, Slit, Shutter, Camera, LinearStage, TemperatureController, FluxMonitor (graduated).** BM26 is a further consumer of each; nothing new.
- **LinkamStage -> TemperatureController (?).** The Linkam is a temperature-controlled sample stage; it binds the graduated `TemperatureController` (the i22 Linkam precedent) by what it actuates. Confirm the `LinkamHardwareController` presents a settable setpoint loop (vs a bare hardware handle) before binding; the controller class is BM26-specific (`bm26.linkam`).
- **Bending-magnet source -> loose (not InsertionDevice).** BM26 has no insertion device; the source is the bending magnet, modeled loosely as the beam source (the 2-BM precedent), NOT through the InsertionDevice Family. Carry as `SRC-1`.
- **StorageRing / TimingController / GenericProbe / Screen.** Same loose / fallback bindings as the other ESRF beamlines; held, not coined.

## Deferred / absent

- **The bending-magnet source detail (`SRC-1`).** No source controller in the config; the bending-magnet energy reach and the white-beam acceptance are not in source.
- **PSS permit signals and hutch interlocks (`PSS-1`, `ENC-1`).** The config carries the shutters (`fe`, `bsh1`/`bsh2`, `p1m_protection`) but not the personnel-safety permit leaves, nor a clean oh/eh hutch-zone grouping. The Enclosure column is inferred from the config layout and the session names.
- **WAGO / multiplexer / simulation devices not mapped.** The wago crates (`wcd26b..f`), the opiom multiplexer, and the `manu` test session are infrastructure / test scaffolding, not beamline Assets; deferred (`INFRA-1`).
- **The XAFS detail.** DUBBLE runs XAFS as well as SAXS/WAXS; the config carries the Keithley picoammeters (ion-chamber readout) but the ion chambers themselves and any XAFS-specific monochromator scanning mode are not separately instantiated; confirm the XAFS detection chain (`XAFS-1`).
