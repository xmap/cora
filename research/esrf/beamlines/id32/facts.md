# Extracted facts: ID32

Candidate device facts for `id32` (ESRF ID32, soft X-ray RIXS / XMCD / XES). Candidates only; confirm every row before modeling. Source: the public ID32 BLISS Beacon config (`gitlab.esrf.fr/id32/beamline_configuration`, commit `e14bef4`, last activity 2026-05-27). Every value is carried `confirm` until ID32 staff verify it: a config snapshot is strong evidence, not a CORA-owned fact. Handles are BLISS object names and Tango device URLs (the descriptor `pv` slot); ESRF runs BLISS / Tango / IcePAP, not EPICS.

!!! note "Retrospective alignment, not net-new"
    ID32 is already a shipped ESRF deployment (`deployments/id32/beamline.yaml`), so this Tier-2 pass is a *reference and cross-check*, not a fresh scaffold. It is cross-checked against the shipped descriptor; the device map agrees with it, and the one cross-cut finding is recorded under new-family watch: ID32's RIXS and XES arms are grating-dispersive (the `SpectrometerArm` lineage, RIXS-1), which is a genuinely different optic from the ID28 IXS crystal-analyzer arm (EnergyAnalyzer, ANALYZER-1). The two ESRF inelastic beamlines reinforce *different* loose families, not the same one.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level BLISS handle the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding. ID32 has shared optics plus two endstations (RIXS and XMCD); the Enclosure column carries the config zone (optics / RIXS / XMCD).

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| StorageRing | StorageRing | `//acs:10000/fe/master/id32` (BLISS `machinfo`, MachInfo); emittance `//acs:10000/srdiag/beam-emittance/main-h` / `main-v` | (observe-only machine state; emh/emv counters) | optics | source | yes |
| FrontEndShutter | Shutter | `acs.esrf.fr:10000/fe/master/id32` (BLISS `fe`, TangoShutter FrontEnd) | (front-end shutter) | optics | source | yes |
| BeamShutters | Shutter | `id32/v-rv/16a`, `id32/v-rv/16b`, `id32/v-rv/19a`, `id32/v-rv/20a`, `id32/v-rv/20b`, `id32/v-rv/21b` (BLISS `sh_rv*`, TangoShutter, `EXPH/safshut.yml`) | (six vacuum safety shutters) | optics | source | yes |
| Undulators | InsertionDevice | `//acs:10000/id/master/id32` (BLISS `ESRF_Undulator`) | hu70ag=`HU70a_GAP`, hu70ap=`HU70a_PHASE`, hu70apo=`HU70a_POSOFFSET`, hu70ano=`HU70a_NEGOFFSET`; hu70cg=`HU70c_GAP`, hu70cp=`HU70c_PHASE`, hu70cpo/hu70cno; ps35bg=`PS35b_GAP` | optics | source | yes |
| Monochromator | GratingMonochromator | BLISS `pgm` (MonochromatorGrating, `MONO/monochromator_grating.yml`) | gratings XMCD_300/XMCD_900 (l/mm), RIXS_800/RIXS_1600; calc reals nu=`mroty`, psi=`groty`; energy `energy_pgm` | optics | optics | yes |
| BeamEnergy | PseudoAxis | BLISS `energy` / `energy_pgm` (GratingEnergyCalcMotor, `MONO/monochromator_grating_calc_motors.yml`) | energy (eV) over nu=`mroty`/psi=`groty`; undulator-tracked via `grating_tracker` | optics | optics | yes |
| Polarization | PseudoAxis | BLISS PolarizationPolicy (`MONO/monochromator_grating.yml`) | policies horizontal/vertical/linear/circular_plus/circular_minus over APPLE-II gap/phase/offset modes | optics | optics | yes |
| CffAxis | PseudoAxis | BLISS `rixs_cff_motor_ctrl` (CffMotorController, `RIXS/calc_motors/cff_rixs.yml`) | cff over nu=`mroty`, psi=`groty` | optics | optics | yes |
| PrimarySlits | Slit | BLISS `psh` / `psv` (`EXPH/slits/slit_pshg.yml`, `slit_psvg.yml`) | real pshall/psring (h), calc pshg/psho; v slit pair | optics | optics | yes |
| SecondarySlits | Slit | BLISS `ssh` / `ssv` (`EXPH/slits/slit_sshg.yml`, `slit_ssvg.yml`) | h/v gap + offset | optics | optics | yes |
| MonoSlits | Slit | BLISS `msh` / `msv` (`EXPH/slits/slit_mshg.yml`, `slit_msvg.yml`) | h/v gap + offset | optics | optics | yes |
| BeamViewers | Screen (?) | BLISS EBV / BpmController (`beamviewers/beamviewers.yml`); cameras `id32/limaccds/{diagon,dg2,dg3,dg4,dg5a,dg5b,dg6a,dg7b,bva,bvb,microscope}` | dg1..dg7 diagnostic viewers + diodes (dgN_diode); exit-slit bva/bvb; on-axis microscope | optics | diagnostics | yes |
| RIXS_Diffractometer | Goniometer | BLISS `fourc` (DiffE4CH, geometry E4CH, `RIXS/diffractometer.yml`) | real tth=`$tth`, omega=`$th`, chi=`$chi`, phi=`$phi`, energy=`$energy` (iceid323 th/chi/phi); pseudo H/K/L/Q | RIXS | sample | yes |
| RIXS_SampleManipulator | LinearStage | `id32/hexapode/rfo` (BLISS `hexa_rfo`, esrf_hexapode) + `e753id32-rfo:50000` (BLISS `rfopictrl`, PI_E753, `RIXS/rfo_pi753.yml`) | hexapod rfox/rfoy/rfoz/rforotx/rforoty/rforotz; PI piezo rfopi (closed-loop) | RIXS | sample | yes |
| RIXS_SpectrometerArm | SpectrometerArm | BLISS `rixs_spectro` (SpectrometerArmsController, `RIXS/calc_motors/spectro_rixs.yml`) | real detx/detz/grtx (iceid324); virtual r1/r2; grating modes RIXS_2500 (gr2roty), RIXS_1400 (gr1roty), Rowland radius ~122000 | RIXS | detection | yes |
| RIXS_Polarimeter | PolarizationAnalyzer | `iceid324` (IcePAP host) | thpol=`addr` (line 141), chipol, zpol, ypol, tthpol (scattered-beam polarization-analysis block) | RIXS | detection | yes |
| RIXS_Detector | Camera | `id32/limaccds/andor_1` (BLISS `andor1`, Lima); temp counters `id32/andor/andor_1` | Andor CCD (tandor1 temperature, spandor1 setpoint) | RIXS | detection | yes |
| XMCD_Magnet | Magnet | `id32/cryogenic_magnet_ps/xmcd1` (BLISS `mps`, CryogenicPSController); serial `tango://id32/Serialrp_232/lid323_ttyR33` | field axis `magnet`; 9 T coil (max_field 9.0203, 0.04909 T/A) + 4 T coil (max_field 4.0504); counters target_field/magnet_field | XMCD | sample | yes |
| XMCD_NeedleValve | FlowController (?) | `tango://id32/Serialrp_232/lid323_ttyR34` (BLISS `nvalve_ctrl`, NeedleValveController) | nvalve axis (encoder_step_size 9.6 mm); nvpress pressure counter (mBar) | XMCD | sample | yes |
| XMCD_HeMassFlow | FlowController | `tango://id32/flowbus/xmcd` / `xmcd2` (BLISS `mfc_xmcd` / `mfc_xmcd2`, Bronkhorst) | heflow_xmcd / heflow_xmcd2 (He mass-flow) | XMCD | sample | yes |
| XMCD_SampleManipulator | LinearStage | `id32/hexapode/hrm` (BLISS `hexa_hrm`, esrf_hexapode) + PI_E753 (`XMCD/hrm_pi753.yml`); + `id32/hexapode/vrm` (BLISS `hexa_vrm`) | hrmx/hrmy/hrmz/hrmrotx/hrmroty/hrmrotz; vrm hexapod stack | XMCD | sample | yes |
| XMCD_VTI_TempController | TemperatureController | `id32/regulation/ls336_hfm_in_A..D`, `ls336_hfm_out_1` (BLISS `ls336_hfm_*`, LakeShore336TangoInput + SoftLoop, `XMCD/lakeshore336_hfm.yml`) | VTI loop: A=hex, B=helium_pot, C, D=sam; SoftLoop P40 I10 D0 | XMCD | sample | yes |
| XMCD_CoilDiag_TempController | TemperatureController | `id32/regulation/ls340_hfm_in_A..D*` (BLISS `ls340_hfm_*`, TangoInput, `XMCD/lakeshore340_hfm.yml`) | coil/shield diagnostics: A=base_magnet_shell, B=helium_reservoir, C1/C2=9T coils, C3/C4=4T coils, D1/D2=shields | XMCD | sample | yes |
| XES_SpectrometerArm | SpectrometerArm | BLISS `xes_spectro` (SpectrometerArmsController, `XMCD/calc_motors/spectro_xes.yml`) | real xesdetx/xesdetz/xesgrtx (iceid329); virtual xesr1/xesr2; grating modes XES_1200 (xesgrot, radius 26055), XES_empty | XMCD | detection | yes |
| XMCD_Detector | Camera | `id32/limaccds/andor_2` (BLISS `andor2`, Lima); temp counters `id32/andor/andor_2` | Andor CCD (tandor2 temperature, spandor2 setpoint) | XMCD | detection | yes |
| XMCD_Electrometers | GenericProbe (?) | BLISS Keithley `XMCD/keithley2000.yml`, `keithley2450.yml`, `keithley428.yml`, `keithley6221.yml`, `keithley6487.yml`, `keithley6517A.yml`; SR830 lock-in (`XMCD/sr830.yml`); MCCE (`XMCD/mcce.yml`); VAPS (`XMCD/vaps_electrometer.yml`) | sample-current / drain-current readout chain for XMCD TEY/TFY | XMCD | detection | yes |
| AnalyzerCounters | GenericProbe (?) | `RIXS/p201_lid322.yml`, `XMCD/p201_lid323.yml`, `EXPH/p201_lid321.yml` (BLISS P201 CT2 cards) | beam-monitor / detector counting channels per endstation | (per zone) | detection | yes |
| TimingControllers | TimingController (?) | BLISS `musst_mono` (`EXPH/musst_mono.yml`), `musst_xmcd` (`XMCD/musst_xmcd.yml`), `musst_diff` (`DIFF/musst_diff.yml`) | MUSST timing masters per endstation (energy-scan / fly gating) | (per zone) | detection | yes |

The device-level handles above are read verbatim from the cloned config (`machine/`, `MONO/`, `EXPH/`, `RIXS/`, `XMCD/`, `DIFF/`, `beamviewers/`, `lima/`, `icepap/`). The RIXS arm reals (`detx`/`detz`/`grtx`) live on `icepap/iceid324.yml`; the XES arm reals (`xesdetx`/`xesdetz`/`xesgrtx`) on `icepap/iceid329.yml`; the diffractometer reals (`th`/`chi`/`phi`) on `icepap/iceid323.yml`; the polarimeter axes (`thpol`/`chipol`/`zpol`/`ypol`/`tthpol`) on `icepap/iceid324.yml`. There is a third endstation directory in the config (`DIFF/`, `EXPH/`, `PUMA/`) carrying a diffraction / general-purpose station and shared optics; this cut models the two main published endstations (RIXS, XMCD) plus shared optics, matching the shipped descriptor (DIFF-2).

## Role hints

- **Positioner**: the PGM grating axes (nu/psi), all slit assemblies, the 4-circle diffractometer (tth/omega/chi/phi), the RIXS / XMCD hexapod + PI piezo sample manipulators, the two spectrometer arms (detx/detz/grtx), and the RIXS polarimeter block. Mix of `esrf_hexapode`, `PI_E753`, `IcePAP`, and BLISS calc controllers (`MonochromatorGrating`, `SpectrometerArmsController`, `DiffE4CH`).
- **Sensor**: the EBV beamviewer diodes, the P201 CT2 counters, the Andor CCD temperature readouts, the magnet field counters, the needle-valve pressure, and the XMCD electrometer chain (Keithley / SR830 / MCCE / VAPS) reading sample / drain current.
- **Detector**: the two Andor CCDs (RIXS andor1, XES andor2).
- **Regulator** (settable continuous setpoint): the 9 T `CryogenicPSController` magnet (a settable field axis, the Magnet lineage), the VTI LakeShore 336 SoftLoop (TemperatureController), the He Bronkhorst mass-flow controllers and the cryogenic needle valve (FlowController lineage). The LakeShore 340 coil-diagnostic chain is read-only (`TangoInput` only), a Sensor not a Regulator.
- **Controller / timing**: the three MUSST cards (`musst_mono` / `musst_xmcd` / `musst_diff`) are the energy-scan / fly gating masters (TimingController-role hint).

## Trust hints

The ID32 Beacon config carries no queue-server / user-group-permissions artifact (BLISS has no equivalent of the NSLS-II `user_group_permissions.yaml`). Authorization at ESRF is a Tango / BLISS-session concern not expressed in the device database. The orchestration layer CORA would conduct over is the BLISS sequences (`sessions/scripts/*.py`, e.g. `sequences/scan_energy.yml`), consistent with the ESRF survey; no binding here.

## New-family watch

Nothing to coin from ID32 alone. Bindings to flag, all reinforcing already-graduated or already-held loose families (the shipped descriptor's reading is confirmed by source):

- **SpectrometerArm (loose, RIXS-1), reinforced and disambiguated.** ID32 carries the same `SpectrometerArmsController` class instantiated twice (`rixs_spectro` + `xes_spectro`), both grating-dispersive Rowland arms (grating modes, Rowland radius), so ID32 reaches the `SpectrometerArm` rule-of-three on its own (RIXS arm + XES arm) plus the SIX precedent. HELD per the owner decision (RIXS-1). The cross-cut with ID28: ID28's IXS arm is a *crystal* analyzer (`TwoThetaMultilayer` + `InclinedAnalyser`), which the catalog assigns to the loose `EnergyAnalyzer` (ANALYZER-1), NOT `SpectrometerArm`. So the two ESRF inelastic beamlines reinforce *different* loose families: ID32 = grating SpectrometerArm (RIXS-1), ID28 = crystal EnergyAnalyzer (ANALYZER-1). This is the recurrence-relevant finding; see `recurrence.md`. Do not coin either from ESRF alone.
- **Magnet (loose, MAG-1).** The 9 T / 4 T `CryogenicPSController` binds the loose `Magnet` family (the third consumer after 4-ID + i10-1 per the shipped descriptor). HELD; do not coin.
- **PolarizationAnalyzer (loose, POL-2).** The RIXS scattered-beam polarimeter block (`thpol`/`chipol`/`zpol`/`ypol`/`tthpol` on iceid324) binds the loose `PolarizationAnalyzer` (the third consumer after 4-ID + i10). HELD; do not coin.
- **GratingMonochromator (graduated).** The PGM binds the graduated `GratingMonochromator` (the SIX / CSX / ESM soft X-ray precedent); ID32 is a further consumer, nothing to coin.
- **FlowController (graduated).** The Bronkhorst He mass-flow controllers and the cryogenic needle valve bind the graduated `FlowController` (settable-setpoint flow). The needle valve is a `(?)` pending confirm it presents a settable flow / pressure setpoint vs a bare position axis.
- **StorageRing (loose, MACHINE-1), TimingController (?) for MUSST, GenericProbe (?) for the electrometer / P201 chains.** Same loose / fallback bindings as ID28; held, not coined.

## Deferred / absent

- **The third endstation (`DIFF/`, `PUMA/`, `EXPH/` general station).** The config carries a diffraction station (`DIFF/`, DiffE4CH-adjacent) and a PUMA / general-purpose experimental setup beyond the two published RIXS / XMCD endstations. This cut models RIXS + XMCD + shared optics to match the shipped descriptor; the third station is deferred (`DIFF-2`), present in source, not modeled here.
- **PSS permit signals and hutch interlocks (`PSS-1`, `ENC-1`).** The config carries the shutters (`fe`, `sh_rv*` on `id32/v-rv/*`) but not the personnel-safety permit leaves behind them, nor a clean hutch-zone grouping. The Enclosure column is inferred from the config directory layout (optics / RIXS / XMCD).
- **WAGO / opiom / FLY / simulation devices not mapped.** The `wago` crates (`wcid32c..h`, referenced by the beamviewers), the `opiom_mux/` multiplexers, the `FLY/` LakeShore 336 fly controllers, the `helium_recovery` machine device, and the `sim_*` simulation devices are infrastructure / test scaffolding or sub-device detail, not top-level beamline Assets; deferred (`INFRA-1`).
- **He balance (`RIXS/i5.yml`).** A Preciamolen I5 weighing balance + HeBalance (liquid-helium bottle weight tracking) is in source; it is cryogen-logistics instrumentation, not a beam-path Asset, deferred (`SUP-1`).
- **Undulator period / APPLE-II detail (`SRC-1`).** The twin APPLE-II undulators are named `HU70a` / `HU70c` (70 mm period implied) with a `PS35B` (35 mm) third device; the exact period, segment count, and which feeds which mode / polarization are not fully pinned in the config.
