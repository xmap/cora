# Extracted facts: polar-bits

Machine-extracted candidate facts for `4-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| btetramm | TetrAMMRO (?) | `4idbSoft:TetrAMM:` | 4-ID-B | detection | detector, xbpm, baseline, 4idb | yes |
| ctr8 | CustomMeasCompCtr (?) | `4idCTR8_1:` | 4-ID-B | detection | detector, 4idb, 4idg, 4idh, baseline | yes |
| eiger | Eiger1MDetector (?) | `4idEiger:` | 4-ID-G | detection | 4idg, detector | yes |
| flagcam_hhl | VimbaDetector (?) | `4idaPostMirrBeam:` | 4-ID-A | detection | camera, detector, flag | yes |
| flagcam_mono | VimbaDetector (?) | `4idaPostMonoBeam:` | 4-ID-A | detection | camera, detector, flag | yes |
| flagcam_toro | VimbaDetector (?) | `4idbPostToroBeam:` | 4-ID-B | detection | camera, detector, flag | yes |
| flagcam_xeye | VimbaDetector (?) | `4idXrayEye:` | ? | detection | camera, detector, flag | yes |
| gsydor | SydorEMRO (?) | `4idgSydor:T4U_BPM:` | 4-ID-G | detection | detector, xbpm, baseline, 4idg | yes |
| hsydor | SydorEMRO (?) | `4idhSydor:T4U_BPM:` | 4-ID-H | detection | detector, xbpm, baseline, 4idh | yes |
| scaler1 | GenericProbe | `4idCTR8_1:scaler1` | 4-ID-B | detection | detector, scaler, 4idb, 4idg, 4idh | yes |
| scaler2 | GenericProbe | `4idCTR8_1:scaler2` | 4-ID-B | detection | detector, scaler, 4idb, 4idg, 4idh | yes |
| sgz_vortex | SGZVortex (?) | `4iddMZ0:` | 4-ID-D | detection | detector | yes |
| aps_xbpm | MyXBPM (?) | `S04` | ? | source | core, source, baseline | yes |
| ashutter | Shutter | - | ? | source | core, shutter, baseline | yes |
| bfilter | APSFilter (?) | `4idbSoft:filter:` | 4-ID-B | source | 4idb, filter, baseline | yes |
| bkb | Mirror | rot=`4idbSoft:m15`; x=`4idbSoft:m16` | 4-ID-B | source | 4idb, optics, baseline | no |
| bmag | Magnet2T (?) | - | 4-ID-B | source | 4idb, magnet, baseline | yes |
| bshutter | Shutter | - | ? | source | core, shutter, baseline | yes |
| bslt | Slit | bot=`4idbSoft:m10`; inb=`4idbSoft:m12`; out=`4idbSoft:m13`; top=`4idbSoft:m11` | 4-ID-B | source | 4idb, slit, baseline | yes |
| chopper | ChopperDevice (?) | `4idChopper:` | ? | source | baseline | yes |
| comp | GEController (?) | `4idPace:PC1:` | ? | source | high pressure, baseline | yes |
| crl | CRLClass (?) | `4idPyCRL:CRL4ID:` | 4-ID-G | source | 4idg, 4idh, optics, track_energy, baseline | yes |
| decomp | GEController (?) | `4idPace:PC2:` | ? | source | high pressure, baseline | yes |
| diamond_window | WindowStages (?) | x=`4idbSoft:m1`; y=`4idbSoft:m2` | 4-ID-B | source | core, baseline | yes |
| dm_experiment | Signal (?) | - | ? | source | core, dm, baseline | yes |
| dm_workflow | DM_WorkflowConnector (?) | - | ? | source | core, dm, baseline | yes |
| emag | Magnet2T (?) | - | 4-ID-B | source | 4idb, magnet, baseline | yes |
| energy | EnergySignal (?) | - | ? | source | core, energy device, baseline | yes |
| flagmotor_hhl | EpicsMotor (?) | `4idVDCM:m6` | ? | source | motor, flag, baseline | yes |
| flagmotor_mono | EpicsMotor (?) | `4idVDCM:m7` | ? | source | motor, flag, baseline | yes |
| flagmotor_toro | EpicsMotor (?) | `4idbSoft:m3` | 4-ID-B | source | motor, flag, baseline | yes |
| gfilter | APSFilter (?) | `4idPyFilter:FL1:` | 4-ID-G | source | 4idg, filter, baseline | yes |
| gkb | GKBDevice (?) | `4idgKB:` | 4-ID-G | source | 4idg, optics, baseline, kb | yes |
| gmag | KepcoDevice (?) | `4idkepco:` | 4-ID-K | source | baseline | yes |
| gslt | Slit | bot=`4idgSoft:m43`; inb=`4idgSoft:m45`; out=`4idgSoft:m46`; top=`4idgSoft:m44` | 4-ID-G | source | 4idg, slit, baseline | yes |
| gxbpm | XBPM (?) | x=`4idgSoft:m48`; y=`4idgSoft:m47` | 4-ID-G | source | 4idg, baseline | yes |
| hfilter | APSFilter (?) | `4idPyFilter:FL2:` | 4-ID-H | source | 4idh, filter, baseline | yes |
| hhl_mirror | Mirror | curvature=`4idHHLM:pm3`; ds_bend=`4idHHLM:m5`; elipticity=`4idHHLM:pm4`; pitch=`4idHHLM:pm2`; us_bend=`4idHHLM:m4`; x=`4idHHLM:pm1`; x1=`4idHHLM:m2`; x2=`4idHHLM:m3`; y=`4idHHLM:m1` | ? | source | core, mirror, baseline | yes |
| hkb | HKBDevice (?) | `4idhKB:` | 4-ID-H | source | 4idh, optics, baseline, kb | yes |
| hslt | Slit | bot=`4idhSoft:m10`; inb=`4idhSoft:m13`; out=`4idhSoft:m12`; top=`4idhSoft:m11` | 4-ID-H | source | 4idh, slit, baseline | yes |
| huber_euler | CradleDiffractometer (?) | x=`4idgSoft:m40`; y=`4idgSoft:m41`; z=`4idgSoft:m42` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_euler_psi | CradleDiffractometerPSI (?) | `4idgSoft:` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_hp | HPDiffractometer (?) | basex=`4idgSoft:m7`; basey=`4idgSoft:SMBaseY`; basey_motor=`4idgSoft:m9`; basez=`4idgSoft:SMBaseZ`; basez_motor=`4idgSoft:m8`; chi=`4idgSoft:m5`; phi=`4idgSoft:m6`; sample_tilt=`4idgSoft:m11`; x=`4idgSoft:m12`; y=`4idgSoft:m14`; z=`4idgSoft:m13` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_hp_psi | HPDiffractometerPSI (?) | `4idgSoft:` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| hxbpm | XBPM (?) | x=`4idhSoft:m6`; y=`4idhSoft:m5` | 4-ID-H | source | 4idh, baseline | yes |
| i0g | I04idg (?) | x=`4idgSoft:m52`; y=`4idgSoft:m53` | 4-ID-G | source | 4idg, baseline | yes |
| i0h | I04idh (?) | x=`4idhSoft:m20`; y=`4idhSoft:m21` | 4-ID-H | source | 4idh, baseline | yes |
| labjack_4ida | CustomLabJackT7 (?) | `4idaSoft:LJ:` | 4-ID-A | source | core, baseline | yes |
| labjack_4idb | CustomLabJackT7 (?) | `4idbSoft:LJ:` | 4-ID-B | source | 4idb, baseline | yes |
| laser | VentusLaser (?) | `4idhSoft:LQE1:` | 4-ID-H | source | 4idh, baseline | yes |
| magnet911 | Magnet911 (?) | `4idhSoft:` | 4-ID-H | source | 4idh, magnet, baseline | yes |
| midtable_4idb | Table4idb (?) | x_ds=`4idbSoft:m8`; x_us=`4idbSoft:m5`; y_ds_in=`4idbSoft:m7`; y_ds_out=`4idbSoft:m6`; y_us=`4idbSoft:m4` | 4-ID-B | source | 4idb, baseline | yes |
| mono | Monochromator | chi2=`4idVDCM:m5`; crystal_select=`4idVDCM:m2`; th=`4idVDCM:m1`; thf2=`4idVDCM:m4`; y2=`4idVDCM:m3` | ? | source | core, monochromator, energy device, baseline | yes |
| mono_feedback | MonoFeedback (?) | `4idbSoft:` | 4-ID-B | source | core, monochromator, feedback, baseline | yes |
| monoslt | Slit | bot=`4idVDCM:m13`; inb=`4idVDCM:m15`; out=`4idVDCM:m16`; top=`4idVDCM:m14` | ? | source | core, slit, baseline | yes |
| piezo_jena | PiezoJena (?) | `4idgSoftX:asyn_MOXA_G:2` | 4-ID-G | source | 4idg, baseline | yes |
| pol | PolAnalyzer (?) | th=`4idbSoft:m9`; y=`4idbSoft:m17` | 4-ID-B | source | 4idb, baseline | yes |
| pr1 | PRDevice (?) | th=`4idam4`; x=`4idam1`; y=`4idam2` | 4-ID-A | source | core, phase retarder, energy device, track_energy, baseline | yes |
| pr2 | PRDevice (?) | th=`4idam9`; x=`4idam6`; y=`4idam7` | 4-ID-A | source | core, phase retarder, energy device, track_energy, baseline | yes |
| pr3 | PRDeviceBase (?) | th=`4idam12`; x=`4idam10`; y=`4idam11` | 4-ID-A | source | core, phase retarder, energy device, track_energy, baseline | yes |
| preamp_4idbI | LocalPreAmp (?) | `4idbSoft:A4` | 4-ID-B | source | 4idb, preamp, baseline | yes |
| preamp_4idbI0 | LocalPreAmp (?) | `4idbSoft:A3` | 4-ID-B | source | 4idb, preamp, baseline | yes |
| preamp_4idgI | LocalPreAmp (?) | `4idgSoftX:A2` | 4-ID-G | source | 4idg, preamp, baseline | yes |
| preamp_4idgI0 | LocalPreAmp (?) | `4idgSoftX:A1` | 4-ID-G | source | 4idg, preamp, baseline | yes |
| preamp_4idhI0 | LocalPreAmp (?) | `4idhSoft:A1` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| preamp_4idhI1 | LocalPreAmp (?) | `4idhSoft:A2` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| preamp_4idhI2 | LocalPreAmp (?) | `4idhSoft:A3` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| qxscan_setup | QxscanParams (?) | - | ? | source | core, qxscan, energy device, baseline | yes |
| ringlight | Ringlight (?) | `RINGLIGHT:` | 4-ID-G | source | 4idg, baseline | yes |
| srs810 | LockinDevice (?) | `4idbSoft:SRS810:1:` | 4-ID-B | source | core, baseline | yes |
| status_aps | StatusAPS (?) | - | ? | source | core, source, status, baseline | yes |
| status_polar | Status4ID (?) | `S04ID-PSS:` | ? | source | core, status, baseline | yes |
| t_mirror | Mirror | `4idbToro:` | 4-ID-B | source | core, optics, mirror, baseline | yes |
| table_4idh | Table4idh (?) | x_ds=`4idhSoft:m2`; x_us=`4idhSoft:m1`; y_ds=`4idhSoft:m4`; y_us=`4idhSoft:m3` | 4-ID-H | source | 4idh, table, baseline | yes |
| temp_336_4idg | LakeShore336Device (?) | `4idgSoft:LS336:TC1:` | 4-ID-G | source | 4idg, temperature, baseline | yes |
| temp_340_4idg | LakeShore340Device (?) | `4idgSoftX:LS340:TC1:` | 4-ID-G | source | 4idg, temperature, baseline | yes |
| undulators | InsertionDevice | `S04ID:` | ? | source | core, source, energy device, baseline | yes |
| wbslt | Slit | diag=`4idVDCM:m10`; hor=`4idVDCM:m9`; pitch=`4idVDCM:m11`; yaw=`4idVDCM:m12` | ? | source | core, slit, baseline | yes |

## Candidate enclosures

`4-ID-A`, `4-ID-B`, `4-ID-D`, `4-ID-G`, `4-ID-H`, `4-ID-K` (all inferred, confirm).

## Role hints (from labels)

`Controller`, `Detector`, `Positioner`

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Open confirms

- **aps_xbpm** (`id4_common.devices.aps_xbpm.MyXBPM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyXBPM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **ashutter** (`id4_common.devices.shutters.PolarShutter`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
- **bfilter** (`id4_common.devices.filters_device.APSFilter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'APSFilter'; needs a CORA Family
- **bmag** (`id4_common.devices.electromagnet.Magnet2T`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'Magnet2T'; needs a CORA Family
    - sx: FormattedComponent suffix resolved at runtime
    - sy: FormattedComponent suffix resolved at runtime
    - srot: FormattedComponent suffix resolved at runtime
    - mx: FormattedComponent suffix resolved at runtime
    - my: FormattedComponent suffix resolved at runtime
    - mrot: FormattedComponent suffix resolved at runtime
    - kepco: FormattedComponent suffix resolved at runtime
- **bshutter** (`apstools.devices.ApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - ophyd class 'ApsPssShutterWithStatus' not found in devices/*.py
- **bslt** (`id4_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **btetramm** (`id4_common.devices.quadems.TetrAMMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'TetrAMMRO'; needs a CORA Family
- **chopper** (`id4_common.devices.chopper_device.ChopperDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'ChopperDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - translation: FormattedComponent suffix resolved at runtime
- **comp** (`id4_common.devices.ge_controller.GEController`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'GEController'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **crl** (`id4_common.devices.crl_device.CRLClass`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CRLClass'; needs a CORA Family
    - ophyd class 'CRLClass' not found in devices/*.py
- **ctr8** (`id4_common.devices.usb_ctr8.CustomMeasCompCtr`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomMeasCompCtr'; needs a CORA Family
- **decomp** (`id4_common.devices.ge_controller.GEController`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'GEController'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **diamond_window** (`id4_common.devices.diamond_window_table.WindowStages`)
    - family is the ophyd class name 'WindowStages'; needs a CORA Family
- **dm_experiment** (`ophyd.Signal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'Signal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'Signal' not found in devices/*.py
- **dm_workflow** (`apstools.devices.DM_WorkflowConnector`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'DM_WorkflowConnector'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'DM_WorkflowConnector' not found in devices/*.py
- **eiger** (`id4_common.devices.ad_eiger1M.Eiger1MDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Eiger1MDetector'; needs a CORA Family
- **emag** (`id4_common.devices.electromagnet.Magnet2T`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'Magnet2T'; needs a CORA Family
    - sx: FormattedComponent suffix resolved at runtime
    - sy: FormattedComponent suffix resolved at runtime
    - srot: FormattedComponent suffix resolved at runtime
    - mx: FormattedComponent suffix resolved at runtime
    - my: FormattedComponent suffix resolved at runtime
    - mrot: FormattedComponent suffix resolved at runtime
    - kepco: FormattedComponent suffix resolved at runtime
- **energy** (`id4_common.devices.energy_device.EnergySignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EnergySignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **flagcam_hhl** (`id4_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_mono** (`id4_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_toro** (`id4_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_xeye** (`id4_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **flagmotor_hhl** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flagmotor_mono** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flagmotor_toro** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **gfilter** (`id4_common.devices.filters_device_avs.APSFilter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'APSFilter'; needs a CORA Family
- **gkb** (`id4_common.devices.kb_generic.GKBDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'GKBDevice'; needs a CORA Family
    - ophyd class 'GKBDevice' not found in devices/*.py
- **gmag** (`id4_common.devices.magnet_kepco_4idg.KepcoDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'KepcoDevice'; needs a CORA Family
- **gslt** (`id4_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **gsydor** (`id4_common.devices.quadems.SydorEMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SydorEMRO'; needs a CORA Family
    - conf: non-literal or absent component suffix
- **gxbpm** (`id4_common.devices.xbpm.XBPM`)
    - family is the ophyd class name 'XBPM'; needs a CORA Family
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
- **hfilter** (`id4_common.devices.filters_device_avs.APSFilter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'APSFilter'; needs a CORA Family
- **hhl_mirror** (`id4_common.devices.hhl_mirror.HHLMirror`)
    - enclosure unresolved from prefix or labels
    - fine_pitch: FormattedComponent suffix resolved at runtime
- **hkb** (`id4_common.devices.kb_generic.HKBDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'HKBDevice'; needs a CORA Family
    - ophyd class 'HKBDevice' not found in devices/*.py
- **hslt** (`id4_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **hsydor** (`id4_common.devices.quadems.SydorEMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SydorEMRO'; needs a CORA Family
    - conf: non-literal or absent component suffix
- **huber_euler** (`id4_common.devices.polar_diffractometer_hklpy2.CradleDiffractometer`)
    - family is the ophyd class name 'CradleDiffractometer'; needs a CORA Family
- **huber_euler_psi** (`id4_common.devices.polar_diffractometer_hklpy2.CradleDiffractometerPSI`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CradleDiffractometerPSI'; needs a CORA Family
    - ophyd class 'CradleDiffractometerPSI' not found in devices/*.py
- **huber_hp** (`id4_common.devices.polar_diffractometer_hklpy2.HPDiffractometer`)
    - family is the ophyd class name 'HPDiffractometer'; needs a CORA Family
    - nanox: FormattedComponent suffix resolved at runtime
    - nanoy: FormattedComponent suffix resolved at runtime
    - nanoz: FormattedComponent suffix resolved at runtime
    - xeryon: FormattedComponent suffix resolved at runtime
- **huber_hp_psi** (`id4_common.devices.polar_diffractometer_hklpy2.HPDiffractometerPSI`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'HPDiffractometerPSI'; needs a CORA Family
    - ophyd class 'HPDiffractometerPSI' not found in devices/*.py
- **hxbpm** (`id4_common.devices.xbpm.XBPM`)
    - family is the ophyd class name 'XBPM'; needs a CORA Family
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
- **i0g** (`id4_common.devices.gh_i0_motors.I04idg`)
    - family is the ophyd class name 'I04idg'; needs a CORA Family
- **i0h** (`id4_common.devices.gh_i0_motors.I04idh`)
    - family is the ophyd class name 'I04idh'; needs a CORA Family
- **labjack_4ida** (`id4_common.devices.labjacks.CustomLabJackT7`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomLabJackT7'; needs a CORA Family
- **labjack_4idb** (`id4_common.devices.labjacks.CustomLabJackT7`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomLabJackT7'; needs a CORA Family
- **laser** (`id4_common.devices.ventus_laser.VentusLaser`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VentusLaser'; needs a CORA Family
- **magnet911** (`id4_common.devices.magnet_911.Magnet911`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Magnet911'; needs a CORA Family
- **midtable_4idb** (`id4_common.devices.table_4idb.Table4idb`)
    - family is the ophyd class name 'Table4idb'; needs a CORA Family
- **mono** (`id4_common.devices.monochromator.MonoDevice`)
    - enclosure unresolved from prefix or labels
    - energy: pseudo axis (computed, not a physical motor)
    - energy: non-literal or absent component suffix
    - pzt_thf2: FormattedComponent suffix resolved at runtime
    - pzt_chi2: FormattedComponent suffix resolved at runtime
- **mono_feedback** (`id4_common.devices.mono_feedback.MonoFeedback`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MonoFeedback'; needs a CORA Family
- **monoslt** (`id4_common.devices.jj_slits.SlitDevice`)
    - enclosure unresolved from prefix or labels
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **piezo_jena** (`id4_common.devices.piezo_jena.PiezoJena`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'PiezoJena'; needs a CORA Family
- **pol** (`id4_common.devices.polarimeter.PolAnalyzer`)
    - family is the ophyd class name 'PolAnalyzer'; needs a CORA Family
- **pr1** (`id4_common.devices.phaseplates.PRDevice`)
    - family is the ophyd class name 'PRDevice'; needs a CORA Family
    - pzt: FormattedComponent suffix resolved at runtime
    - select_pr: FormattedComponent suffix resolved at runtime
- **pr2** (`id4_common.devices.phaseplates.PRDevice`)
    - family is the ophyd class name 'PRDevice'; needs a CORA Family
    - pzt: FormattedComponent suffix resolved at runtime
    - select_pr: FormattedComponent suffix resolved at runtime
- **pr3** (`id4_common.devices.phaseplates.PRDeviceBase`)
    - family is the ophyd class name 'PRDeviceBase'; needs a CORA Family
    - energy: pseudo axis (computed, not a physical motor)
    - energy: non-literal or absent component suffix
    - th: FormattedComponent suffix resolved at runtime
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - d_spacing: non-literal or absent component suffix
    - offset_degrees: non-literal or absent component suffix
    - motor_switch: non-literal or absent component suffix
    - tracking: non-literal or absent component suffix
- **preamp_4idbI** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idbI0** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idgI** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idgI0** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI0** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI1** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI2** (`id4_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **qxscan_setup** (`id4_common.devices.qxscan_device.QxscanParams`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'QxscanParams'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - pre_edge: non-literal or absent component suffix
    - edge: non-literal or absent component suffix
    - post_edge: non-literal or absent component suffix
    - energy_list: non-literal or absent component suffix
    - factor_list: non-literal or absent component suffix
- **ringlight** (`id4_common.devices.ringlight.Ringlight`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Ringlight'; needs a CORA Family
    - state: FormattedComponent suffix resolved at runtime
- **scaler1** (`id4_common.devices.scaler.LocalScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - preset_monitor: non-literal or absent component suffix
- **scaler2** (`id4_common.devices.scaler.LocalScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - preset_monitor: non-literal or absent component suffix
- **sgz_vortex** (`id4_common.devices.softgluezynq_vortex.SGZVortex`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SGZVortex'; needs a CORA Family
    - preset_monitor: non-literal or absent component suffix
    - clock_freq: non-literal or absent component suffix
- **srs810** (`id4_common.devices.srs810.LockinDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LockinDevice'; needs a CORA Family
- **status_aps** (`id4_common.devices.aps_status.StatusAPS`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'StatusAPS'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **status_polar** (`id4_common.devices.polar_status.Status4ID`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Status4ID'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **t_mirror** (`id4_common.devices.mirror_toroidal.ToroidalMirror`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **table_4idh** (`id4_common.devices.table_4idh.Table4idh`)
    - family is the ophyd class name 'Table4idh'; needs a CORA Family
- **temp_336_4idg** (`apstools.devices.LakeShore336Device`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LakeShore336Device'; needs a CORA Family
    - ophyd class 'LakeShore336Device' not found in devices/*.py
- **temp_340_4idg** (`apstools.devices.LakeShore340Device`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LakeShore340Device'; needs a CORA Family
    - ophyd class 'LakeShore340Device' not found in devices/*.py
- **undulators** (`id4_common.devices.aps_undulator.PolarUndulatorPair`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
- **wbslt** (`id4_common.devices.wb_slit.SlitDevice`)
    - enclosure unresolved from prefix or labels
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
