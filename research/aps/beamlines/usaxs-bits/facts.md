# Extracted facts: usaxs-bits

Machine-extracted candidate facts for `usaxs-bits` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| blackfly_det | MyPointGreyDetector (?) | `usxFLY3:` | ? | detection | camera, area_detector | yes |
| blackfly_optical | MyPointGreyDetectorJPEG (?) | `usxFLY2:` | ? | detection | camera, area_detector | yes |
| saxs_det | MyPilatusDetector (?) | `usaxs_pilatus3:` | ? | detection | camera, area_detector | yes |
| waxs_det | MyEigerDetector (?) | `usaxs_eiger1:` | ? | detection | camera, area_detector | yes |
| Filter_AlTi | FilterBank (?) | `12idPyFilter:` | ? | source | baseline | yes |
| LAXm1 | EpicsMotor (?) | `usxLAX:m58:c0:m1` | ? | source | LAXm1 | yes |
| LAXm2 | EpicsMotor (?) | `usxLAX:m58:c0:m2` | ? | source | LAXm2 | yes |
| LAXm3 | EpicsMotor (?) | `usxLAX:m58:c0:m3` | ? | source | LAXm3 | yes |
| LAXm4 | EpicsMotor (?) | `usxLAX:m58:c0:m4` | ? | source | LAXm4 | yes |
| LAXm5 | EpicsMotor (?) | `usxLAX:m58:c0:m5` | ? | source | LAXtcam, baseline | yes |
| LAXm6 | EpicsMotor (?) | `usxLAX:m58:c0:m6` | ? | source | LAXgsy | yes |
| LAXm7 | EpicsMotor (?) | `usxLAX:m58:c0:m7` | ? | source | LAXgsx | yes |
| LAXm8 | EpicsMotor (?) | `usxLAX:m58:c0:m8` | ? | source | LAXm8 | yes |
| a_stage | UsaxsAnalyzerStageDevice (?) | x=`usxAERO:m4`; y=`usxAERO:m5` | ? | source | - | yes |
| ar_start | EpicsSignal (?) | - | ? | source | - | yes |
| auto_collect | AutoCollectDataDevice (?) | `usxLAX:AutoCollection` | ? | source | - | yes |
| bss | BssDevice (?) | `usxTerms:bss:` | ? | source | baseline | yes |
| d_stage | UsaxsDetectorStageDevice (?) | - | ? | source | - | yes |
| diagnostics | DiagnosticsParameters (?) | - | ? | source | baseline | yes |
| flyscan_trajectories | Trajectories (?) | - | ? | source | - | yes |
| gslit_stage | Slit | x=`usxLAX:m58:c0:m7`; y=`usxLAX:m58:c0:m6` | ? | source | - | yes |
| guard_slit | Slit | x=`usxLAX:m58:c0:m7`; y=`usxLAX:m58:c0:m6` | ? | source | baseline | yes |
| lax_autosave | Autosave (?) | `usxLAX:` | ? | source | - | yes |
| linkam_tc1 | My_Linkam_T96_Device (?) | `usxLINKAM:tc1:` | ? | source | - | yes |
| m_stage | UsaxsCollimatorStageDevice (?) | x=`usxAERO:m10`; y=`usxAERO:m11` | ? | source | - | yes |
| monochromator | Monochromator | - | ? | source | baseline | yes |
| pi_c867 | SampleRotator (?) | `usxPI:c867:c0:m1` | ? | source | - | yes |
| ptc10 | USAXS_PTC10 (?) | `usxTEMP:tc1:` | ? | source | - | yes |
| s_stage | UsaxsSampleStageDevice (?) | x=`usxAERO:m8`; y=`usxAERO:m9` | ? | source | - | yes |
| sample_data | SampleDataDevice (?) | - | ? | source | baseline | yes |
| saxs_stage | SaxsDetectorStageDevice (?) | x=`usxAERO:m13`; y=`usxAERO:m15`; z=`usxAERO:m14` | ? | source | - | yes |
| scaler2_I000_counts | EpicsSignalRO (?) | - | ? | source | - | yes |
| scaler2_I000_cps | EpicsSignalRO (?) | - | ? | source | - | yes |
| struck | Struck3820 (?) | `usxLAX:3820:` | ? | source | - | yes |
| terms | GeneralParameters (?) | - | ? | source | baseline | yes |
| upd_valid | EpicsSignalRO (?) | - | ? | source | - | yes |
| usaxs_CheckBeamStandard | EpicsSignalRO (?) | - | ? | source | - | yes |
| usaxs_flyscan | UsaxsFlyScanDevice (?) | - | ? | source | - | yes |
| usaxs_q_calc | SwaitRecord (?) | `usxLAX:USAXS:Q` | ? | source | - | yes |
| usaxs_slit | Slit | h_size=`usxLAX:m58:c1:m8`; v_size=`usxLAX:m58:c1:m7`; x=`usxLAX:m58:c1:m6`; y=`usxLAX:m58:c1:m5` | ? | source | baseline | yes |
| userCalcs_lax | UserCalcsDevice (?) | `usxLAX:` | ? | source | - | yes |
| user_data | UserDataDevice (?) | - | ? | source | baseline | yes |
| waxs2x | EpicsMotor (?) | `usxAERO:m7` | ? | source | waxs2x, motor, baseline | yes |
| waxsx | EpicsMotor (?) | `usxAERO:m3` | ? | source | wasxs, motor, baseline | yes |
| white_beam_ready | WhiteBeamReadyCalc (?) | `usxLAX:userCalc9` | ? | source | - | yes |

## Candidate enclosures

None inferred from prefixes or labels.

## Role hints (from labels)

`Detector`, `Positioner`

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Simulated devices (excluded from the candidate)

`sim_motor`, `sim_det`

## Open confirms

- **Filter_AlTi** (`usaxs.devices.filters.FilterBank`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FilterBank'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - fPos: FormattedComponent suffix resolved at runtime
    - fPos_RBV: FormattedComponent suffix resolved at runtime
    - attenuation: FormattedComponent suffix resolved at runtime
    - transmission: FormattedComponent suffix resolved at runtime
- **LAXm1** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm2** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm3** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm4** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm5** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm6** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm7** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **LAXm8** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **a_stage** (`usaxs.devices.stages.UsaxsAnalyzerStageDevice`)
    - family is the ophyd class name 'UsaxsAnalyzerStageDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **ar_start** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **auto_collect** (`usaxs.devices.autocollect.AutoCollectDataDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AutoCollectDataDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **blackfly_det** (`usaxs.devices.blackfly_module.MyPointGreyDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyPointGreyDetector'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **blackfly_optical** (`usaxs.devices.blackfly_module.MyPointGreyDetectorJPEG`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyPointGreyDetectorJPEG'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **bss** (`usaxs.devices.bss.BssDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'BssDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **d_stage** (`usaxs.devices.stages.UsaxsDetectorStageDevice`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'UsaxsDetectorStageDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **diagnostics** (`usaxs.devices.diagnostics.DiagnosticsParameters`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'DiagnosticsParameters'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - PSS: non-literal or absent component suffix
- **flyscan_trajectories** (`usaxs.devices.trajectories.Trajectories`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'Trajectories'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **gslit_stage** (`usaxs.devices.stages.GuardSlitsStageDevice`)
    - enclosure unresolved from prefix or labels
- **guard_slit** (`usaxs.devices.slits.GSlitDevice`)
    - enclosure unresolved from prefix or labels
- **lax_autosave** (`usaxs.devices.autosave.Autosave`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Autosave'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **linkam_tc1** (`usaxs.devices.linkam.My_Linkam_T96_Device`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'My_Linkam_T96_Device'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **m_stage** (`usaxs.devices.stages.UsaxsCollimatorStageDevice`)
    - family is the ophyd class name 'UsaxsCollimatorStageDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **monochromator** (`usaxs.devices.monochromator.MyMonochromator`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
- **pi_c867** (`usaxs.devices.sample_rotator.SampleRotator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SampleRotator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **ptc10** (`usaxs.devices.ptc10_controller.USAXS_PTC10`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'USAXS_PTC10'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **s_stage** (`usaxs.devices.stages.UsaxsSampleStageDevice`)
    - family is the ophyd class name 'UsaxsSampleStageDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **sample_data** (`usaxs.devices.sample_data.SampleDataDevice`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'SampleDataDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **saxs_det** (`usaxs.devices.pilatus_module.MyPilatusDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyPilatusDetector'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **saxs_stage** (`usaxs.devices.stages.SaxsDetectorStageDevice`)
    - family is the ophyd class name 'SaxsDetectorStageDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **scaler2_I000_counts** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **scaler2_I000_cps** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **struck** (`apstools.devices.Struck3820`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Struck3820'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'Struck3820' not found in devices/*.py
- **terms** (`usaxs.devices.general_terms.GeneralParameters`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'GeneralParameters'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - USAXS: non-literal or absent component suffix
    - SBUSAXS: non-literal or absent component suffix
    - SAXS: non-literal or absent component suffix
    - SAXS_WAXS: non-literal or absent component suffix
    - WAXS: non-literal or absent component suffix
    - Radiography: non-literal or absent component suffix
    - Imaging: non-literal or absent component suffix
    - OutOfBeam: non-literal or absent component suffix
    - FlyScan: non-literal or absent component suffix
    - preUSAXStune: non-literal or absent component suffix
    - HeaterProcess: non-literal or absent component suffix
- **upd_valid** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **usaxs_CheckBeamStandard** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **usaxs_flyscan** (`usaxs.devices.usaxs_fly_scan.UsaxsFlyScanDevice`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'UsaxsFlyScanDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - flying: non-literal or absent component suffix
- **usaxs_q_calc** (`apstools.synApps.swait.SwaitRecord`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SwaitRecord'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'SwaitRecord' not found in devices/*.py
- **usaxs_slit** (`usaxs.devices.slits.UsaxsSlitDevice`)
    - enclosure unresolved from prefix or labels
- **userCalcs_lax** (`apstools.synApps.swait.UserCalcsDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'UserCalcsDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'UserCalcsDevice' not found in devices/*.py
- **user_data** (`usaxs.devices.user_data.UserDataDevice`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'UserDataDevice'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **waxs2x** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **waxs_det** (`usaxs.devices.pilatus_module.MyEigerDetector`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyEigerDetector'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **waxsx** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **white_beam_ready** (`usaxs.devices.white_beam_ready_calc.WhiteBeamReadyCalc`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'WhiteBeamReadyCalc'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - available: non-literal or absent component suffix
