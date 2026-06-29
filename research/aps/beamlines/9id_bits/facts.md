# Extracted facts: 9id_bits

Machine-extracted candidate facts for `9-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| pilatus1m | Camera | `PILATUS_1MF:` | ? | detection | area_detector, detectors | yes |
| aerorot_1 | EpicsMotor (?) | `9idAerotech2:R1:m1` | ? | source | motors, baseline | yes |
| analysis_machine | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| analysis_type | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| b_stop_x | AcsMotor (?) | `9idd:CR9D4M1:m14` | 9-ID-D | source | motor, baseline | yes |
| b_stop_z | AcsMotor (?) | `9idd:CR9D4M1:m15` | 9-ID-D | source | motor, baseline | yes |
| bd3_base_hor | AcsMotor (?) | `9idd:CR9D1M1:m7` | 9-ID-D | source | motor, baseline | yes |
| bd3_base_vert | AcsMotor (?) | `9idd:CR9D1M1:m8` | 9-ID-D | source | motor, baseline | yes |
| bd5_base_hor | AcsMotor (?) | `9idd:CR9D1M1:m23` | 9-ID-D | source | motor, baseline | yes |
| bd5_base_vert | AcsMotor (?) | `9idd:CR9D1M1:m24` | 9-ID-D | source | motor, baseline | yes |
| carriage_bs_bot | EpicsMotor (?) | `9idGT:mcs2-02:m3` | ? | source | motor, baseline | yes |
| carriage_hor_bs_y | EpicsMotor (?) | `9idGT:m1` | ? | source | motor, baseline | yes |
| crl9id2x | JJtransfocator2xZ (?) | `9idPyCRL:CRL9ID:` | ? | source | transfocators, baseline | yes |
| cssi_X4 | EpicsMotor (?) | `9idCSSI:mcs2-01:m4` | ? | source | motor, baseline | yes |
| cssi_Y4 | EpicsMotor (?) | `9idCSSI:mcs2-01:m3` | ? | source | motor, baseline | yes |
| cssi_Z4 | EpicsMotor (?) | `9idCSSI:mcs2-01:m2` | ? | source | motor, baseline | yes |
| cssi_flyz | EpicsMotor (?) | `9idANT95:aero:c0:m1` | ? | source | motor, baseline | yes |
| cssi_theta3 | FlexCombinedCap (?) | `9idCSSI:` | ? | source | motors, baseline | yes |
| cssi_theta_x2 | EpicsMotor (?) | `9idCSSI:mcs2-01:m1` | ? | source | motor, baseline | yes |
| cssi_x2 | FlexCombinedCap (?) | `9idCSSI:` | ? | source | motors, baseline | yes |
| cssi_y2 | FlexCombinedEnc (?) | `9idCSSI:` | ? | source | motors, baseline | yes |
| cssi_z2 | FlexCombinedEnc (?) | `9idCSSI:` | ? | source | motors, baseline | yes |
| cycle_name | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| damm_hor | AcsMotor (?) | `9ida:CR9A1:m6` | 9-ID-A | source | motor, baseline | yes |
| damm_vert | AcsMotor (?) | `9ida:CR9A1:m7` | 9-ID-A | source | motor, baseline | yes |
| eiger_x | EpicsMotor (?) | `9idGT:m11` | ? | source | motor, baseline | yes |
| eiger_y | EpicsMotor (?) | `9idGT:m12` | ? | source | motor, baseline | yes |
| experiment_name | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| file_name | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| file_path | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| fl1 | AVSfilters (?) | `9idPyFilter:FL1:` | ? | source | filters, baseline | yes |
| flag1_mot | AcsMotor (?) | `9ida:CR9A1:m5` | 9-ID-A | source | motor, baseline | yes |
| flag2_mot | AcsMotor (?) | `9ida:CR9A1:m13` | 9-ID-A | source | motor, baseline | yes |
| flag3_mot | AcsMotor (?) | `9ida:MONO:m3` | 9-ID-A | source | motor, baseline | yes |
| flag4_mot | AcsMotor (?) | `9idd:CR9D1M1:m10` | 9-ID-D | source | motor, baseline | yes |
| gixs_sam_x | EpicsMotor (?) | `9idd:CR9D4M1:m3` | 9-ID-D | source | motor, baseline | yes |
| hexapod1 | aerotechHexapod (?) | `9idAerotech:HP1:` | ? | source | hexapod, motors, baseline | yes |
| hexapod2 | aerotechHexapod (?) | `9idAerotech2:HP2:` | ? | source | hexapod, motors, baseline | yes |
| idt_mono | Monochromator | `9ida:` | 9-ID-A | source | mono, baseline | yes |
| kb_cssi_granite | AcsMotor (?) | `9idd:CR9D1M1:m29` | 9-ID-D | source | motor, baseline | yes |
| kb_hor_ds | FlexCombinedCap (?) | `9idKB:` | ? | source | motors, baseline | yes |
| kb_hor_us | FlexCombinedCap (?) | `9idKB:` | ? | source | motors, baseline | yes |
| kb_ver_ds | FlexCombinedCap (?) | `9idKB:` | ? | source | motors, baseline | yes |
| kb_ver_us | FlexCombinedCap (?) | `9idKB:` | ? | source | motors, baseline | yes |
| kohzu_linear | EpicsMotor (?) | `9idCSSI:CR9D1M2:m1` | ? | source | motor, baseline | yes |
| kohzu_rotate | EpicsMotor (?) | `9idCSSI:CR9D1M2:m2` | ? | source | motor, baseline | yes |
| measurement_num | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| metadata_full_path | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| mr1_bender2 | AcsMotor (?) | `9ida:FMBO:m8` | 9-ID-A | source | motor, baseline | yes |
| mr1_piezo | EpicsMotor (?) | `9ida:FMBO:Piezo:m1` | 9-ID-A | source | motor, baseline | yes |
| mr1_pitch | AcsMotor (?) | `9ida:FMBO:m6` | 9-ID-A | source | motor, baseline | yes |
| mr1_x | AcsMotor (?) | `9ida:FMBO:m4` | 9-ID-A | source | motor, baseline | yes |
| mr1_y | AcsMotor (?) | `9ida:FMBO:m2` | 9-ID-A | source | motor, baseline | yes |
| mr2_bender1 | AcsMotor (?) | `9ida:FMBO:m7` | 9-ID-A | source | motor, baseline | yes |
| mr2_piezo | EpicsMotor (?) | `9ida:FMBO:Piezo:m2` | 9-ID-A | source | motor, baseline | yes |
| mr2_pitch | AcsMotor (?) | `9ida:FMBO:m5` | 9-ID-A | source | motor, baseline | yes |
| mr2_x | AcsMotor (?) | `9ida:FMBO:m3` | 9-ID-A | source | motor, baseline | yes |
| mr2_y | AcsMotor (?) | `9ida:FMBO:m1` | 9-ID-A | source | motor, baseline | yes |
| mux_2_sel_signal | EpicsSignal (?) | - | ? | source | - | yes |
| qmap_file | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| qnw_index | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| sample_name | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| scattering_orientation | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| shutter | Shutter | - | ? | source | shutters | yes |
| slit1 | HHLApertureWBA (?) | `9ida:SL-1:` | 9-ID-A | source | slits, baseline | yes |
| slit2 | HHLApertureWBA (?) | `9ida:SL-2:` | 9-ID-A | source | slits, baseline | yes |
| slit3 | Slit | `9idd:Slit3` | 9-ID-D | source | slits, baseline | yes |
| slit3_base_hor | AcsMotor (?) | `9idd:CR9D1M1:m5` | 9-ID-D | source | motor, baseline | yes |
| slit3_base_vert | AcsMotor (?) | `9idd:CR9D1M1:m6` | 9-ID-D | source | motor, baseline | yes |
| slit4 | Slit | `9idd:Slit4` | 9-ID-D | source | slits, baseline | yes |
| slit4_base_hor | AcsMotor (?) | `9idd:CR9D1M1:m15` | 9-ID-D | source | motor, baseline | yes |
| slit4_base_vert | AcsMotor (?) | `9idd:CR9D1M1:m16` | 9-ID-D | source | motor, baseline | yes |
| slit5 | Slit | `9idd:Slit5` | 9-ID-D | source | slits, baseline | yes |
| slit5_base_hor | AcsMotor (?) | `9idd:CR9D1M1:m21` | 9-ID-D | source | motor, baseline | yes |
| slit5_base_vert | AcsMotor (?) | `9idd:CR9D1M1:m22` | 9-ID-D | source | motor, baseline | yes |
| spec_file | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| start_bluesky | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| tetramm1 | MyTetrAMM (?) | `9idTetra:QUAD1:` | ? | source | tetramm | yes |
| undulator | InsertionDevice | `S09ID:DSID:` | ? | source | - | yes |
| uscope_focus | EpicsMotor (?) | `9idCSSI:CR9D1M2:m10` | ? | source | motor, baseline | yes |
| uscope_x | EpicsMotor (?) | `9idCSSI:CR9D1M2:m5` | ? | source | motor, baseline | yes |
| uscope_y | EpicsMotor (?) | `9idCSSI:CR9D1M2:m9` | ? | source | motors, baseline | yes |
| uscope_z | EpicsMotor (?) | `9idCSSI:CR9D1M2:m6` | ? | source | motor, baseline | yes |
| user_comments | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| user_description | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| waxs_x_gixs_ped1 | AcsMotor (?) | `9idd:CR9D1M1:m31` | 9-ID-D | source | motor, baseline | yes |
| waxs_y_gixs_ped2 | AcsMotor (?) | `9idd:CR9D1M1:m32` | 9-ID-D | source | motor, baseline | yes |
| workflow_name | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm1_sum | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm1_xpos | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm1_ypos | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm2_sum | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm2_xpos | EpicsSignal (?) | - | ? | source | metadataPV | yes |
| xpbm2_ypos | EpicsSignal (?) | - | ? | source | metadataPV | yes |

## Candidate enclosures

`9-ID-A`, `9-ID-D` (all inferred, confirm).

## Role hints (from labels)

`Detector`, `Positioner`

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Simulated devices (excluded from the candidate)

`sim_motor`, `sim_det`, `sim_motor_cssi`, `sim_det_cssi`, `sim_motor_saxs`, `sim_det_saxs`, `sim_motor_waxs`, `sim_det_waxs`, `sim_motor_xpcs`, `sim_det_xpcs`

## Open confirms

- **aerorot_1** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **analysis_machine** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **analysis_type** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **b_stop_x** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **b_stop_z** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **bd3_base_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **bd3_base_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **bd5_base_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **bd5_base_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **carriage_bs_bot** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **carriage_hor_bs_y** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **crl9id2x** (`common_9id.devices.JJtransfocator2xZ`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'JJtransfocator2xZ'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - z2: FormattedComponent suffix resolved at runtime
- **cssi_X4** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **cssi_Y4** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **cssi_Z4** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **cssi_flyz** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **cssi_theta3** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **cssi_theta_x2** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **cssi_x2** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **cssi_y2** (`common_9id.devices.FlexCombinedEnc`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedEnc'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - enc: FormattedComponent suffix resolved at runtime
- **cssi_z2** (`common_9id.devices.FlexCombinedEnc`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedEnc'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - enc: FormattedComponent suffix resolved at runtime
- **cycle_name** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **damm_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **damm_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **eiger_x** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **eiger_y** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **experiment_name** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **file_name** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **file_path** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **fl1** (`common_9id.devices.AVSfilters`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AVSfilters'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - index: FormattedComponent suffix resolved at runtime
    - attenuation: FormattedComponent suffix resolved at runtime
    - transmission: FormattedComponent suffix resolved at runtime
    - translation: FormattedComponent suffix resolved at runtime
- **flag1_mot** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **flag2_mot** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **flag3_mot** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **flag4_mot** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **gixs_sam_x** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **hexapod1** (`common_9id.devices.aerotechHexapod`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'aerotechHexapod'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - z: FormattedComponent suffix resolved at runtime
    - ax: FormattedComponent suffix resolved at runtime
    - ay: FormattedComponent suffix resolved at runtime
    - az: FormattedComponent suffix resolved at runtime
- **hexapod2** (`common_9id.devices.aerotechHexapod`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'aerotechHexapod'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - x: FormattedComponent suffix resolved at runtime
    - y: FormattedComponent suffix resolved at runtime
    - z: FormattedComponent suffix resolved at runtime
    - ax: FormattedComponent suffix resolved at runtime
    - ay: FormattedComponent suffix resolved at runtime
    - az: FormattedComponent suffix resolved at runtime
- **idt_mono** (`apstools.devices.KohzuSeqCtl_Monochromator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - ophyd class 'KohzuSeqCtl_Monochromator' not found in devices/*.py
- **kb_cssi_granite** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **kb_hor_ds** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **kb_hor_us** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **kb_ver_ds** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **kb_ver_us** (`common_9id.devices.FlexCombinedCap`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'FlexCombinedCap'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - cap: FormattedComponent suffix resolved at runtime
- **kohzu_linear** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **kohzu_rotate** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **measurement_num** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **metadata_full_path** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **mr1_bender2** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr1_piezo** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **mr1_pitch** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr1_x** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr1_y** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr2_bender1** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr2_piezo** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **mr2_pitch** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr2_x** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mr2_y** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **mux_2_sel_signal** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **pilatus1m** (`apstools.devices.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **qmap_file** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **qnw_index** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **sample_name** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **scattering_orientation** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **shutter** (`apstools.devices.SimulatedApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - ophyd class 'SimulatedApsPssShutterWithStatus' not found in devices/*.py
- **slit1** (`common_9id.devices.HHLApertureWBA`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'HHLApertureWBA'; needs a CORA Family
- **slit2** (`common_9id.devices.HHLApertureWBA`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'HHLApertureWBA'; needs a CORA Family
- **slit3** (`common_9id.devices.Optics2Slit2D_soft`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **slit3_base_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **slit3_base_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **slit4** (`common_9id.devices.Optics2Slit2D_soft`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **slit4_base_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **slit4_base_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **slit5** (`common_9id.devices.Optics2Slit2D_soft`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
- **slit5_base_hor** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **slit5_base_vert** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **spec_file** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **start_bluesky** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **tetramm1** (`common_9id.devices.MyTetrAMM`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MyTetrAMM'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - conf: non-literal or absent component suffix
- **undulator** (`apstools.devices.aps_undulator.PlanarUndulator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - ophyd class 'PlanarUndulator' not found in devices/*.py
- **uscope_focus** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **uscope_x** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **uscope_y** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **uscope_z** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsMotor' not found in devices/*.py
- **user_comments** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **user_description** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **waxs_x_gixs_ped1** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **waxs_y_gixs_ped2** (`common_9id.devices.AcsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'AcsMotor'; needs a CORA Family
- **workflow_name** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm1_sum** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm1_xpos** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm1_ypos** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm2_sum** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm2_xpos** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **xpbm2_ypos** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
