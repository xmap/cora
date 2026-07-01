# Extracted facts: ID28

Candidate device facts for `id28` (ESRF ID28, momentum-resolved inelastic X-ray scattering, IXS). Candidates only; confirm every row before modeling. Source: the public ID28 BLISS Beacon config (`gitlab.esrf.fr/id28/beamline_configuration`, commit `85fe3f3`, last activity 2026-02-24). Every value is carried `confirm` until ID28 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! note "Retrospective alignment, not net-new"
    ID28 is already a shipped ESRF deployment (`deployments/id28/beamline.yaml`), so this Tier-2 pass is a *reference and cross-check*, not a fresh scaffold. It is cross-checked against the shipped descriptor; two discrepancies surfaced (a clutch of side-station devices the shipped cut omitted, and the analyzer-arm Family map), recorded honestly below rather than silently aligned.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source (`name`, BLISS object name, or Tango URL). A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| StorageRing | StorageRing | `//acs:10000/fe/master/id28` (BLISS `machinfo`, MachInfo) | (observe-only machine state) | oh1 | source | yes |
| FrontEndShutter | Shutter | `acs.esrf.fr:10000/fe/master/id28` (BLISS `fe`, TangoShutter FrontEnd) | (PPS-fed front-end shutter) | oh1 | source | yes |
| BeamShutters | Shutter | `id28/v-bsh/0`, `id28/v-bsh/1`, `id28/v-bsh/2` (BLISS `bsh1`/`bsh2`/`bsh3`, TangoShutter) | (three vacuum beam shutters) | oh1 | source | yes |
| Undulator | InsertionDevice | `//acs:10000/id/master/id28` (BLISS `ESRF_Undulator`) | u22gap=`IVU22a_GAP` (11.1-300 mm); u133gap=`IVU13-3c_GAP` (11.1-300 mm) | oh1 | source | yes |
| Premonochromator | Monochromator | (BLISS session motors `mono`, `pi1`, `pmscr`; no standalone controller yml in config) | mono=premono angle; pi1=second-xtal correction; pmscr=screen | oh1 | source | yes |
| Postmonochromator | Monochromator | (BLISS session motors `pmth`/`pmchi`/`pmy`/`pmz`/`pi2`/`pmono2`/`pmscr2`; no standalone controller yml) | pmth=theta; pmchi=chi; pmy/pmz=translations; pi2=fine rotation; pmono2=second-xtal | oh2 | source | yes |
| Monochromator | Monochromator | `e518id28` (tcp) (BLISS `PI_E518`, `oh3/main_mono_pi_e518.yml`) | pimth=`channel 1` (enc `pimth_enc`); pimchi=`channel 2` (enc `pimchi_enc`); session reals mth/mchi | oh3 | source | yes |
| BeamEnergy | PseudoAxis | `enet://gpibid28c` pad 3 (BLISS `F700`, ASL F700, `oh3/asl_f700.yml`) | monot=setpoint (7-23 C); deltae=energy (kev, +/-800); LAMBDA 0.5226; T0 22.854 | oh3 | source | yes |
| HorizontalFocusingMirror | Mirror | BLISS `hfm_ctrl` (HFM, `oh3/hfm.yml`) | real hfmb1/hfmb2 (benders); hfmz1/hfmz2 (z); hfmth (rotation); hfmtz (tiltz); calc hfmz/hfmy/hfmtx/hfmb | oh3 | source | yes |
| VerticalFocusingMirror | Mirror | BLISS `vfm_ctrl` (VFM, `oh3/vfm.yml`) | real vfmb1/vfmb2 (benders); vfmz1/vfmz2 (z); calc vfmz/vfmb | oh3 | source | yes |
| BeamPositionMonitor | BeamPositionMonitor | `tango://id28/elettra/oh2` (BLISS `elettra_bpm_oh2`, Elettra) | ebpmx/ebpmy (position); ebpmc1..ebpmc4 (quadrant currents); ebpmct (total) | oh2 | source | yes |
| PrimarySlits | Slit | BLISS `slits_ph` / `slits_pv` (`slits/slit_phg.yml`, `slits/slit_pvg.yml`) | real pr/pl (h) on `iceid281`, pu/pd (v); calc phg/pho, pvg/pvo | oh3 | source | yes |
| MonoSlit | Slit | BLISS `slits_mx` (`slits/slit_mxgap.yml`) | real mxr/mxl; calc mxgap/mxoff | oh3 | source | yes |
| SampleStage | Goniometer (?) | `iceid282` (IcePAP host) | sax=`addr 52`; say=`addr 53`; saz=`addr 54`; th=`addr 23`; sphi=`addr 26`; chi=`addr 48`; tthm=`addr 24`; ty=`addr 22`; session adth/ovrot/tiltz | eh1 | sample | yes |
| SideStationStage | LinearStage | `iceid285` (IcePAP host, `eh1_ss/motors/iceid285.yml`) | phi=`address 4`; omega=`address 6`; sz=`address 12` | eh1_ss | sample | yes |
| SmarActStage | LinearStage | `172.29.46.81` (tcp) (BLISS `smaract1`, SmarAct_MCS2) | Gx=`channel 0`; Gy=`channel 1` (1 nano-degree step) | eh1_ss | sample | yes |
| SampleSlits | Slit | BLISS `slits_sh` / `slits_sv` (`slits/slit_shg.yml`, `slits/slit_svg.yml`) | real sr/sl (h), su/sd (v); calc shg/sho, svg/svo; session i1shg/i1sho/i1svg/i1svo | eh1 | sample | yes |
| Transfocator | Transfocator | `wcid28e` (controller_ip) (BLISS `tf`, Transfocator, `eh1_ss/tf.yml`) | layout `P L L L L L L L P` (8 lenslets + 2 pinholes) | eh1_ss | source | yes |
| BeamViewer | Screen (?) | `wcid28f` (modbustcp) (BLISS `mbv`, EBV, `eh1_ss/mbv.yml`); camera `id28/limaccds/mbv` | diode counter; single_model false; has_foil false | eh1_ss | source | yes |
| BPMPositioner | LinearStage | `amc100id281` (host) (BLISS `AMC100`, attocube, `eh1/attocube_amc100_bpmxy.yml`) | bpm_y=`channel 1`; bpm_z=`channel 2` (ECSx5050) | eh1 | source | yes |
| EnergyAnalyzer | EnergyAnalyzer | BLISS `tth_multilayer` (TwoThetaMultilayer, `eh1/tth_multilayer.yml`) + `a2_inca`/`a3_inca`/`a4_inca` (InclinedAnalyser, `eh1/inca.yml`) | arm: real tthm, calc tth; per-crystal: achipN/athpN (real), achiN/athN (calc); cylslits a1h..a9h, a1v..a6v (`CylSlit`, radius 43.5, `slits/cylslits.yml`) | eh1 | detection | yes |
| Detector | Camera | `id28/limaccds/basler_0` (BLISS `basler_ixs`, Lima) + `id28/limaccds/pco` (BLISS `pco`, Lima) | basler bpm counters via `id28/bpm/basler_0` (intensity/x/y/fwhm_x/fwhm_y) | eh1 | detection | yes |
| AnalyzerCounters | GenericProbe (?) | `tcp://lid282:8909` / `:8910` / `:8911` (BLISS `P201_282_A`/`B`/`C`, CT2 P201) | deta1..deta9 (per-analyzer); izero/ione/imirr; pmoni/pomoni; detsq; iver1/iver2/ihor1/ihor2 | eh1 | detection | yes |
| TimingController | TimingController (?) | `enet://gpibid28e.esrf.fr` pad 13 (BLISS `musst_eh1`, musst) | musst_x/musst_y/musst_i/musst_ref (adc5 channels 1-4) | eh1 | detection | yes |
| SidePicoammeter | FluxMonitor (?) | `enet://gpibid28ssa.esrf.fr` pad 14 (BLISS Keithley 6485, `eh1_ss/counters/keithley.yml`) | pico1=`address 1` (diode current) | eh1_ss | detection | yes |
| SampleTemperatureController | TemperatureController | `enet://gpibid28g.esrf.fr` pad 12 (BLISS `lakeshore340_10kdiplex`, LakeShore 340) | Tango `id28/regulation/lakeshore340_*` (inputs A-D, loop `ls340_loop1`); alternatives: Oxford 700 (`oxford700`, `rfc2217://lid281:28326`, `id28/regulation/oxford_700_*`) and nanodac gas blower (`nanodac_gasblower`, `172.29.46.36`, `id28/regulation/nanodac_gasblower_*`) | eh1 | sample | yes |

The device-level handles above are read verbatim from the cloned config (`machine/`, `oh2/`, `oh3/`, `slits/`, `eh1/`, `eh1_ss/`, `icepap/`, `lima/`, `regulation/`, `sessions/bliss_fourc.yml`). The premono / postmono Assets appear only as session motors (`sessions/bliss_fourc.yml`); they have no standalone controller yml in the public config, so their handles are the BLISS axis names, not a controller object (MONO-1). The scattering-geometry axes (`sax`/`say`/`saz`/`th`/`sphi`/`chi`/`tthm`/`ty`) are defined on `icepap/iceid282.yml` at the IcePAP addresses shown (read verbatim from the `address:` field, not the file line).

## Role hints

- **Positioner**: the two mirrors (HFM / VFM, IcePAP-driven bender + height + rotation), the mono piezo (PI E518 pimth/pimchi), all four slit assemblies, the scattering-geometry sample stage (`iceid282`), the side-station stage (`iceid285`), the SmarAct fine stage, the transfocator lens drives, and the AMC100 BPM positioner. Most are `IcePAP` or dedicated BLISS calc controllers (`HFM`/`VFM`/`slits`/`TwoThetaMultilayer`/`InclinedAnalyser`/`CylSlit`).
- **Sensor**: the Elettra OH2 beam-position monitor (quadrant currents + position), the P201 CT2 counter cards (per-analyzer `deta1..deta9`, beam monitors `izero`/`ione`/`imirr`), the Keithley 6485 side-station picoammeter, and the basler `id28/bpm/basler_0` intensity/centroid readout.
- **Detector**: the Basler IXS Lima camera and the PCO Lima camera.
- **Regulator** (settable continuous setpoint): the three sample-temperature controllers (LakeShore 340 displex, Oxford 700 cryostream, nanodac gas blower) each expose a regulation loop with a setpoint; they present the Regulator Role (the TemperatureController lineage). The ASL F700 is also a temperature controller, but it regulates the *monochromator crystal* temperature to set the incident energy, so it is modeled as the BeamEnergy PseudoAxis realization, not a sample-environment Regulator (MONO-1).
- **Controller / timing**: the MUSST card (`musst_eh1`) is the fly / gated-acquisition timing master driving the P201 chain (the `chain_fourc` ExtGate config in `sessions/bliss_fourc.yml`), a TimingController-role hint.

## Trust hints

The ID28 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has no equivalent of the NSLS-II `user_group_permissions.yaml`); authorization at ESRF is a Tango / BLISS-session concern not expressed in the device database. CORA models its own Trust spine, so this absence is itself a seam-read input: the orchestration layer CORA would conduct over is the BLISS sequences (`sessions/scripts/*.py`), consistent with the ESRF survey. No binding here.

## New-family watch

Nothing to coin from ID28 alone. Bindings to flag, none meeting rule-of-three from this beamline:

- **EnergyAnalyzer (loose), NOT SpectrometerArm.** This is the one substantive cross-check finding. The IXS two-theta multi-analyzer arm (`tth_multilayer` carrying the `inca` inclined-crystal analyzers in backscattering) is the catalog's loose **`EnergyAnalyzer`** case (the "IXS diced-crystal analyzer selecting a fixed final energy on the inelastic-scattering arm", `ANALYZER-1`), distinct by the catalog's own note from the loose **`SpectrometerArm`** (the "SIX soft X-ray grating-dispersive multi-chamber RIXS arm", `RIXS-1`). The shipped `deployments/id28/beamline.yaml` binds this Asset to `SpectrometerArm`, reading ID28 as a further `SpectrometerArm` consumer reinforcing `RIXS-1`. Per `catalog/catalog.yaml` the IXS crystal-analyzer arm is the `EnergyAnalyzer` lineage, not the grating-dispersive `SpectrometerArm`. Recorded as a question for the next ID28 modeling pass, not silently aligned: confirm which loose family ID28 reinforces (this changes which graduation `ANALYZER-1` vs `RIXS-1` ID28 is a sighting toward). Either way it stays LOOSE and held; do not coin from ID28.
- **The nine-crystal analyzer array is a per-Asset setting, not a child-Asset family.** The `a1..a9` inclined analyzers (each with chi / theta and a cylinder slit) are the array on the one arm; this is the `IXS-1` per-Asset-settings question, not a new Family. Note the config instantiates explicit `InclinedAnalyser` controllers only for `a2`/`a3`/`a4` (`eh1/inca.yml`); `a1` and `a5..a9` appear only as session tilt motors (`ath1`/`achi1`, `ath5..ath9`/`achi5..achi9` in `sessions/bliss_fourc.yml`), and the cylinder slits run `a1h..a9h` but only `a1v..a6v` (no `a7v`/`a8v`/`a9v` in `slits/cylslits.yml`). The operative crystal count is `IXS-1`.
- **TimingController (?) for MUSST.** The MUSST card is the gated-acquisition timing master (the `chain_fourc` ExtGate). `TimingController` is a catalog Family; confirm MUSST presents it (vs a bare GenericProbe). MUSST/PandABox/Zebra-style timing recurs across fly / gated-scan beamlines fleet-wide (the SRX Zebra watch), a graduation watch but not coined here.
- **AnalyzerCounters / SidePicoammeter -> GenericProbe / FluxMonitor (?) (loose).** The P201 CT2 cards are the IXS counting backend (per-analyzer photon counts); they stay loose GenericProbe like the NSLS-II scaler precedent. The Keithley 6485 reads a side-station diode current; FluxMonitor covers picoammeters by what they measure, but confirm it reads beam flux (vs a generic voltage) before binding.
- **BeamPositionMonitor (loose, DIAG-1).** The OH2 Elettra binds the loose `BeamPositionMonitor`, already held under the fleet-wide `DIAG-1` position-monitor review; do not coin from ID28.
- **BeamViewer -> Screen (?).** The MBV (ESRF Beam Viewer, `EBV` class) is a diode + Lima-camera beam viewer; `Screen` is the closest catalog Family (the BMM DiagnosticScreen precedent). Confirm it is a Screen (a viewer) vs a FluxMonitor (the diode); likely a composed Screen + diode.

## Deferred / absent

- **PSS permit signals and hutch interlocks (`PSS-1`, `ENC-1`).** The config carries the shutters (`fe`, `bsh1`/`bsh2`/`bsh3`) but not the personnel-safety permit leaves behind them, nor a clean oh1/oh2/oh3/eh1/eh1_ss hutch-zone grouping. The enclosure column above is inferred from the config directory layout (`oh2/`, `oh3/`, `eh1/`, `eh1_ss/`); confirm the hutch boundaries with staff.
- **Undulator period / segment detail (`SRC-1`).** The two in-vacuum undulators are named `IVU22a` / `IVU13-3c` (implying 22 mm / 13 mm periods) but the period, segment count, and which feeds which mode are not in the config.
- **WAGO / opiom / simulation devices not mapped.** The `wago/` Modbus crates (`wcid28a..g`), the `simulation/` mirror devices, and the `laurent` test session are infrastructure / test scaffolding, not beamline Assets; deferred, not modeled (`INFRA-1`).
- **Laser-heating and thin-film sample setups.** `sessions/bliss_fourc.yml` lists a laser-heating axis group (`lhux`/`lhuy`/`lhuz`/`lhdx`/`lhdy`/`lhdz`/`lhchi`) and a thin-film group (`actz`/`acth`/`acrg`/`acfine`/`acwl`/`cmlh`/`cmlv`); these are alternative sample-environment stages present in source but not mapped to Assets in this cut (`SAMPLE-2`).
