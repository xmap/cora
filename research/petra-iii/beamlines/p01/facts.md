# Extracted facts: P01

Machine-extracted candidate facts for `P01` (facility `petra-iii`). Candidates only; confirm every row before modeling. Source: DESY OnlineXML (the beamline's online_*.xml Tango device registry).

Filtered out 34 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| gap_b | motor_tango (?) | `p01/attributemotor/gap.02` | P01-EH1 | sample | - | yes |
| bpm2_x | oms58 (?) | `p01/motor/eh1.21` | P01-EH1 | source | - | yes |
| bpm2_y | oms58 (?) | `p01/motor/eh1.22` | P01-EH1 | source | - | yes |
| bunch_y | oms58 (?) | `p01/motor/eh1.16` | P01-EH1 | source | - | yes |
| crl2_rot | oms58 (?) | `p01/motor/eh1.17` | P01-EH1 | source | - | yes |
| crl2_th | oms58 (?) | `p01/motor/eh1.18` | P01-EH1 | source | - | yes |
| crl2_x | oms58 (?) | `p01/motor/eh1.19` | P01-EH1 | source | - | yes |
| crl2_y | oms58 (?) | `p01/motor/eh1.20` | P01-EH1 | source | - | yes |
| dcm_bragg | motor_tango (?) | `p01/dcmmotor/oh.01` | P01-OH1 | source | - | yes |
| dcm_ener | motor_tango (?) | `p01/dcmener/oh.01` | P01-OH1 | source | - | yes |
| dcm_ener_und | motor_tango (?) | `p01/multiplemotors/eh1.01` | P01-EH1 | source | - | yes |
| dcm_lat | oms58 (?) | `p01/motor/oh1.08` | P01-OH1 | source | - | yes |
| dcm_offset | motor_tango (?) | `p01/attributemotor/fmbexitoffset.01` | P01-OH1 | source | - | yes |
| dcm_para | oms58 (?) | `p01/motor/oh1.10` | P01-OH1 | source | - | yes |
| dcm_perp | oms58 (?) | `p01/motor/oh1.09` | P01-OH1 | source | - | yes |
| dcm_pitch | oms58 (?) | `p01/motor/oh1.11` | P01-OH1 | source | - | yes |
| dcm_roll | oms58 (?) | `p01/motor/oh1.02` | P01-OH1 | source | - | yes |
| dcm_y | motor_tango (?) | `p01/vmexecutor/dcm_z` | P01-OH1 | source | - | yes |
| dcm_y1 | oms58 (?) | `p01/motor/oh1.03` | P01-OH1 | source | - | yes |
| dcm_y2 | oms58 (?) | `p01/motor/oh1.04` | P01-OH1 | source | - | yes |
| dcm_y3 | oms58 (?) | `p01/motor/oh1.07` | P01-OH1 | source | - | yes |
| det16_th | oms58 (?) | `p01/motor/eh3.25` | P01-EH3 | source | - | yes |
| det16_x | oms58 (?) | `p01/motor/eh3.26` | P01-EH3 | source | - | yes |
| det16_y | oms58 (?) | `p01/motor/eh3.27` | P01-EH3 | source | - | yes |
| det_th | oms58 (?) | `p01/motor/eh3.44` | P01-EH3 | source | - | yes |
| det_x | oms58 (?) | `p01/motor/eh2.29` | P01-EH2 | source | - | yes |
| det_x | oms58 (?) | `p01/motor/eh3.42` | P01-EH3 | source | - | yes |
| det_y | oms58 (?) | `p01/motor/eh2.30` | P01-EH2 | source | - | yes |
| det_y | oms58 (?) | `p01/motor/eh3.43` | P01-EH3 | source | - | yes |
| diff_th | oms58 (?) | `p01/motor/eh2.49` | P01-EH2 | source | - | yes |
| diff_tth | oms58 (?) | `p01/motor/eh2.37` | P01-EH2 | source | - | yes |
| dslit_bottom | oms58 (?) | `p01/motor/eh2.27` | P01-EH2 | source | - | yes |
| dslit_bottom | oms58 (?) | `p01/motor/eh3.47` | P01-EH3 | source | - | yes |
| dslit_cx | motor_tango (?) | `p01/vmexecutor/hslit_eh2_cx` | P01-EH2 | source | - | yes |
| dslit_cx | motor_tango (?) | `p01/vmexecutor/hslit_eh3_cx` | P01-EH3 | source | - | yes |
| dslit_cy | motor_tango (?) | `p01/vmexecutor/hslit_eh2_cy` | P01-EH2 | source | - | yes |
| dslit_cy | motor_tango (?) | `p01/vmexecutor/hslit_eh3_cy` | P01-EH3 | source | - | yes |
| dslit_dx | motor_tango (?) | `p01/vmexecutor/hslit_eh2_dx` | P01-EH2 | source | - | yes |
| dslit_dx | motor_tango (?) | `p01/vmexecutor/hslit_eh3_dx` | P01-EH3 | source | - | yes |
| dslit_dy | motor_tango (?) | `p01/vmexecutor/hslit_eh2_dy` | P01-EH2 | source | - | yes |
| dslit_dy | motor_tango (?) | `p01/vmexecutor/hslit_eh3_dy` | P01-EH3 | source | - | yes |
| dslit_left | oms58 (?) | `p01/motor/eh2.26` | P01-EH2 | source | - | yes |
| dslit_left | oms58 (?) | `p01/motor/eh3.46` | P01-EH3 | source | - | yes |
| dslit_right | oms58 (?) | `p01/motor/eh2.25` | P01-EH2 | source | - | yes |
| dslit_right | oms58 (?) | `p01/motor/eh3.45` | P01-EH3 | source | - | yes |
| dslit_top | oms58 (?) | `p01/motor/eh2.28` | P01-EH2 | source | - | yes |
| dslit_top | oms58 (?) | `p01/motor/eh3.48` | P01-EH3 | source | - | yes |
| fe_slit1_cy | oms58 (?) | `p01/motor/oh1.12` | P01-OH1 | source | - | yes |
| fe_slit1_dy | oms58 (?) | `p01/motor/oh1.05` | P01-OH1 | source | - | yes |
| fe_slit2_cy | oms58 (?) | `p01/motor/oh1.14` | P01-OH1 | source | - | yes |
| fe_slit2_dy | oms58 (?) | `p01/motor/oh1.13` | P01-OH1 | source | - | yes |
| fe_slit2_left | oms58 (?) | `p01/motor/oh1.15` | P01-OH1 | source | - | yes |
| fe_slit2_right | oms58 (?) | `p01/motor/oh1.16` | P01-OH1 | source | - | yes |
| gap_a | motor_tango (?) | `p01/attributemotor/gap.01` | P01-EH1 | source | - | yes |
| hrm1064_pth | motor_tango (?) | `p01/attributemotor/pieh2.51` | P01-EH1 | source | - | yes |
| hrm1064_ptilt | motor_tango (?) | `p01/attributemotor/pieh2.52` | P01-EH1 | source | - | yes |
| hrm1064_th | oms58 (?) | `p01/motor/eh1.34` | P01-EH1 | source | - | yes |
| hrm1064_tilt | oms58 (?) | `p01/motor/eh1.33` | P01-EH1 | source | - | yes |
| hrm1064_x | oms58 (?) | `p01/motor/eh1.36` | P01-EH1 | source | - | yes |
| hrm1064_y | oms58 (?) | `p01/motor/eh1.35` | P01-EH1 | source | - | yes |
| hrm3d_th | oms58 (?) | `p01/motor/eh1.47` | P01-EH1 | source | - | yes |
| hrm3d_tilt | oms58 (?) | `p01/motor/eh1.46` | P01-EH1 | source | - | yes |
| hrm3d_x | oms58 (?) | `p01/motor/eh1.42` | P01-EH1 | source | - | yes |
| hrm3d_y | oms58 (?) | `p01/motor/eh1.48` | P01-EH1 | source | - | yes |
| hrm3w_th | oms58 (?) | `p01/motor/eh1.44` | P01-EH1 | source | - | yes |
| hrm3w_tilt | oms58 (?) | `p01/motor/eh1.43` | P01-EH1 | source | - | yes |
| hrm3w_x | oms58 (?) | `p01/motor/eh1.41` | P01-EH1 | source | - | yes |
| hrm3w_y | oms58 (?) | `p01/motor/eh1.45` | P01-EH1 | source | - | yes |
| hrm400_pth | motor_tango (?) | `p01/attributemotor/pieh2.49` | P01-EH1 | source | - | yes |
| hrm400_ptilt | motor_tango (?) | `p01/attributemotor/pieh2.50` | P01-EH1 | source | - | yes |
| hrm400_th | oms58 (?) | `p01/motor/eh1.02` | P01-EH1 | source | - | yes |
| hrm400_tilt | oms58 (?) | `p01/motor/eh1.01` | P01-EH1 | source | - | yes |
| hrm400_x | oms58 (?) | `p01/motor/eh1.04` | P01-EH1 | source | - | yes |
| hrm400_y | oms58 (?) | `p01/motor/eh1.03` | P01-EH1 | source | - | yes |
| hrm_ener | motor_tango (?) | `p01/vmexecutor/hrm_ener` | P01-EH1 | source | - | yes |
| hrm_ener2 | motor_tango (?) | `p01/vmexecutor/hrm_ener2` | P01-EH1 | source | - | yes |
| ic2_x | oms58 (?) | `p01/motor/eh1.23` | P01-EH1 | source | - | yes |
| ic2_y | oms58 (?) | `p01/motor/eh1.24` | P01-EH1 | source | - | yes |
| kb3h_bd | oms58 (?) | `p01/motor/eh3.02` | P01-EH3 | source | - | yes |
| kb3h_bu | oms58 (?) | `p01/motor/eh3.01` | P01-EH3 | source | - | yes |
| kb3h_th | oms58 (?) | `p01/motor/eh3.03` | P01-EH3 | source | - | yes |
| kb3h_th2 | oms58 (?) | `p01/motor/eh3.04` | P01-EH3 | source | - | yes |
| kb3v_bd | oms58 (?) | `p01/motor/eh3.06` | P01-EH3 | source | - | yes |
| kb3v_bu | oms58 (?) | `p01/motor/eh3.05` | P01-EH3 | source | - | yes |
| kb3v_th | oms58 (?) | `p01/motor/eh3.07` | P01-EH3 | source | - | yes |
| kb3v_th2 | oms58 (?) | `p01/motor/eh3.08` | P01-EH3 | source | - | yes |
| oh1_m1_pitch | oms58 (?) | `p01/motor/oh1.17` | P01-OH1 | source | - | yes |
| oh1_m1_rot | oms58 (?) | `p01/motor/oh1.21` | P01-OH1 | source | - | yes |
| oh1_m1_x | oms58 (?) | `p01/motor/oh1.18` | P01-OH1 | source | - | yes |
| oh1_m1_y | oms58 (?) | `p01/motor/oh1.22` | P01-OH1 | source | - | yes |
| oh1_m2_pitch | oms58 (?) | `p01/motor/oh1.25` | P01-OH1 | source | - | yes |
| oh1_m2_rot | oms58 (?) | `p01/motor/oh1.29` | P01-OH1 | source | - | yes |
| oh1_m2_x | oms58 (?) | `p01/motor/oh1.26` | P01-OH1 | source | - | yes |
| oh1_m2_y | oms58 (?) | `p01/motor/oh1.30` | P01-OH1 | source | - | yes |
| oh2_diam_y | oms58 (?) | `p01/motor/oh2.28` | P01-OH2 | source | - | yes |
| rixs_x | oms58 (?) | `p01/motor/oh2.04` | P01-OH2 | source | - | yes |
| sam_tilt | oms58 (?) | `p01/motor/eh2.35` | P01-EH2 | source | - | yes |
| sam_x | oms58 (?) | `p01/motor/eh2.34` | P01-EH2 | source | - | yes |
| sam_y | oms58 (?) | `p01/motor/eh2.33` | P01-EH2 | source | - | yes |
| samp_b | oms58 (?) | `p01/motor/eh3.28` | P01-EH3 | source | - | yes |
| samp_rot | oms58 (?) | `p01/motor/eh3.32` | P01-EH3 | source | - | yes |
| samp_tilt | oms58 (?) | `p01/motor/eh3.29` | P01-EH3 | source | - | yes |
| samp_x | oms58 (?) | `p01/motor/eh3.31` | P01-EH3 | source | - | yes |
| samp_y | oms58 (?) | `p01/motor/eh3.30` | P01-EH3 | source | - | yes |
| slit1_bottom | oms58 (?) | `p01/motor/oh2.45` | P01-OH2 | source | - | yes |
| slit1_cx | motor_tango (?) | `p01/vmexecutor/slit1_cx` | P01-OH2 | source | - | yes |
| slit1_cy | motor_tango (?) | `p01/vmexecutor/slit1_cy` | P01-OH2 | source | - | yes |
| slit1_dx | motor_tango (?) | `p01/vmexecutor/slit1_dx` | P01-OH2 | source | - | yes |
| slit1_dy | motor_tango (?) | `p01/vmexecutor/slit1_dy` | P01-OH2 | source | - | yes |
| slit1_left | oms58 (?) | `p01/motor/oh2.47` | P01-OH2 | source | - | yes |
| slit1_right | oms58 (?) | `p01/motor/oh2.48` | P01-OH2 | source | - | yes |
| slit1_top | oms58 (?) | `p01/motor/oh2.46` | P01-OH2 | source | - | yes |
| slit2_bottom | oms58 (?) | `p01/motor/eh1.05` | P01-EH1 | source | - | yes |
| slit2_cx | motor_tango (?) | `p01/vmexecutor/jjslit_eh1_cx` | P01-EH1 | source | - | yes |
| slit2_cy | motor_tango (?) | `p01/vmexecutor/jjslit_eh1_cy` | P01-EH1 | source | - | yes |
| slit2_dx | motor_tango (?) | `p01/vmexecutor/jjslit_eh1_dx` | P01-EH1 | source | - | yes |
| slit2_dy | motor_tango (?) | `p01/vmexecutor/jjslit_eh1_dy` | P01-EH1 | source | - | yes |
| slit2_left | oms58 (?) | `p01/motor/eh1.07` | P01-EH1 | source | - | yes |
| slit2_right | oms58 (?) | `p01/motor/eh1.08` | P01-EH1 | source | - | yes |
| slit2_top | oms58 (?) | `p01/motor/eh1.06` | P01-EH1 | source | - | yes |
| slit3_bottom | oms58 (?) | `p01/motor/eh2.01` | P01-EH2 | source | - | yes |
| slit3_cx | motor_tango (?) | `p01/vmexecutor/jjslit_eh2_cx` | P01-EH2 | source | - | yes |
| slit3_cy | motor_tango (?) | `p01/vmexecutor/jjslit_eh2_cy` | P01-EH2 | source | - | yes |
| slit3_dx | motor_tango (?) | `p01/vmexecutor/jjslit_eh2_dx` | P01-EH2 | source | - | yes |
| slit3_dy | motor_tango (?) | `p01/vmexecutor/jjslit_eh2_dy` | P01-EH2 | source | - | yes |
| slit3_left | oms58 (?) | `p01/motor/eh2.03` | P01-EH2 | source | - | yes |
| slit3_right | oms58 (?) | `p01/motor/eh2.04` | P01-EH2 | source | - | yes |
| slit3_top | oms58 (?) | `p01/motor/eh2.02` | P01-EH2 | source | - | yes |
| tab1_x | oms58 (?) | `p01/motor/eh1.31` | P01-EH1 | source | - | yes |
| tab1_y | oms58 (?) | `p01/motor/eh1.32` | P01-EH1 | source | - | yes |
| tab2_x | oms58 (?) | `p01/motor/eh2.39` | P01-EH2 | source | - | yes |
| tab2_y | oms58 (?) | `p01/motor/eh2.40` | P01-EH2 | source | - | yes |
| tab4_x | motor_tango (?) | `p01/vmexecutor/eh3_tab2_x` | P01-EH3 | source | - | yes |
| tab4_x1 | oms58 (?) | `p01/motor/eh3.37` | P01-EH3 | source | - | yes |
| tab4_x2 | oms58 (?) | `p01/motor/eh3.38` | P01-EH3 | source | - | yes |
| tab4_y | motor_tango (?) | `p01/vmexecutor/eh3_tab2_y` | P01-EH3 | source | - | yes |
| tab4_y1 | oms58 (?) | `p01/motor/eh3.34` | P01-EH3 | source | - | yes |
| tab4_y2 | oms58 (?) | `p01/motor/eh3.35` | P01-EH3 | source | - | yes |
| tab4_y3 | oms58 (?) | `p01/motor/eh3.36` | P01-EH3 | source | - | yes |
| taper_a | motor_tango (?) | `p01/attributemotor/taper.01` | P01-EH1 | source | - | yes |
| taper_b | motor_tango (?) | `p01/attributemotor/taper.02` | P01-EH1 | source | - | yes |

## Candidate enclosures

`P01-EH1`, `P01-EH2`, `P01-EH3`, `P01-OH1`, `P01-OH2` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **bpm2_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **bpm2_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **bunch_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crl2_rot** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crl2_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crl2_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crl2_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_bragg** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_ener** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_ener_und** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_lat** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_offset** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_para** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_perp** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_pitch** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_roll** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_y** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_y1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_y2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_y3** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det16_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det16_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det16_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **det_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_tth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_bottom** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_bottom** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_top** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dslit_top** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit1_cy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit1_dy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit2_cy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit2_dy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit2_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fe_slit2_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **gap_a** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **gap_b** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_pth** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_ptilt** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm1064_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3d_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3d_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3d_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3d_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3w_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3w_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3w_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm3w_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_pth** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_ptilt** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm400_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm_ener** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hrm_ener2** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ic2_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ic2_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3h_bd** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3h_bu** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3h_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3h_th2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3v_bd** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3v_bu** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3v_th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **kb3v_th2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m1_pitch** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m1_rot** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m1_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m1_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m2_pitch** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m2_rot** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m2_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh1_m2_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **oh2_diam_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **rixs_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **sam_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **sam_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **sam_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samp_b** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samp_rot** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samp_tilt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samp_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samp_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_bottom** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1_top** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01oh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_bottom** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2_top** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_bottom** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3_top** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab1_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab1_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab2_x** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab2_y** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh2:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_x** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_x1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_x2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_y** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_y1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_y2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tab4_y3** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh3:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **taper_a** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **taper_b** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp01eh1:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
