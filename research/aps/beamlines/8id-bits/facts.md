# Extracted facts: 8id-bits

Machine-extracted candidate facts for `8-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| detector | AerotechDetectorStage (?) | x=`8idiAerotech:m4`; y=`8idiAerotech:m5` | 8-ID-I | detection | detector, stage | yes |
| eiger4M | Camera | `8idEiger4m:` | ? | detection | area_detector, detectors | yes |
| lambda2M | Camera | `8idLambda2m:` | ? | detection | area_detector, detectors | yes |
| rigaku3M | Camera | `8idRigaku3m:` | ? | detection | area_detector, detectors | yes |
| rheometer | AerotechRheometerStage (?) | pitch=`8idiAerotech:m11`; roll=`8idiAerotech:m10`; x=`8idiAerotech:m8`; y=`8idiAerotech:m9`; yaw=`8idiAerotech:m12`; z=`8idiAerotech:m7` | 8-ID-I | sample | rheometer, stage | yes |
| sample | AerotechSampleStage (?) | x=`8idiAerotech:m1`; y=`8idiAerotech:m3`; z=`8idiAerotech:m2` | 8-ID-I | sample | sample, stage | yes |
| bd5a | HV_Motors (?) | h=`8iddSoft:CR8-D1:m9`; v=`8iddSoft:CR8-D1:m10` | 8-ID-D | source | - | yes |
| bd6a | HV_Motors (?) | h=`8ideSoft:CR8-E2:m9`; v=`8ideSoft:CR8-E2:m10` | 8-ID-E | source | - | yes |
| bs_motors | FlightTubeBeamStop (?) | ds_x=`8idiSoft:FLIGHT:m5`; ds_y=`8idiSoft:FLIGHT:m6`; us=`8idiSoft:FLIGHT:m7` | 8-ID-I | source | - | yes |
| cam_stage_8idi | XY_Motors (?) | - | ? | source | - | yes |
| det_motors | FlightTubeDetector (?) | tth=`8idiSoft:FLIGHT:m2`; z=`8idiSoft:FLIGHT:m1` | 8-ID-I | source | - | yes |
| dpKeysight | Function_Generator (?) | `dpKeysight:KEY1:` | ? | source | - | yes |
| filter_8ide | AVSfilters (?) | `8idPyFilter:FL2:` | ? | source | - | yes |
| fl2 | EpicsMotor (?) | `8ideSoft:CR8-E2:m7` | 8-ID-E | source | motor | yes |
| fl3 | EpicsMotor (?) | `8idiSoft:CR8-I2:m7` | 8-ID-I | source | motor | yes |
| flag4 | EpicsMotor (?) | `8iddSoft:CR8-D1:m1` | 8-ID-D | source | motor | yes |
| flight_path_8idi | FlightPath (?) | ds_x=`8idiSoft:FLIGHT:m5`; ds_y=`8idiSoft:FLIGHT:m6`; length=`8idiSoft:FLIGHT:m1`; swing=`8idiSoft:FLIGHT:m2`; us=`8idiSoft:FLIGHT:m7` | 8-ID-I | source | - | yes |
| fofb_s09 | FOFB (?) | `S09-FOFB` | ? | source | - | yes |
| granite | granite_device (?) | `8idiSoft:CR8-I2:US` | 8-ID-I | source | - | yes |
| granite_8idi_valve | Valve_Enable (?) | `8idiSoft:CR8-I2:` | 8-ID-I | source | - | yes |
| huber | Huber_Diffractometer (?) | chi=`8ideSoft:CR8-E1:m8`; delta=`8ideSoft:CR8-E1:m5`; eta=`8ideSoft:CR8-E1:m7`; mu=`8ideSoft:CR8-E1:m6`; nu=`8ideSoft:CR8-E1:m4`; phi=`8ideSoft:CR8-E1:m9`; x=`8ideSoft:CR8-E1:m15`; y=`8ideSoft:CR8-E1:m10`; z=`8ideSoft:CR8-E1:m11` | 8-ID-E | source | - | yes |
| idt_mono | IDTMono (?) | `8idaSoft:MONO:` | 8-ID-A | source | mono, baseline | yes |
| keysight | Function_Generator (?) | `8idKeysight:KEY1:` | ? | source | - | yes |
| labjack | LabJack (?) | `8idiSoft:LJT705:` | 8-ID-I | source | - | yes |
| lakeshore1 | Lakeshore (?) | `8ideSoft:LS336:1:` | 8-ID-E | source | - | yes |
| lakeshore2 | Lakeshore (?) | `8ideSoft:LS336:2:` | 8-ID-E | source | - | yes |
| mcr_wait_signal | Rheometer_Wait (?) | - | ? | source | - | yes |
| mono | Monochromator | energy=`8idaSoft:MN1:Energy`; gap=`8idaSoft:MN1:Gap`; offset=`8idaSoft:MN1:Offset`; theta=`8idaSoft:MN1:Bragg`; wavelength=`8idaSoft:MN1:Lambda` | 8-ID-A | source | - | yes |
| mono_slit | Slit | `8idaSoft:CR8-A1:US` | 8-ID-A | source | - | yes |
| mr1 | Mirror | coarse_pitch=`8idaSoft:FMBO:m6`; fine_pitch=`8idaSoft:FMBO:Piezo:m1`; flag=`8idaSoft:CR8-A1:m5`; x=`8idaSoft:FMBO:m4`; y=`8idaSoft:FMBO:m2` | 8-ID-A | source | - | no |
| mr2 | Mirror | bender1=`8idaSoft:FMBO:m7`; bender2=`8idaSoft:FMBO:m8`; coarse_pitch=`8idaSoft:FMBO:m5`; fine_pitch=`8idaSoft:FMBO:Piezo:m2`; flag=`8idaSoft:CR8-A1:m6`; x=`8idaSoft:FMBO:m3`; y=`8idaSoft:FMBO:m1` | 8-ID-A | source | - | no |
| pd | PIND (?) | `8ideSoft:pdu1:` | 8-ID-E | source | - | yes |
| psic | creator (?) | `8ideSoft:CR8-E1:` | 8-ID-E | source | diffractometer | yes |
| pv_registers | EpicsPvStorageRegisters (?) | `8ideSoft:` | 8-ID-E | source | - | yes |
| qnw_env1 | QnwDevice (?) | `8idiSoft:QNWenv_1:` | 8-ID-I | source | - | yes |
| qnw_env2 | QnwDevice (?) | `8idiSoft:QNWenv_2:` | 8-ID-I | source | - | yes |
| qnw_env3 | QnwDevice (?) | `8idiSoft:QNWenv_3:` | 8-ID-I | source | - | yes |
| rl1 | Transfocator (?) | lens1=`8iddSoft:TRANS:m5`; lens10=`8iddSoft:TRANS:m14`; lens2=`8iddSoft:TRANS:m6`; lens3=`8iddSoft:TRANS:m7`; lens4=`8iddSoft:TRANS:m8`; lens5=`8iddSoft:TRANS:m9`; lens6=`8iddSoft:TRANS:m10`; lens7=`8iddSoft:TRANS:m11`; lens8=`8iddSoft:TRANS:m12`; lens9=`8iddSoft:TRANS:m13`; pitch=`8iddSoft:TRANS:m4`; x=`8iddSoft:TRANS:m2`; y=`8iddSoft:TRANS:m1`; yaw=`8iddSoft:TRANS:m3` | 8-ID-D | source | - | yes |
| rl2 | Transfocator (?) | lens1=`8iddSoft:TRANS:m15`; lens10=`8iddSoft:TRANS:m24`; lens2=`8iddSoft:TRANS:m16`; lens3=`8iddSoft:TRANS:m17`; lens4=`8iddSoft:TRANS:m18`; lens5=`8iddSoft:TRANS:m19`; lens6=`8iddSoft:TRANS:m20`; lens7=`8iddSoft:TRANS:m21`; lens8=`8iddSoft:TRANS:m22`; lens9=`8iddSoft:TRANS:m23`; pitch=`8iddSoft:TRANS:m28`; x=`8iddSoft:TRANS:m26`; y=`8iddSoft:TRANS:m25`; yaw=`8iddSoft:TRANS:m27` | 8-ID-D | source | - | yes |
| shutter_8ide | Shutter | `8ideSoft:fastshutter:` | 8-ID-E | source | - | yes |
| sim_psic | creator (?) | - | ? | source | diffractometer | yes |
| sl4 | Slit | `8iddSoft:Slit1` | 8-ID-D | source | - | yes |
| sl4_base | Slit | `8iddSoft:CR8-D1:US` | 8-ID-D | source | - | yes |
| sl5 | Slit | `8ideSoft:Slit1` | 8-ID-E | source | - | yes |
| sl5_base | Slit | `8ideSoft:CR8-E2:US` | 8-ID-E | source | - | yes |
| sl5_motors | Slit | `8ideSoft:CR8-E2:US` | 8-ID-E | source | - | yes |
| sl7 | Slit | `8ideSoft:Slit2` | 8-ID-E | source | - | yes |
| sl7_base | Slit | `8ideSoft:CR8-E2:US` | 8-ID-E | source | - | yes |
| sl8 | Slit | `8idiSoft:Slit1` | 8-ID-I | source | - | yes |
| sl8_base | Slit | `8idiSoft:CR8-I2:US` | 8-ID-I | source | - | yes |
| sl9 | Slit | `8idiSoft:Slit2` | 8-ID-I | source | - | yes |
| sl9_base | Slit | `8idiSoft:CR8-I2:US` | 8-ID-I | source | - | yes |
| sl9_motors | Slit | `8idiSoft:CR8-I2:US` | 8-ID-I | source | - | yes |
| softglue | SoftGlue (?) | acq_period=`8idMZ1:userTran1.A`; acq_time=`8idMZ1:userTran1.C`; clear1=`8idMZ1:SG:UpCntr-1_CLEAR_Signal`; clear2=`8idMZ1:SG:UpCntr-2_CLEAR_Signal`; clear3=`8idMZ1:SG:UpCntr-3_CLEAR_Signal`; enable_rigaku=`8idMZ1:SG:MUX2-1_SEL_Signal`; num_triggers=`8idMZ1:userTran1.J`; start_pulses=`8idMZ1:SG:plsTrn-1_Inp_Signal`; stop_pulses=`8idMZ1:SG:plsTrn-1_Dis_Signal` | ? | source | - | yes |
| softglue_8id_acq | softglue_acq8id (?) | - | ? | source | - | yes |
| softglue_8id_mz2 | softglue_mz2 (?) | - | ? | source | - | yes |
| softglue_8idi | SoftGlue (?) | acq_period=`8idMZ1:userTran1.A`; acq_time=`8idMZ1:userTran1.A`; enable_rigaku=`8idMZ1:SG:MUX2-1_SEL_Signal`; num_triggers=`8idMZ1:userTran1.J`; start_pulses=`8idMZ1:SG:plsTrn-1_Inp_Signal`; stop_pulses=`8idMZ1:SG:plsTrn-1_Dis_Signal` | ? | source | - | yes |
| tetramm1 | MyTetrAMM (?) | `8idTetra:QUAD1:` | ? | source | - | yes |
| tetramm2 | MyTetrAMM (?) | `8idTetra:QUAD2:` | ? | source | - | yes |
| tetramm3 | MyTetrAMM (?) | `8idTetra:QUAD3:` | ? | source | - | yes |
| tetramm4 | MyTetrAMM (?) | `8idTetra:QUAD4:` | ? | source | - | yes |
| undulator_downstream | InsertionDevice | `S08ID:DSID:` | ? | source | - | yes |
| undulator_upstream | InsertionDevice | `S08ID:USID:` | ? | source | - | yes |
| ur5 | UR5 (?) | `RobocartUR5:` | ? | source | - | yes |
| wb_slit | Slit | `8idaSoft:CR8-A1:US` | 8-ID-A | source | - | yes |
| xbpm1 | SydorTP4U (?) | `8ideBPM:T4U_BPM:` | 8-ID-E | source | - | yes |

## Candidate enclosures

`8-ID-A`, `8-ID-D`, `8-ID-E`, `8-ID-I` (all inferred, confirm).

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

- **bd5a** (`id8_common.devices.hv_motors.HV_Motors`)
    - family is the ophyd class name 'HV_Motors'; needs a CORA Family
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **bd6a** (`id8_common.devices.hv_motors.HV_Motors`)
    - family is the ophyd class name 'HV_Motors'; needs a CORA Family
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **bs_motors** (`id8_common.devices.flight_tube.FlightTubeBeamStop`)
    - family is the ophyd class name 'FlightTubeBeamStop'; needs a CORA Family
- **cam_stage_8idi** (`id8_common.devices.xy_motors.XY_Motors`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'XY_Motors'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
- **det_motors** (`id8_common.devices.flight_tube.FlightTubeDetector`)
    - family is the ophyd class name 'FlightTubeDetector'; needs a CORA Family
- **detector** (`id8_common.devices.aerotech_stages.AerotechDetectorStage`)
    - family is the ophyd class name 'AerotechDetectorStage'; needs a CORA Family
- **dpKeysight** (`id8_common.devices.func_gen.Function_Generator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Function_Generator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **eiger4M** (`apstools.devices.area_detector_factory.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **filter_8ide** (`id8_common.devices.avs_filters.AVSfilters`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AVSfilters'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - index: FormattedComponent suffix resolved at runtime
    - attenuation: FormattedComponent suffix resolved at runtime
    - transmission: FormattedComponent suffix resolved at runtime
- **fl2** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **fl3** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flag4** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **flight_path_8idi** (`id8_common.devices.flight_path.FlightPath`)
    - family is the ophyd class name 'FlightPath'; needs a CORA Family
- **fofb_s09** (`id8_common.devices.fofb.FOFB`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FOFB'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **granite** (`id8_common.devices.granite.granite_device`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'granite_device'; needs a CORA Family
    - x: FormattedComponent suffix resolved at runtime
- **granite_8idi_valve** (`id8_common.devices.granite_enable.Valve_Enable`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Valve_Enable'; needs a CORA Family
- **huber** (`id8_common.devices.huber_diffractometer.Huber_Diffractometer`)
    - family is the ophyd class name 'Huber_Diffractometer'; needs a CORA Family
- **idt_mono** (`id8_common.devices.idt_mono.IDTMono`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'IDTMono'; needs a CORA Family
    - bragg: FormattedComponent suffix resolved at runtime
    - xtal_gap: FormattedComponent suffix resolved at runtime
    - flag: FormattedComponent suffix resolved at runtime
    - coarse_pitch: FormattedComponent suffix resolved at runtime
    - coarse_roll: FormattedComponent suffix resolved at runtime
    - x_slide: FormattedComponent suffix resolved at runtime
    - y_slide: FormattedComponent suffix resolved at runtime
    - energy: FormattedComponent suffix resolved at runtime
    - moving: FormattedComponent suffix resolved at runtime
    - allstop_button: FormattedComponent suffix resolved at runtime
    - move_button: FormattedComponent suffix resolved at runtime
- **keysight** (`id8_common.devices.func_gen.Function_Generator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Function_Generator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **labjack** (`id8_common.devices.labjack_support.LabJack`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LabJack'; needs a CORA Family
- **lakeshore1** (`id8_common.devices.lakeshore.Lakeshore`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Lakeshore'; needs a CORA Family
- **lakeshore2** (`id8_common.devices.lakeshore.Lakeshore`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'Lakeshore'; needs a CORA Family
- **lambda2M** (`apstools.devices.area_detector_factory.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **mcr_wait_signal** (`id8_common.devices.rheometer_wait_signal.Rheometer_Wait`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'Rheometer_Wait'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **mono** (`id8_common.devices.idt_mono.BraggGap_Monochromator`)
    - bragg_motor: FormattedComponent suffix resolved at runtime
    - gap_motor: FormattedComponent suffix resolved at runtime
- **mono_slit** (`id8_common.devices.hhl_slits.HHLSlits`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - hgap: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - vgap: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
- **pd** (`id8_common.devices.pin_diode.PIND`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'PIND'; needs a CORA Family
- **psic** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **pv_registers** (`id8_common.devices.registers_device.EpicsPvStorageRegisters`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsPvStorageRegisters'; needs a CORA Family
- **qnw_env1** (`id8_common.devices.qnw_device.QnwDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'QnwDevice'; needs a CORA Family
    - tolerance: non-literal or absent component suffix
- **qnw_env2** (`id8_common.devices.qnw_device.QnwDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'QnwDevice'; needs a CORA Family
    - tolerance: non-literal or absent component suffix
- **qnw_env3** (`id8_common.devices.qnw_device.QnwDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'QnwDevice'; needs a CORA Family
    - tolerance: non-literal or absent component suffix
- **rheometer** (`id8_common.devices.aerotech_stages.AerotechRheometerStage`)
    - family is the ophyd class name 'AerotechRheometerStage'; needs a CORA Family
- **rigaku3M** (`apstools.devices.area_detector_factory.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **rl1** (`id8_common.devices.transfocator.Transfocator`)
    - family is the ophyd class name 'Transfocator'; needs a CORA Family
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - lens1: FormattedComponent suffix resolved at runtime
    - lens2: FormattedComponent suffix resolved at runtime
    - lens3: FormattedComponent suffix resolved at runtime
    - lens4: FormattedComponent suffix resolved at runtime
    - lens5: FormattedComponent suffix resolved at runtime
    - lens6: FormattedComponent suffix resolved at runtime
    - lens7: FormattedComponent suffix resolved at runtime
    - lens8: FormattedComponent suffix resolved at runtime
    - lens9: FormattedComponent suffix resolved at runtime
    - lens10: FormattedComponent suffix resolved at runtime
- **rl2** (`id8_common.devices.transfocator.Transfocator`)
    - family is the ophyd class name 'Transfocator'; needs a CORA Family
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - lens1: FormattedComponent suffix resolved at runtime
    - lens2: FormattedComponent suffix resolved at runtime
    - lens3: FormattedComponent suffix resolved at runtime
    - lens4: FormattedComponent suffix resolved at runtime
    - lens5: FormattedComponent suffix resolved at runtime
    - lens6: FormattedComponent suffix resolved at runtime
    - lens7: FormattedComponent suffix resolved at runtime
    - lens8: FormattedComponent suffix resolved at runtime
    - lens9: FormattedComponent suffix resolved at runtime
    - lens10: FormattedComponent suffix resolved at runtime
- **sample** (`id8_common.devices.aerotech_stages.AerotechSampleStage`)
    - family is the ophyd class name 'AerotechSampleStage'; needs a CORA Family
- **shutter_8ide** (`id8_common.devices.fast_shutter.FastShutter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sim_psic** (`hklpy2.creator`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'creator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'creator' not found in devices/*.py
- **sl4** (`id8_common.devices.slit.ID8Optics2Slit2D_HV`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sl4_base** (`id8_common.devices.slit_base.SlitBase`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **sl5** (`id8_common.devices.slit.ID8Optics2Slit2D_HV`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sl5_base** (`id8_common.devices.slit_base.SlitBase`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **sl5_motors** (`id8_common.devices.individual_slits.IndividualSlits`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - hp: FormattedComponent suffix resolved at runtime
    - hn: FormattedComponent suffix resolved at runtime
    - vp: FormattedComponent suffix resolved at runtime
    - vn: FormattedComponent suffix resolved at runtime
- **sl7** (`id8_common.devices.slit.ID8Optics2Slit2D_HV`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sl7_base** (`id8_common.devices.slit_base.SlitBase`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **sl8** (`id8_common.devices.slit.ID8Optics2Slit2D_HV`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sl8_base** (`id8_common.devices.slit_base.SlitBase`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **sl9** (`id8_common.devices.slit.ID8Optics2Slit2D_HV`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **sl9_base** (`id8_common.devices.slit_base.SlitBase`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - h: FormattedComponent suffix resolved at runtime
    - v: FormattedComponent suffix resolved at runtime
- **sl9_motors** (`id8_common.devices.individual_slits.IndividualSlits`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - hp: FormattedComponent suffix resolved at runtime
    - hn: FormattedComponent suffix resolved at runtime
    - vp: FormattedComponent suffix resolved at runtime
    - vn: FormattedComponent suffix resolved at runtime
- **softglue** (`id8_common.devices.softglue.SoftGlue`)
    - family is the ophyd class name 'SoftGlue'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - acq_period: FormattedComponent suffix resolved at runtime
    - acq_time: FormattedComponent suffix resolved at runtime
    - num_triggers: FormattedComponent suffix resolved at runtime
    - start_pulses: FormattedComponent suffix resolved at runtime
    - stop_pulses: FormattedComponent suffix resolved at runtime
    - enable_rigaku: FormattedComponent suffix resolved at runtime
- **softglue_8id_acq** (`id8_common.devices.softglue.softglue_acq8id`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'softglue_acq8id'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **softglue_8id_mz2** (`id8_common.devices.softglue.softglue_mz2`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'softglue_mz2'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **softglue_8idi** (`id8_common.devices.softglue.SoftGlue`)
    - family is the ophyd class name 'SoftGlue'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - acq_period: FormattedComponent suffix resolved at runtime
    - acq_time: FormattedComponent suffix resolved at runtime
    - num_triggers: FormattedComponent suffix resolved at runtime
    - start_pulses: FormattedComponent suffix resolved at runtime
    - stop_pulses: FormattedComponent suffix resolved at runtime
    - enable_rigaku: FormattedComponent suffix resolved at runtime
- **tetramm1** (`id8_common.devices.tetramm_picoammeter.MyTetrAMM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyTetrAMM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - conf: non-literal or absent component suffix
- **tetramm2** (`id8_common.devices.tetramm_picoammeter.MyTetrAMM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyTetrAMM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - conf: non-literal or absent component suffix
- **tetramm3** (`id8_common.devices.tetramm_picoammeter.MyTetrAMM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyTetrAMM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - conf: non-literal or absent component suffix
- **tetramm4** (`id8_common.devices.tetramm_picoammeter.MyTetrAMM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyTetrAMM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - conf: non-literal or absent component suffix
- **undulator_downstream** (`id8_common.devices.undulator.RevolverUndulator_8ID`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
- **undulator_upstream** (`id8_common.devices.undulator.RevolverUndulator_8ID`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
- **ur5** (`id8_common.devices.ur5_control.UR5`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'UR5'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **wb_slit** (`id8_common.devices.hhl_slits.HHLSlits`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - pitch: FormattedComponent suffix resolved at runtime
    - yaw: FormattedComponent suffix resolved at runtime
    - horizontal: FormattedComponent suffix resolved at runtime
    - diagonal: FormattedComponent suffix resolved at runtime
    - hgap: FormattedComponent suffix resolved at runtime
    - hcen: FormattedComponent suffix resolved at runtime
    - vgap: FormattedComponent suffix resolved at runtime
    - vcen: FormattedComponent suffix resolved at runtime
- **xbpm1** (`id8_common.devices.sydor_tp4u.SydorTP4U`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SydorTP4U'; needs a CORA Family
    - conf: non-literal or absent component suffix
