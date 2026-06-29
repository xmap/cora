# Extracted facts: 6idb-bits

Machine-extracted candidate facts for `4-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| btetramm | TetrAMMRO (?) | `4idbSoft:TetrAMM:` | 4-ID-B | detection | detector, xbpm, baseline, 4idb | yes |
| ctr8 | CustomMeasCompCtr (?) | `4idCTR8_1:` | 4-ID-B | detection | detector, 4idb, 4idg, 4idh, baseline | yes |
| eiger | Eiger1MDetector (?) | `4idEiger:` | 4-ID-G | detection | 4idg, detector | yes |
| flagcam_hhl | VimbaDetector (?) | `4idaPostMirrBeam:` | 4-ID-A | detection | 4ida, camera, detector, flag | yes |
| flagcam_mono | VimbaDetector (?) | `4idaPostMonoBeam:` | 4-ID-A | detection | 4ida, camera, detector, flag | yes |
| flagcam_toro | VimbaDetector (?) | `4idbPostToroBeam:` | 4-ID-B | detection | 4idb, camera, detector, flag | yes |
| flagcam_xeye | VimbaDetector (?) | `4idXrayEye:` | 4-ID-G | detection | 4idg, camera, detector, flag | yes |
| gsydor | SydorEMRO (?) | `4idgSydor:T4U_BPM:` | 4-ID-G | detection | detector, xbpm, baseline, 4idg | yes |
| hsydor | SydorEMRO (?) | `4idhSydor:T4U_BPM:` | 4-ID-H | detection | detector, xbpm, baseline, 4idh | yes |
| scaler1 | GenericProbe | `4idCTR8_1:scaler1` | 4-ID-B | detection | detector, scaler, 4idb, 4idg | yes |
| scaler2 | GenericProbe | `4idCTR8_1:scaler2` | 4-ID-H | detection | detector, scaler, 4idh | yes |
| sgz_vortex | SGZVortex (?) | `4iddMZ0:` | 4-ID-G | detection | detector, 4idg, 4idh | yes |
| aps_xbpm | MyXBPM (?) | `S04` | ? | source | source, baseline | yes |
| ashutter | Shutter | - | 4-ID-A | source | 4ida, shutter, baseline | yes |
| bfilter | APSFilter (?) | `4idbSoft:filter:` | 4-ID-B | source | 4idb, filter, baseline | yes |
| bkb | Mirror | rot=`4idbSoft:m15`; x=`4idbSoft:m16` | 4-ID-B | source | 4idb, optics, baseline | no |
| bshutter | Shutter | - | 4-ID-B | source | 4idb, shutter, baseline | yes |
| bslt | Slit | bot=`4idbSoft:m10`; inb=`4idbSoft:m12`; out=`4idbSoft:m13`; top=`4idbSoft:m11` | 4-ID-B | source | 4idb, slit, baseline | yes |
| chopper | ChopperDevice (?) | `4idChopper:` | 4-ID-B | source | 4idb, baseline | yes |
| crl | mb_creator (?) | `6idbSoft:TRANS:` | 6-ID-B | source | - | yes |
| diamond_window | WindowStages (?) | x=`4idbSoft:m1`; y=`4idbSoft:m2` | 4-ID-A | source | 4ida, baseline | yes |
| dm_experiment | Signal (?) | - | ? | source | dm, baseline | yes |
| dm_workflow | DM_WorkflowConnector (?) | - | ? | source | dm, baseline | yes |
| emag | Magnet2T (?) | mrot=`4idb:m20`; mx=`4idb:m22`; my=`4idb:m21`; srot=`4idb:m19`; sx=`4idb:m18`; sy=`4idb:m17` | 4-ID-B | source | 4idb, magnet, baseline | yes |
| energy | EnergySignal (?) | - | ? | source | energy device, baseline | yes |
| flagmotor_hhl | EpicsMotor (?) | `4idVDCM:m6` | 4-ID-A | source | 4ida, motor, flag, baseline | yes |
| flagmotor_mono | EpicsMotor (?) | `4idVDCM:m7` | 4-ID-A | source | 4ida, motor, flag, baseline | yes |
| flagmotor_toro | EpicsMotor (?) | `4idbSoft:m3` | 4-ID-B | source | 4idb, motor, flag, baseline | yes |
| gfilter | APSFilter (?) | `4idPyFilter:FL1:` | 4-ID-G | source | 4idg, filter, baseline | yes |
| gkb | KBDevice (?) | `4idgKB:` | 4-ID-G | source | 4idg, optics, baseline, kb | yes |
| gslt | Slit | bot=`4idgSoft:m43`; inb=`4idgSoft:m45`; out=`4idgSoft:m46`; top=`4idgSoft:m44` | 4-ID-G | source | 4idg, slit, baseline | yes |
| gxbpm | XBPM (?) | x=`4idgSoft:m6`; y=`4idgSoft:m5` | 4-ID-G | source | 4idg, baseline | yes |
| hhl_mirror | Mirror | curvature=`4idHHLM:pm3`; ds_bend=`4idHHLM:m5`; elipticity=`4idHHLM:pm4`; pitch=`4idHHLM:pm2`; us_bend=`4idHHLM:m4`; x=`4idHHLM:pm1`; x1=`4idHHLM:m2`; x2=`4idHHLM:m3`; y=`4idHHLM:m1` | 4-ID-A | source | 4ida, mirror, baseline | yes |
| hslt | Slit | bot=`4idhSoft:m10`; inb=`4idhSoft:m13`; out=`4idhSoft:m12`; top=`4idhSoft:m11` | 4-ID-H | source | 4idh, slit, baseline | yes |
| huber_euler | CradleDiffractometer (?) | chi=`4idgSoft:m37`; phi=`4idgSoft:m38`; x=`4idgSoft:m40`; y=`4idgSoft:m41`; z=`4idgSoft:m42` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_euler_psi | CradlePSI (?) | chi=`4idgSoft:m37`; phi=`4idgSoft:m38` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_hp | HPDiffractometer (?) | basex=`4idgSoft:m7`; basey=`4idgSoft:SMBaseY`; basey_motor=`4idgSoft:m9`; basez=`4idgSoft:SMBaseZ`; basez_motor=`4idgSoft:m8`; chi=`4idgSoft:m5`; phi=`4idgSoft:m6`; sample_tilt=`4idgSoft:m11`; x=`4idgSoft:m12`; y=`4idgSoft:m14`; z=`4idgSoft:m13` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| huber_hp_psi | HPPSI (?) | chi=`4idgSoft:m5`; phi=`4idgSoft:m6` | 4-ID-G | source | 4idg, diffractometer, baseline | yes |
| hxbpm | XBPM (?) | x=`4idhSoft:m6`; y=`4idhSoft:m5` | 4-ID-H | source | 4idh, baseline | yes |
| i0g | I04idg (?) | x=`4idgSoft:m52`; y=`4idgSoft:m53` | 4-ID-G | source | 4idg, baseline | yes |
| i0h | I04idh (?) | x=`4idhSoft:m20`; y=`4idhSoft:m21` | 4-ID-H | source | 4idh, baseline | yes |
| labjack_4ida | CustomLabJackT7 (?) | `4idaSoft:LJ:` | 4-ID-A | source | 4ida, baseline | yes |
| labjack_4idb | CustomLabJackT7 (?) | `4idbSoft:LJ:` | 4-ID-B | source | 4idb, baseline | yes |
| magnet911 | Magnet911 (?) | `4idhSoft:` | 4-ID-H | source | 4idh, magnet, baseline | yes |
| midtable_4idb | Table4idb (?) | x_ds=`4idbSoft:m8`; x_us=`4idbSoft:m5`; y_ds_in=`4idbSoft:m7`; y_ds_out=`4idbSoft:m6`; y_us=`4idbSoft:m4` | 4-ID-B | source | 4idb, baseline | yes |
| mirror1 | mb_creator (?) | - | ? | source | - | yes |
| mono | Monochromator | chi2=`4idVDCM:m5`; crystal_select=`4idVDCM:m2`; th=`4idVDCM:m1`; thf2=`4idVDCM:m4`; y2=`4idVDCM:m3` | 4-ID-A | source | 4ida, monochromator, energy device, baseline | yes |
| mono_feedback | MonoFeedback (?) | `4idbSoft:` | 4-ID-B | source | monochromator, feedback, baseline | yes |
| monoslt | Slit | bot=`4idVDCM:m13`; inb=`4idVDCM:m15`; out=`4idVDCM:m16`; top=`4idVDCM:m14` | 4-ID-A | source | 4ida, slit, baseline | yes |
| pol | PolAnalyzer (?) | th=`4idbSoft:m9`; y=`4idbSoft:m17` | 4-ID-B | source | 4idb, baseline | yes |
| pr1 | PRDevice (?) | th=`4idam4`; x=`4idam1`; y=`4idam2` | 4-ID-A | source | 4ida, phase retarder, energy device, track_energy, baseline | yes |
| pr2 | PRDevice (?) | th=`4idam9`; x=`4idam6`; y=`4idam7` | 4-ID-A | source | 4ida, phase retarder, energy device, track_energy, baseline | yes |
| pr3 | PRDeviceBase (?) | th=`4idam12`; x=`4idam10`; y=`4idam11` | 4-ID-A | source | 4ida, phase retarder, energy device, track_energy, baseline | yes |
| preamp_4idbI | LocalPreAmp (?) | `4idbSoft:A4` | 4-ID-B | source | 4idb, preamp, baseline | yes |
| preamp_4idbI0 | LocalPreAmp (?) | `4idbSoft:A3` | 4-ID-B | source | 4idb, preamp, baseline | yes |
| preamp_4idgI | LocalPreAmp (?) | `4idgSoftX:A2` | 4-ID-G | source | 4idg, preamp, baseline | yes |
| preamp_4idgI0 | LocalPreAmp (?) | `4idgSoftX:A1` | 4-ID-G | source | 4idg, preamp, baseline | yes |
| preamp_4idhI0 | LocalPreAmp (?) | `4idhSoft:A1` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| preamp_4idhI1 | LocalPreAmp (?) | `4idhSoft:A2` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| preamp_4idhI2 | LocalPreAmp (?) | `4idhSoft:A3` | 4-ID-H | source | 4idh, preamp, baseline | yes |
| psic | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |
| psic_psi | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |
| psic_q | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |
| psic_sim | creator (?) | - | ? | source | diffractometer, hklpy2 | yes |
| qxscan_setup | QxscanParams (?) | - | ? | source | qxscan, energy device, baseline | yes |
| shutter | Shutter | - | ? | source | shutters, baseline | yes |
| status_aps | StatusAPS (?) | - | ? | source | source, status, baseline | yes |
| status_polar | Status4ID (?) | `PA:04ID:` | ? | source | status, baseline | yes |
| table_4idh | Table4idh (?) | x_ds=`4idhSoft:m2`; x_us=`4idhSoft:m1`; y_ds=`4idhSoft:m4`; y_us=`4idhSoft:m3` | 4-ID-H | source | 4idh, table, baseline | yes |
| temp_4idg | LakeShore336Device (?) | `4idgSoft:LS336:cryo:` | 4-ID-G | source | 4idg, temperature, baseline | yes |
| transfocator | TransfocatorClass (?) | `4idPyCRL:CRL4ID:` | 4-ID-G | source | 4idg, optics, track_energy, baseline | yes |
| undulators | InsertionDevice | `S04ID:` | ? | source | source, energy device, baseline | yes |
| wbslt | Slit | diag=`4idVDCM:m10`; hor=`4idVDCM:m9`; pitch=`4idVDCM:m11`; yaw=`4idVDCM:m12` | 4-ID-A | source | 4ida, slit, baseline | yes |

## Candidate enclosures

`4-ID-A`, `4-ID-B`, `4-ID-G`, `4-ID-H`, `6-ID-B` (all inferred, confirm).

## Role hints (from labels)

`Controller`, `Detector`, `Positioner`

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Simulated devices (excluded from the candidate)

`sim_motor`, `sim_det`

## Open confirms

- **aps_xbpm** (`polar_common.devices.aps_xbpm.MyXBPM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyXBPM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **ashutter** (`polar_common.devices.shutters.PolarShutter`)
    - no prefix and no resolvable axes
- **bfilter** (`polar_common.devices.filters_device.APSFilter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'APSFilter'; needs a CORA Family
- **bshutter** (`apstools.devices.ApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - ophyd class 'ApsPssShutterWithStatus' not found in devices/*.py
- **bslt** (`polar_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **btetramm** (`polar_common.devices.quadems.TetrAMMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'TetrAMMRO'; needs a CORA Family
- **chopper** (`polar_common.devices.chopper_device.ChopperDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'ChopperDevice'; needs a CORA Family
    - translation: FormattedComponent suffix resolved at runtime
- **crl** (`apstools.devices.mb_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **ctr8** (`polar_common.devices.usb_ctr8.CustomMeasCompCtr`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomMeasCompCtr'; needs a CORA Family
- **diamond_window** (`polar_common.devices.diamond_window_table.WindowStages`)
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
- **eiger** (`polar_common.devices.ad_eiger1M.Eiger1MDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Eiger1MDetector'; needs a CORA Family
- **emag** (`polar_common.devices.electromagnet.Magnet2T`)
    - family is the ophyd class name 'Magnet2T'; needs a CORA Family
- **energy** (`polar_common.devices.energy_device.EnergySignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EnergySignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **flagcam_hhl** (`polar_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_mono** (`polar_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_toro** (`polar_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagcam_xeye** (`polar_common.devices.ad_vimba.VimbaDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'VimbaDetector'; needs a CORA Family
- **flagmotor_hhl** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flagmotor_mono** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flagmotor_toro** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **gfilter** (`polar_common.devices.filters_device_avs.APSFilter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'APSFilter'; needs a CORA Family
- **gkb** (`polar_common.devices.kb_4idg.KBDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'KBDevice'; needs a CORA Family
- **gslt** (`polar_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **gsydor** (`polar_common.devices.quadems.SydorEMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SydorEMRO'; needs a CORA Family
    - conf: non-literal or absent component suffix
- **gxbpm** (`polar_common.devices.xbpm_4idg.XBPM`)
    - family is the ophyd class name 'XBPM'; needs a CORA Family
- **hhl_mirror** (`polar_common.devices.hhl_mirror.ToroidalMirror`)
    - fine_pitch: FormattedComponent suffix resolved at runtime
- **hslt** (`polar_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **hsydor** (`polar_common.devices.quadems.SydorEMRO`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SydorEMRO'; needs a CORA Family
    - conf: non-literal or absent component suffix
- **huber_euler** (`polar_common.devices.polar_diffractometer.CradleDiffractometer`)
    - family is the ophyd class name 'CradleDiffractometer'; needs a CORA Family
- **huber_euler_psi** (`polar_common.devices.polar_diffractometer.CradlePSI`)
    - family is the ophyd class name 'CradlePSI'; needs a CORA Family
- **huber_hp** (`polar_common.devices.polar_diffractometer.HPDiffractometer`)
    - family is the ophyd class name 'HPDiffractometer'; needs a CORA Family
    - nanox: FormattedComponent suffix resolved at runtime
    - nanoy: FormattedComponent suffix resolved at runtime
    - nanoz: FormattedComponent suffix resolved at runtime
- **huber_hp_psi** (`polar_common.devices.polar_diffractometer.HPPSI`)
    - family is the ophyd class name 'HPPSI'; needs a CORA Family
- **hxbpm** (`polar_common.devices.xbpm_4idh.XBPM`)
    - family is the ophyd class name 'XBPM'; needs a CORA Family
- **i0g** (`polar_common.devices.gh_i0_motors.I04idg`)
    - family is the ophyd class name 'I04idg'; needs a CORA Family
- **i0h** (`polar_common.devices.gh_i0_motors.I04idh`)
    - family is the ophyd class name 'I04idh'; needs a CORA Family
- **labjack_4ida** (`polar_common.devices.labjacks.CustomLabJackT7`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomLabJackT7'; needs a CORA Family
- **labjack_4idb** (`polar_common.devices.labjacks.CustomLabJackT7`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'CustomLabJackT7'; needs a CORA Family
- **magnet911** (`polar_common.devices.magnet_911.Magnet911`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Magnet911'; needs a CORA Family
- **midtable_4idb** (`polar_common.devices.table_4idb.Table4idb`)
    - family is the ophyd class name 'Table4idb'; needs a CORA Family
- **mirror1** (`apstools.devices.mb_creator`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **mono** (`polar_common.devices.monochromator.MonoDevice`)
    - energy: pseudo axis (computed, not a physical motor)
    - energy: non-literal or absent component suffix
    - pzt_thf2: FormattedComponent suffix resolved at runtime
    - pzt_chi2: FormattedComponent suffix resolved at runtime
- **mono_feedback** (`polar_common.devices.mono_feedback.MonoFeedback`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MonoFeedback'; needs a CORA Family
- **monoslt** (`polar_common.devices.jj_slits.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
- **pol** (`polar_common.devices.polarimeter.PolAnalyzer`)
    - family is the ophyd class name 'PolAnalyzer'; needs a CORA Family
- **pr1** (`polar_common.devices.phaseplates.PRDevice`)
    - family is the ophyd class name 'PRDevice'; needs a CORA Family
    - pzt: FormattedComponent suffix resolved at runtime
    - select_pr: FormattedComponent suffix resolved at runtime
- **pr2** (`polar_common.devices.phaseplates.PRDevice`)
    - family is the ophyd class name 'PRDevice'; needs a CORA Family
    - pzt: FormattedComponent suffix resolved at runtime
    - select_pr: FormattedComponent suffix resolved at runtime
- **pr3** (`polar_common.devices.phaseplates.PRDeviceBase`)
    - family is the ophyd class name 'PRDeviceBase'; needs a CORA Family
    - energy: pseudo axis (computed, not a physical motor)
    - energy: non-literal or absent component suffix
    - th: FormattedComponent suffix resolved at runtime
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - d_spacing: non-literal or absent component suffix
    - offset_degrees: non-literal or absent component suffix
    - tracking: non-literal or absent component suffix
- **preamp_4idbI** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idbI0** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idgI** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idgI0** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI0** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI1** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **preamp_4idhI2** (`polar_common.devices.preamps.LocalPreAmp`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LocalPreAmp'; needs a CORA Family
- **psic** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **psic_psi** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **psic_q** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **psic_sim** (`hklpy2.creator`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'creator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'creator' not found in devices/*.py
- **qxscan_setup** (`polar_common.devices.qxscan_device.QxscanParams`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'QxscanParams'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - pre_edge: non-literal or absent component suffix
    - edge: non-literal or absent component suffix
    - post_edge: non-literal or absent component suffix
    - energy_list: non-literal or absent component suffix
    - factor_list: non-literal or absent component suffix
- **scaler1** (`polar_common.devices.scaler.LocalScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - preset_monitor: non-literal or absent component suffix
- **scaler2** (`polar_common.devices.scaler.LocalScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - preset_monitor: non-literal or absent component suffix
- **sgz_vortex** (`polar_common.devices.softgluezynq_vortex.SGZVortex`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SGZVortex'; needs a CORA Family
    - preset_monitor: non-literal or absent component suffix
- **shutter** (`apstools.devices.SimulatedApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - ophyd class 'SimulatedApsPssShutterWithStatus' not found in devices/*.py
- **status_aps** (`polar_common.devices.aps_status.StatusAPS`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'StatusAPS'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **status_polar** (`polar_common.devices.polar_status.Status4ID`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Status4ID'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **table_4idh** (`polar_common.devices.table_4idh.Table4idh`)
    - family is the ophyd class name 'Table4idh'; needs a CORA Family
- **temp_4idg** (`apstools.devices.LakeShore336Device`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LakeShore336Device'; needs a CORA Family
    - ophyd class 'LakeShore336Device' not found in devices/*.py
- **transfocator** (`polar_common.devices.transfocator_device.TransfocatorClass`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'TransfocatorClass'; needs a CORA Family
    - energy: non-literal or absent component suffix
    - tracking: non-literal or absent component suffix
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - z: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - reference_data_x: non-literal or absent component suffix
    - reference_data_y: non-literal or absent component suffix
    - deltax: non-literal or absent component suffix
    - deltay: non-literal or absent component suffix
    - trackxy: non-literal or absent component suffix
- **undulators** (`polar_common.devices.aps_undulator.PolarUndulatorPair`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
- **wbslt** (`polar_common.devices.wb_slit.SlitDevice`)
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
    - vsize: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - hsize: FormattedComponent suffix resolved at runtime
