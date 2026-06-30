# Extracted facts: CoSAXS (B310A)

Candidate device facts for `cosaxs` (MAX IV B310A, coherent / small-angle X-ray scattering: SAXS / WAXS, coherent SAXS). Candidates only; confirm every row before modeling. Source: the public `maxiv-science/contrast` DAQ framework (`beamlines/cosaxs/cosaxs.py`, read at commit `8e787ac`, 2026-01). Every value is carried `confirm` until CoSAXS staff verify it: the contrast beamline file is strong evidence, not a CORA-owned fact. Handles are Tango device addresses (`domain/family/member`, several fully qualified with the `b-v-cosaxs-csdb-0:10000/` Tango-host prefix) and Tango-pool names, carried in the descriptor `pv` slot; MAX IV runs Tango + Sardana, not EPICS.

!!! note "Source idiom and the active-vs-commented rule"
    Like NanoMAX, CoSAXS declares devices as `contrast` Python objects (`TangoMotor(device='...', name='...')`, `EigerTango(device_name='...')`). Commented-out variants exist (borrowed-from-NanoMAX sample piezos, a Thorlabs pinhole stage, `sma6`/`theta` spare axes); ONLY active (uncommented, not-in-docstring) device handles are recorded here, confirmed by stripping triple-quoted blocks and `#` lines. The Tango address case is preserved verbatim (the config mixes `b310a-...` and `B310A-...`). Many handles carry an explicit Tango database host prefix `b-v-cosaxs-csdb-0:10000/`; this is recorded verbatim as part of the handle.

!!! note "Single endstation"
    CoSAXS is one experimental station (B310A-E / B310A-E01) on a coherent SAXS optics train (B310A-O02), unlike NanoMAX's two endstations. The long SAXS detector sits in a flight tube on a translating table.

## Device inventory

Asset granularity: one row per stage / assembly, the device-level handle the descriptor binds, component axes as sub-detail read verbatim from source. Two-bender mirrors group their bend/pitch/translation axes into the one mirror Asset; the BCU01 attenuator + beamstop block groups its `bcu01-*` axes. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

### Source + optics (B310A-O02 / front end)

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Undulator | InsertionDevice | `b-v-cosaxs-csdb-0:10000/motor/gap_ctrl/1` | ivu_gap (4.599-49.9) | B310A | source | yes |
| BeamEnergy | PseudoAxis | `b-v-cosaxs-csdb-0:10000/pm/mono_bragg_ctrl/1` | energy (mono bragg pseudo, 5000-32000 eV) | B310A-O | optics | yes |
| VerticalFocusingMirror1 | Mirror | `b-v-cosaxs-csdb-0:10000/b310a-o02/opt/mir-01-bend01` | bend01=`mir-01-bend01`; pit=`mir-01-pit`; row translation x=`mrch-01-x`, y=`mrch-01-y` (VFM, two-bender, first) | B310A-O02 | optics | yes |
| VerticalFocusingMirror2 | Mirror | `b-v-cosaxs-csdb-0:10000/b310a-o02/opt/mir-02-bend01` | bend01=`mir-02-bend01`; pit=`mir-02-pit`; y=`mir-02-y` (VFM, two-bender, second) | B310A-O02 | optics | yes |
| HorizontalFocusingMirror1 | Mirror | `b-v-cosaxs-csdb-0:10000/b310a-o02/opt/mir-03-bend01` | bend01=`mir-03-bend01`; bend02=`mir-03-bend02`; pit=`mir-03-pit` (HFM, two-bender, first) | B310A-O02 | optics | yes |
| HorizontalFocusingMirror2 | Mirror | `b-v-cosaxs-csdb-0:10000/b310a-o02/opt/mir-04-bend01` | bend01=`mir-04-bend01`; bend02=`mir-04-bend02`; pit=`mir-04-pit`; x=`mir-04-x`; row translation y=`mrch-02-y` (HFM, two-bender, second) | B310A-O02 | optics | yes |
| CoherenceSlit | Slit | `b-v-cosaxs-csdb-0:10000/b310a-o02/opt/slit-01-xl` | blades xl/xr/yb/yt=`slit-01-{xl,xr,yb,yt}`; gap/pos pseudos `pm/o02_v_slit1_ctrl/{1,2}` (xgap/xpos), `pm/o02_h_slit1_ctrl/{1,2}` (ygap/ypos) | B310A-O02 | optics | yes |

### Experimental station (B310A-E01 / B310A-E02)

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| UHVSlit1 | Slit | `b-v-cosaxs-csdb-0:10000/b310a-e01/opt/slit-01-xr` | blades xr/xl/yt/yb=`slit-01-{xr,xl,yt,yb}` | B310A-E01 | optics | yes |
| UHVSlit2 | Slit | `b-v-cosaxs-csdb-0:10000/b310a-e01/opt/slit-02-xr` | blades xr/xl/yt/yb=`slit-02-{xr,xl,yt,yb}` | B310A-E01 | optics | yes |
| LastSlit | Slit | `b-v-cosaxs-csdb-0:10000/b310a-e01/opt/slit-03-xr` | blades xr/xl/yt/yb=`slit-03-{xr,xl,yt,yb}` (last slit before lens array / pinhole / sample) | B310A-E01 | optics | yes |
| AttenuatorBeamstopUnit | Filter | `b-v-cosaxs-csdb-0:10000/b310a-e01/dia/bcu01-x1pz` | absorber pushers x1pz/x2pz/x3pz/x4pz (Al / Ti foil ladders) + beamstop bsxpz/bsypz=`bcu01-{bsxpz,bsypz}` (BCU01) | B310A-E01 | optics | yes |
| GraniteTable | LinearStage | `b-v-cosaxs-csdb-0:10000/b310a-e01/dia/tab-01-x` | x=`tab-01-x`; y=`tab-01-y` | B310A-E01 | sample | yes |
| SampleStage | LinearStage | `b-v-cosaxs-csdb-0:10000/b310a-e01/dia/sams-04-x` | Huber sample_x=`sams-04-x` (10-290); sample_y=`sams-04-y` (10-80) | B310A-E01 | sample | yes |
| SampleTiltStack | LinearStage | `b310a-e01/ctl/pzsscu-02` (Smaract MCS2, 6 active axes) | sz (axis 0, long linear); sx (axis 1); sy (axis 2); pinx (axis 3); piny (axis 4); sr (axis 5, rotation) | B310A-E01 | sample | yes |
| DetectorTable | LinearStage | `b-v-cosaxs-csdb-0:10000/b310a-e02/dia/tab-02-x` | det_x=`tab-02-x` (42-200); det_y=`tab-02-y` (36-199); det_z=`motor/cosaxs_flight_ctrl/26` (flight-tube translation, -569.65-13865) | B310A-E02 | detection | yes |
| AreaDetectorEiger4M | Camera | `B310A-E/DIA/det-01` (EigerTango) | (Eiger 4M SAXS area detector; hdf entry/instrument/eiger/data) | B310A-E02 | detection | yes |
| IonChamberElectrometer | FluxMonitor | `172.16.198.48` (AlbaEM, host) | alba0 electrometer (I0 / It / diode channels) | B310A-E01 | detection | yes |
| TimingController | TimingController | `b-cosaxs-pandabox-0` (PandaBox, host) | panda0: FMC ADC capture (I0_m/It_m via FMC_IN), fast-scan trigger | B310A-E01 | detection | yes |

The device-level handles above are read verbatim from `cosaxs.py` (active lines only). The Smaract MCS2 controller `b310a-e01/ctl/pzsscu-02` hosts the six active sample-stack axes shown (axes 6/7, `sma6`/`theta`, are commented out). The detector / pandabox / albaem hosts (`B310A-E/DIA/det-01`, `b-cosaxs-pandabox-0`, `172.16.198.48`) are an EigerTango device name and AlbaEM / PandaBox network hosts respectively, recorded verbatim. Note `vfm1_bend01`/`vfm1_bend02` and `vfm2_bend01`/`vfm2_bend02` bind the SAME address in source (a likely copy-paste in the config, `b310a-o02/opt/mir-01-bend01` / `mir-02-bend01` twice); recorded as-is and flagged (`MIR-1`).

## Role hints

- **Positioner**: the two HFM + two VFM two-bender mirrors, the coherence slit + three UHV/last slits, the BCU01 absorber/beamstop pushers, the Huber sample stages, the MCS2 sample tilt/rotation stack, the granite table, and the detector flight-tube table. Constructor classes `TangoMotor` and `SmaractLinearMotor_MCS2` / `SmaractRotationMotor_MCS2`.
- **Sensor**: the AlbaEM electrometer (I0 / It / diodes, the SAXS flux chain), the PandaBox FMC-ADC pseudo-detector.
- **Detector**: the Eiger 4M SAXS area detector.
- **Controller / timing**: the PandaBox (`panda0`) is the fast-scan trigger + FMC-ADC capture timing master; a TimingController-role hint (the same role as NanoMAX's panda0 and the NSLS-II Zebra).
- **No Regulator / settable-setpoint actuator** is active (no temperature / flow controller in the file).

## Trust hints

The contrast file carries no queue-server / user-group-permissions artifact. It references a `MaxivScheduler` (shutter-pause; commented out with a note that the scheduler DB host `g-v-csproxy-0.maxiv.lu.se:10303` was unreachable) and a `ScicatRecorder` (commented out, Kafka connect failure). The named shutters (`b310a-fe/vac/ha-01`, `b310a-fe/pss/bs-01`, `b310a-o/pss/bs-01`) are the PSS / front-end permit handles to confirm (`PSS-1`), not instantiated as live Assets. The orchestration CORA's edge would conduct over is contrast itself (`SoftwareScan` / `Ct`); SciCat is the data-of-record contest. No binding here.

## New-family watch

Nothing to coin from CoSAXS. All bindings map to existing catalog families and **reinforce the NanoMAX pass** (the cross-MAX-IV recurrence signal):

- **Mirror, Slit, InsertionDevice, Filter, LinearStage, PseudoAxis, Camera, FluxMonitor, TimingController (all graduated).** CoSAXS is a further consumer of each; with NanoMAX this brings several to two MAX IV beamlines (see `recurrence.md`).
- **PandaBox -> TimingController (?).** Same binding-confirm as NanoMAX; PandaBox now sighted at two MAX IV beamlines (NanoMAX + CoSAXS), reinforcing the graduated `TimingController` (still a binding-confirm vs GenericProbe, not a new coin).
- **AlbaEM -> FluxMonitor.** Same as NanoMAX; two MAX IV beamlines now.
- **Two-bender mirror -> Mirror (not a new family).** Each focusing mirror (VFM1/VFM2/HFM1/HFM2) is a `Mirror` Asset; the two-bender + row-translation axis set is a per-Asset settings difference, not a Family split (the catalog Mirror precedent). CoSAXS has four mirror Assets, NanoMAX two; no KB / bender family coined.
- **BCU01 attenuator+beamstop -> Filter (?).** The beam-conditioning unit composes absorber foil ladders (Filter) with a beamstop (a LinearStage / BeamStop). Modeled as one `Filter` Asset here with the beamstop axes as co-hosted sub-detail; confirm whether the beamstop should be a separate Asset (`BCU-1`).

## Deferred / absent

- **PSS permit signals and shutters (`PSS-1`).** The commented `MaxivScheduler` names the real shutter devices (`b310a-fe/vac/ha-01`, `b310a-fe/pss/bs-01`, `b310a-o/pss/bs-01`); not instantiated as live Assets. The fast shutter (`fsopen`/`fsclose`) is driven via PandaBox.
- **Mirror address duplication (`MIR-1`).** `vfm1_bend02` reuses `mir-01-bend01` and `vfm2_bend02` reuses `mir-02-bend01` (identical to their `bend01` siblings) in source, a likely config copy-paste; the true second-bender address per VFM needs staff confirm.
- **Borrowed / temporary sample piezos.** Commented-out NanoMAX-borrowed `LC400Motor` and PI `E727Motor` sample piezos (`b310A/ctl/pzcu-users-01`, `B310A/CTL/PZCU-01`) and a Thorlabs pinhole stage (`sams-01-x/y`); not in the active config, deferred (`SAMPLE-2`).
- **SciCat / scheduler integration.** Both the `ScicatRecorder` and the `MaxivScheduler` are present but disabled in source (Kafka / DB connect failures noted in comments); a seam observation, not a device.
- **Spare MCS2 axes.** `sma6` (axis 6) and `theta` (axis 7) on the sample MCS2 are commented out; not modeled.
