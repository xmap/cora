# Extracted facts: python-nxstools-extras-p09

Machine-extracted candidate facts for `python-nxstools-extras-p09` (facility `petra-iii`). Candidates only; confirm every row before modeling. Source: DESY OnlineXML (the beamline's online_*.xml Tango device registry).

Filtered out 345 bookkeeping rows (counters, timers, registers, measurement groups) not modelled as devices; the inventory below is the modellable remainder.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| SIS3302_1 | GenericProbe | `p09/sis3302/exp.01` | P09-MONO | detection | - | yes |
| SIS3302_1_roi1 | GenericProbe | `p09/sis3302/exp.01/1` | P09-MONO | detection | - | yes |
| SIS3302_1_roi2 | GenericProbe | `p09/sis3302/exp.01/2` | P09-MONO | detection | - | yes |
| SIS3302_1_roi3 | GenericProbe | `p09/sis3302/exp.01/3` | P09-MONO | detection | - | yes |
| SIS3302_1_roi4 | GenericProbe | `p09/sis3302/exp.01/4` | P09-MONO | detection | - | yes |
| SIS3302_1ms_roi1d1 | GenericProbe | `p09/sis3302/exp.01/1` | P09-MONO | detection | - | yes |
| SIS3302_1ms_roi1d2 | GenericProbe | `p09/sis3302/exp.01/2` | P09-MONO | detection | - | yes |
| SIS3302_1ms_roi1d3 | GenericProbe | `p09/sis3302/exp.01/3` | P09-MONO | detection | - | yes |
| SIS3302_1ms_roi1d4 | GenericProbe | `p09/sis3302/exp.01/4` | P09-MONO | detection | - | yes |
| SIS3302_1multiscan | GenericProbe | `p09/sis3302/exp.01` | P09-MONO | detection | - | yes |
| SIS3302_2 | GenericProbe | `p09/sis3302/exp.02` | P09-MONO | detection | - | yes |
| SIS3302_2ms_roi1d1 | GenericProbe | `p09/sis3302/exp.03/1` | P09-MONO | detection | - | yes |
| SIS3302_2ms_roi1d2 | GenericProbe | `p09/sis3302/exp.03/2` | P09-MONO | detection | - | yes |
| SIS3302_2ms_roi1d3 | GenericProbe | `p09/sis3302/exp.03/3` | P09-MONO | detection | - | yes |
| SIS3302_2ms_roi1d4 | GenericProbe | `p09/sis3302/exp.03/4` | P09-MONO | detection | - | yes |
| SIS3302_2multiscan | GenericProbe | `p09/sis3302/exp.03` | P09-MONO | detection | - | yes |
| SIS3302_3 | GenericProbe | `p09/sis3302/exp.03` | P09-MONO | detection | - | yes |
| SIS3302_4 | GenericProbe | `p09/sis3302/exp.04` | P09-MONO | detection | - | yes |
| andor | limaccd (?) | `p09/limaccds/andor.01` | P09-MAG | detection | - | yes |
| exp_mca01 | GenericProbe | `p09/mca/exp.01` | P09-MONO | detection | - | yes |
| lmbd | Camera | `petra3/lambda/01` | ? | detection | - | yes |
| p100 | Camera | `p09/pilatus/p100k` | P09-MAG | detection | - | yes |
| p300 | Camera | `p09/pilatus/300k` | P09-MONO | detection | - | yes |
| dffrctmtr | Diffractometer | `p09/diffractometer/diffrac_eh1` | P09-MONO | sample | - | yes |
| dffrctmtr | Diffractometer | `p09/diffractometer/difsimueh1.01` | P09-DIF | sample | - | yes |
| dffrctmtr | Diffractometer | `p09/diffractometer/diffrac_mag` | P09-MAG | sample | - | yes |
| e6cctrl | Diffractometer | `p09/motor/exp.04` | P09-MONO | sample | - | yes |
| e6cctrl | Diffractometer | `haspp09dif:10000/p09/motor/dif.04` | P09-MAG | sample | - | yes |
| e6cctrleh1 | Diffractometer | `p09/omsvme58/difsimu.01` | P09-DIF | sample | - | yes |
| e6cctrleh2 | Diffractometer | `p09/motor/difsimu.01` | P09-DIF | sample | - | yes |
| G1Bottom | motor_tango (?) | `p09/galildmcslit/exp.02` | P09-MONO | source | - | yes |
| G1Cx | motor_tango (?) | `p09/galildmcslit/exp.05` | P09-MONO | source | - | yes |
| G1Cy | motor_tango (?) | `p09/galildmcslit/exp.06` | P09-MONO | source | - | yes |
| G1Dx | motor_tango (?) | `p09/galildmcslit/exp.07` | P09-MONO | source | - | yes |
| G1Dy | motor_tango (?) | `p09/galildmcslit/exp.08` | P09-MONO | source | - | yes |
| G1Left | motor_tango (?) | `p09/galildmcslit/exp.03` | P09-MONO | source | - | yes |
| G1Right | motor_tango (?) | `p09/galildmcslit/exp.04` | P09-MONO | source | - | yes |
| G1Top | motor_tango (?) | `p09/galildmcslit/exp.01` | P09-MONO | source | - | yes |
| SHexU | motor_tango (?) | `p07/hexapodsmall/U` | ? | source | - | yes |
| SHexV | motor_tango (?) | `p07/hexapodsmall/V` | ? | source | - | yes |
| SHexW | motor_tango (?) | `p07/hexapodsmall/W` | ? | source | - | yes |
| SHexX | motor_tango (?) | `p07/hexapodsmall/X` | ? | source | - | yes |
| SHexY | motor_tango (?) | `p07/hexapodsmall/Y` | ? | source | - | yes |
| SHexZ | motor_tango (?) | `p07/hexapodsmall/Z` | ? | source | - | yes |
| abs | absbox (?) | `p09/absorber/01` | P09-MONO | source | - | yes |
| abs | absbox (?) | `p09/absorbercontroller/mag.01` | P09-MAG | source | - | yes |
| analyzer | motor_tango (?) | `p09/analyzer/eh1.01` | P09-MONO | source | - | yes |
| analyzer | motor_tango (?) | `p09/analyzer/eh2.01` | P09-MAG | source | - | yes |
| ath | oms58 (?) | `p09/motor/exp.15` | P09-MONO | source | - | yes |
| ath | oms58 (?) | `p09/motor/dif.11` | P09-DIF | source | - | yes |
| atth | oms58 (?) | `p09/motor/exp.16` | P09-MONO | source | - | yes |
| atth | oms58 (?) | `p09/motor/dif.12` | P09-DIF | source | - | yes |
| bm | oms58 (?) | `p09/motor/exp.45` | P09-MONO | source | - | yes |
| bpm1 | oms58 (?) | `p09/motor/mono.06` | P09-MONO | source | - | yes |
| bpm2 | oms58 (?) | `p09/motor/exp.46` | P09-MONO | source | - | yes |
| broken | oms58 (?) | `p09/motor/exp.33` | P09-MONO | source | - | yes |
| chi | oms58 (?) | `p09/motor/exp.04` | P09-MONO | source | - | yes |
| chi | oms58 (?) | `p09/omsvme58/difsimu.03` | P09-DIF | source | - | yes |
| chi | oms58 (?) | `p09/motor/dif.05` | P09-DIF | source | - | yes |
| chi_eh2 | oms58 (?) | `p09/motor/dif.05` | P09-DIF | source | - | yes |
| chis_eh2 | oms58 (?) | `p09/motor/dif.39` | P09-DIF | source | - | yes |
| crlbin | absbox (?) | `p09/lensctrl/oh.01` | P09-MONO | source | - | yes |
| crlpi | oms58 (?) | `p09/motor/exp.42` | P09-MONO | source | - | yes |
| crlpi | oms58 (?) | `p09/motor/dif.37` | P09-DIF | source | - | yes |
| crlt | oms58 (?) | `p09/motor/exp.44` | P09-MONO | source | - | yes |
| crlt | oms58 (?) | `p09/motor/dif.36` | P09-DIF | source | - | yes |
| crlx | oms58 (?) | `p09/motor/exp.41` | P09-MONO | source | - | yes |
| crlx | oms58 (?) | `p09/motor/dif.34` | P09-DIF | source | - | yes |
| crlya | oms58 (?) | `p09/motor/exp.43` | P09-MONO | source | - | yes |
| crlya | oms58 (?) | `p09/motor/dif.38` | P09-DIF | source | - | yes |
| crlz | oms58 (?) | `p09/motor/exp.40` | P09-MONO | source | - | yes |
| crlz | oms58 (?) | `p09/motor/dif.35` | P09-DIF | source | - | yes |
| cryocon32tempctrl | module_tango (?) | `p09/cryocontempctrl/exp.01` | P09-MONO | source | - | yes |
| cryox | oms58 (?) | `p09/motor/exp.08` | P09-MONO | source | - | yes |
| cryox | oms58 (?) | `p09/motor/dif.32` | P09-DIF | source | - | yes |
| cryoy | oms58 (?) | `p09/motor/exp.09` | P09-MONO | source | - | yes |
| cryoy | oms58 (?) | `p09/motor/dif.31` | P09-DIF | source | - | yes |
| cryoz | oms58 (?) | `p09/motor/exp.10` | P09-MONO | source | - | yes |
| ctrans | oms58 (?) | `p09/motor/exp.12` | P09-MONO | source | - | yes |
| dcm_bragg | motor_tango (?) | `p09/dcmmotor/mono.01` | P09-MONO | source | - | yes |
| dcm_parallel | oms58 (?) | `p09/motor/mono.09` | P09-MONO | source | - | yes |
| dcm_perp | oms58 (?) | `p09/motor/mono.05` | P09-MONO | source | - | yes |
| del | oms58 (?) | `p09/motor/exp.14` | P09-MONO | source | - | yes |
| del | oms58 (?) | `p09/omsvme58/difsimu.01` | P09-DIF | source | - | yes |
| del | oms58 (?) | `p09/motor/dif.13` | P09-DIF | source | - | yes |
| del_eh2 | oms58 (?) | `p09/motor/dif.13` | P09-DIF | source | - | yes |
| dffrctmtr_hkl | module_tango (?) | `p09/diffractometer/diffrac_eh1-sim-hkl` | P09-MONO | source | - | yes |
| dffrctmtr_hkl | module_tango (?) | `p09/diffractometer/difsimueh1.01-sim-hkl` | P09-DIF | source | - | yes |
| dffrctmtr_hkl | module_tango (?) | `p09/diffractometer/diffrac_mag-sim-hkl` | P09-MONO | source | - | yes |
| diax | oms58 (?) | `p09/motor/exp.50` | P09-MONO | source | - | yes |
| diaz | oms58 (?) | `p09/motor/exp.54` | P09-MONO | source | - | yes |
| dif_mot55 | oms58 (?) | `p09/motor/dif.55` | P09-DIF | source | - | yes |
| dif_mot56 | oms58 (?) | `p09/motor/dif.56` | P09-DIF | source | - | yes |
| dif_mot57 | oms58 (?) | `p09/motor/dif.57` | P09-DIF | source | - | yes |
| dif_mot58 | oms58 (?) | `p09/motor/dif.58` | P09-DIF | source | - | yes |
| dif_mot59 | oms58 (?) | `p09/motor/dif.59` | P09-DIF | source | - | yes |
| dif_mot60 | oms58 (?) | `p09/motor/dif.60` | P09-DIF | source | - | yes |
| dif_mot61 | oms58 (?) | `p09/motor/dif.61` | P09-DIF | source | - | yes |
| dif_mot62 | oms58 (?) | `p09/motor/dif.62` | P09-DIF | source | - | yes |
| dif_mot63 | oms58 (?) | `p09/motor/dif.63` | P09-DIF | source | - | yes |
| dif_mot64 | oms58 (?) | `p09/motor/dif.64` | P09-DIF | source | - | yes |
| diff_height | motor_tango (?) | `p09/vmexecutor/exp.07` | P09-MONO | source | - | yes |
| diff_height | motor_tango (?) | `p09/vmexecutor/dif.07` | P09-DIF | source | - | yes |
| diff_pitch | motor_tango (?) | `p09/vmexecutor/exp.06` | P09-MONO | source | - | yes |
| diff_pitch | motor_tango (?) | `p09/vmexecutor/dif.06` | P09-DIF | source | - | yes |
| diffx | oms58 (?) | `p09/motor/exp.01` | P09-MONO | source | - | yes |
| diffx | oms58 (?) | `p09/motor/dif.01` | P09-DIF | source | - | yes |
| diffz_ds | oms58 (?) | `p09/motor/exp.03` | P09-MONO | source | - | yes |
| diffz_ds | oms58 (?) | `p09/motor/dif.03` | P09-DIF | source | - | yes |
| diffz_us | oms58 (?) | `p09/motor/exp.02` | P09-MONO | source | - | yes |
| diffz_us | oms58 (?) | `p09/motor/dif.02` | P09-DIF | source | - | yes |
| emagvolt | motor_tango (?) | `p09/vmexecutor/exp.20` | P09-MONO | source | - | yes |
| emagvolteh2 | motor_tango (?) | `p09/vmexecutor/mag.01` | P09-MAG | source | - | yes |
| emagz | oms58 (?) | `p09/motor/dif.10` | P09-DIF | source | - | yes |
| energyfmb | motor_tango (?) | `p09/dcmener/mono.01` | P09-MONO | source | - | yes |
| exp_mot48 | oms58 (?) | `p09/motor/exp.48` | P09-MONO | source | - | yes |
| exp_mot49 | oms58 (?) | `p09/motor/exp.49` | P09-MONO | source | - | yes |
| exp_mot55 | oms58 (?) | `p09/motor/exp.55` | P09-MONO | source | - | yes |
| exp_mot56 | oms58 (?) | `p09/motor/exp.56` | P09-MONO | source | - | yes |
| exp_mot57 | oms58 (?) | `p09/motor/exp.57` | P09-MONO | source | - | yes |
| exp_mot58 | oms58 (?) | `p09/motor/exp.58` | P09-MONO | source | - | yes |
| exp_mot59 | oms58 (?) | `p09/motor/exp.59` | P09-MONO | source | - | yes |
| exp_mot60 | oms58 (?) | `p09/motor/exp.60` | P09-MONO | source | - | yes |
| exp_mot61 | oms58 (?) | `p09/motor/exp.61` | P09-MONO | source | - | yes |
| exp_mot62 | oms58 (?) | `p09/motor/exp.62` | P09-MONO | source | - | yes |
| exp_mot63 | oms58 (?) | `p09/motor/exp.63` | P09-MONO | source | - | yes |
| exp_mot64 | oms58 (?) | `p09/motor/exp.64` | P09-MONO | source | - | yes |
| focus | oms58 (?) | `p09/motor/dif.42` | P09-DIF | source | - | yes |
| fsla | module_tango (?) | `p09/fsla/mag.01` | P09-MAG | source | - | yes |
| ga | oms58 (?) | `p09/motor/exp.13` | P09-MONO | source | - | yes |
| ga | oms58 (?) | `p09/omsvme58/difsimu.05` | P09-DIF | source | - | yes |
| ga | oms58 (?) | `p09/motor/dif.14` | P09-DIF | source | - | yes |
| ga_eh2 | oms58 (?) | `p09/motor/dif.14` | P09-DIF | source | - | yes |
| gap | motor_tango (?) | `p09/attributemotor/gap` | P09-MONO | source | - | yes |
| gpib14 | module_tango (?) | `p09/gpib/exp.14` | P09-MONO | source | - | yes |
| gpib15 | module_tango (?) | `p09/gpib/exp.15` | P09-MONO | source | - | yes |
| graz | oms58 (?) | `p09/motor/dif.54` | P09-DIF | source | - | yes |
| hexa_u | motor_tango (?) | `p09/hexapodmotor/mag.04` | P09-MAG | source | - | yes |
| hexa_v | motor_tango (?) | `p09/hexapodmotor/mag.05` | P09-MAG | source | - | yes |
| hexa_w | motor_tango (?) | `p09/hexapodmotor/mag.06` | P09-MAG | source | - | yes |
| hexa_x | motor_tango (?) | `p09/hexapodmotor/mag.01` | P09-MAG | source | - | yes |
| hexa_y | motor_tango (?) | `p09/hexapodmotor/mag.02` | P09-MAG | source | - | yes |
| hexa_z | motor_tango (?) | `p09/hexapodmotor/mag.03` | P09-MAG | source | - | yes |
| hexaconfigsmall | module_tango (?) | `p07/hexapodsmall/config` | ? | source | - | yes |
| k2410 | module_tango (?) | `p09/gpib/keithley2410.01` | P09-MONO | source | - | yes |
| lks336tempctrl | module_tango (?) | `p09/lks336tempctrl/exp.01` | P09-MONO | source | - | yes |
| lks336tempctrleh2 | module_tango (?) | `p09/lks336tempctrl/mag.01` | P09-MAG | source | - | yes |
| lks340tempctrl | module_tango (?) | `p09/lks340tempctrl/exp.01` | P09-MONO | source | - | yes |
| lks340tempctrleh2 | module_tango (?) | `p09/lks340tempctrl/mag.01` | P09-MAG | source | - | yes |
| lscitempctrl | module_tango (?) | `p09/lscitempctrl/exp.01` | P09-MONO | source | - | yes |
| m1pitch | spk (?) | `p09/spk/exp.01` | P09-MONO | source | - | yes |
| m1x | spk (?) | `p09/spk/exp.02` | P09-MONO | source | - | yes |
| m1y | spk (?) | `p09/spk/exp.04` | P09-MONO | source | - | yes |
| m1yaw | spk (?) | `p09/spk/exp.03` | P09-MONO | source | - | yes |
| m2bender | spk (?) | `p09/spk/exp.09` | P09-MONO | source | - | yes |
| m2pitch | spk (?) | `p09/spk/exp.05` | P09-MONO | source | - | yes |
| m2x | spk (?) | `p09/spk/exp.06` | P09-MONO | source | - | yes |
| m2y | spk (?) | `p09/spk/exp.08` | P09-MONO | source | - | yes |
| m2yaw | spk (?) | `p09/spk/exp.07` | P09-MONO | source | - | yes |
| magnet14tf | module_tango (?) | `p09/magnet/exp.01` | P09-MAG | source | - | yes |
| mchi2 | oms58 (?) | `p09/motor/mono.02` | P09-MONO | source | - | yes |
| mirz | oms58 (?) | `p09/motor/exp.47` | P09-MONO | source | - | yes |
| mj1 | oms58 (?) | `p09/motor/mono.03` | P09-MONO | source | - | yes |
| mj2 | oms58 (?) | `p09/motor/mono.04` | P09-MONO | source | - | yes |
| mj3 | oms58 (?) | `p09/motor/mono.07` | P09-MONO | source | - | yes |
| mnchrmtr | motor_tango (?) | `p09/multiplemotors/mono.01` | P09-MONO | source | - | yes |
| mnchrmtr | motor_tango (?) | `p09/tangomotor/dif.01` | P09-DIF | source | - | yes |
| mono_mot31 | oms58 (?) | `p09/motor/mono.31` | P09-MONO | source | - | yes |
| mono_mot32 | oms58 (?) | `p09/motor/mono.32` | P09-MONO | source | - | yes |
| mtable | motor_tango (?) | `p09/vmexecutor/exp.02` | P09-MONO | source | - | yes |
| mth2 | oms58 (?) | `p09/motor/mono.01` | P09-MONO | source | - | yes |
| mu | oms58 (?) | `p09/motor/exp.06` | P09-MONO | source | - | yes |
| mu | oms58 (?) | `p09/omsvme58/difsimu.06` | P09-DIF | source | - | yes |
| mu | motor_tango (?) | `p09/diffracmu/mag.01` | P09-MAG | source | - | yes |
| mx | oms58 (?) | `p09/motor/mono.08` | P09-MONO | source | - | yes |
| myaw | oms58 (?) | `p09/motor/mono.11` | P09-MONO | source | - | yes |
| pchi | motor_tango (?) | `p09/attocubeanc300motor/exp.01` | P09-MONO | source | - | yes |
| pe_ctrl | module_tango (?) | `p09/pectrl/exp.01` | P09-MONO | source | - | yes |
| pe_detector | module_tango (?) | `p09/pedetector/exp.01` | P09-MONO | source | - | yes |
| peta | oms58 (?) | `p09/motor/exp.19` | P09-MONO | source | - | yes |
| peta | oms58 (?) | `p09/motor/dif.17` | P09-DIF | source | - | yes |
| phaseretardercircle1 | motor_tango (?) | `p09/phaseretarder/mono.01` | P09-MONO | source | - | yes |
| phaseretardercircle2 | motor_tango (?) | `p09/phaseretarder/mono.02` | P09-MONO | source | - | yes |
| phi | oms58 (?) | `p09/motor/exp.07` | P09-MONO | source | - | yes |
| phi | oms58 (?) | `p09/omsvme58/difsimu.04` | P09-DIF | source | - | yes |
| phi | oms58 (?) | `p09/motor/dif.06` | P09-DIF | source | - | yes |
| phis_eh2 | oms58 (?) | `p09/motor/dif.40` | P09-DIF | source | - | yes |
| piezo_x | motor_tango (?) | `p09/piezopie725/mag.01` | P09-MAG | source | - | yes |
| piezo_y | motor_tango (?) | `p09/piezopie725/mag.02` | P09-MAG | source | - | yes |
| piezo_z | motor_tango (?) | `p09/piezopie725/mag.03` | P09-MAG | source | - | yes |
| pilc | module_tango (?) | `p09/xmcd/exp.01` | P09-MONO | source | - | yes |
| pperp | motor_tango (?) | `p09/attocubeanc300motor/exp.02` | P09-MONO | source | - | yes |
| pr1chi | oms58 (?) | `p09/motor/mono.13` | P09-MONO | source | - | yes |
| pr1th | oms58 (?) | `p09/motor/mono.14` | P09-MONO | source | - | yes |
| pr1tth | oms58 (?) | `p09/motor/mono.15` | P09-MONO | source | - | yes |
| pr1xt | oms58 (?) | `p09/motor/mono.10` | P09-MONO | source | - | yes |
| pr1zs | oms58 (?) | `p09/motor/mono.16` | P09-MONO | source | - | yes |
| pr1zt | oms58 (?) | `p09/motor/mono.12` | P09-MONO | source | - | yes |
| pr2chi | oms58 (?) | `p09/motor/mono.19` | P09-MONO | source | - | yes |
| pr2th | oms58 (?) | `p09/motor/mono.20` | P09-MONO | source | - | yes |
| pr2tth | oms58 (?) | `p09/motor/mono.21` | P09-MONO | source | - | yes |
| pr2xt | oms58 (?) | `p09/motor/mono.17` | P09-MONO | source | - | yes |
| pr2zs | oms58 (?) | `p09/motor/mono.22` | P09-MONO | source | - | yes |
| pr2zt | oms58 (?) | `p09/motor/mono.18` | P09-MONO | source | - | yes |
| pr2zx | oms58 (?) | `p09/motor/mono.22` | P09-MONO | source | - | yes |
| prpitch | oms58 (?) | `p09/motor/mono.23` | P09-MONO | source | - | yes |
| pryaw | oms58 (?) | `p09/motor/mono.24` | P09-MONO | source | - | yes |
| ps1gap | oms58 (?) | `p09/motor/mono.25` | P09-MONO | source | - | yes |
| ps1off | oms58 (?) | `p09/motor/mono.26` | P09-MONO | source | - | yes |
| ps2gap | oms58 (?) | `p09/motor/mono.27` | P09-MONO | source | - | yes |
| ps2left | oms58 (?) | `p09/motor/mono.29` | P09-MONO | source | - | yes |
| ps2off | oms58 (?) | `p09/motor/mono.28` | P09-MONO | source | - | yes |
| ps2right | oms58 (?) | `p09/motor/mono.30` | P09-MONO | source | - | yes |
| psim | motor_tango (?) | `p09/attributemotor/magnet14tf.rotatorposition` | P09-MAG | source | - | yes |
| pth | oms58 (?) | `p09/motor/exp.28` | P09-MONO | source | - | yes |
| pth | oms58 (?) | `p09/motor/dif.15` | P09-DIF | source | - | yes |
| ptrans | oms58 (?) | `p09/motor/exp.11` | P09-MONO | source | - | yes |
| ptth | motor_tango (?) | `p09/vmexecutor/exp.08` | P09-MONO | source | - | yes |
| ptth | motor_tango (?) | `p09/vmexecutor/dif.08` | P09-DIF | source | - | yes |
| ptth_trans | oms58 (?) | `p09/motor/exp.18` | P09-MONO | source | - | yes |
| ptth_trans | oms58 (?) | `p09/motor/dif.16` | P09-DIF | source | - | yes |
| qbpm1 | oms58 (?) | `p09/motor/mono.06` | P09-MONO | source | - | yes |
| qbpm2 | oms58 (?) | `p09/motor/exp.46` | P09-MONO | source | - | yes |
| rotm | motor_tango (?) | `p09/attributemotor/magnet14tf.soloistposition` | P09-MAG | source | - | yes |
| s1cx | motor_tango (?) | `p09/vmexecutor/exp.18` | P09-MONO | source | - | yes |
| s1cy | motor_tango (?) | `p09/vmexecutor/exp.19` | P09-MONO | source | - | yes |
| s1dx | motor_tango (?) | `p09/vmexecutor/exp.09` | P09-MONO | source | - | yes |
| s1dy | motor_tango (?) | `p09/vmexecutor/exp.04` | P09-MONO | source | - | yes |
| s2cx | motor_tango (?) | `p09/vmexecutor/exp.16` | P09-MONO | source | - | yes |
| s2cy | motor_tango (?) | `p09/vmexecutor/exp.17` | P09-MONO | source | - | yes |
| s2dx | motor_tango (?) | `p09/vmexecutor/exp.11` | P09-MONO | source | - | yes |
| s2dy | motor_tango (?) | `p09/vmexecutor/exp.10` | P09-MONO | source | - | yes |
| s3cx | motor_tango (?) | `p09/vmexecutor/exp.14` | P09-MONO | source | - | yes |
| s3cy | motor_tango (?) | `p09/vmexecutor/exp.15` | P09-MONO | source | - | yes |
| s3dx | motor_tango (?) | `p09/vmexecutor/exp.13` | P09-MONO | source | - | yes |
| s3dy | motor_tango (?) | `p09/vmexecutor/exp.12` | P09-MONO | source | - | yes |
| s4cx | motor_tango (?) | `p09/vmexecutor/s4cx.01` | P09-MONO | source | - | yes |
| s4cy | motor_tango (?) | `p09/vmexecutor/s4cy.01` | P09-MONO | source | - | yes |
| s4dx | motor_tango (?) | `p09/vmexecutor/s4dx.01` | P09-MONO | source | - | yes |
| s4dy | motor_tango (?) | `p09/vmexecutor/s4dy.01` | P09-MONO | source | - | yes |
| s5cx | motor_tango (?) | `p09/vmexecutor/dif.15` | P09-DIF | source | - | yes |
| s5cy | motor_tango (?) | `p09/vmexecutor/dif.16` | P09-DIF | source | - | yes |
| s5dx | motor_tango (?) | `p09/vmexecutor/dif.02` | P09-DIF | source | - | yes |
| s5dy | motor_tango (?) | `p09/vmexecutor/dif.01` | P09-DIF | source | - | yes |
| s6cx | motor_tango (?) | `p09/vmexecutor/dif.13` | P09-DIF | source | - | yes |
| s6cy | motor_tango (?) | `p09/vmexecutor/dif.14` | P09-DIF | source | - | yes |
| s6dx | motor_tango (?) | `p09/vmexecutor/dif.11` | P09-DIF | source | - | yes |
| s6dy | motor_tango (?) | `p09/vmexecutor/dif.10` | P09-DIF | source | - | yes |
| samx | oms58 (?) | `p09/motor/dif.39` | P09-DIF | source | - | yes |
| samy | oms58 (?) | `p09/motor/dif.40` | P09-DIF | source | - | yes |
| samz | oms58 (?) | `p09/motor/dif.41` | P09-DIF | source | - | yes |
| scanx | motor_tango (?) | `p09/piezopie710/mag.01` | P09-MAG | source | - | yes |
| scany | motor_tango (?) | `p09/piezopie710/mag.02` | P09-MAG | source | - | yes |
| scanz | motor_tango (?) | `p09/piezopie710/mag.03` | P09-MAG | source | - | yes |
| slit1d | oms58 (?) | `p09/motor/exp.37` | P09-MONO | source | - | yes |
| slit1l | oms58 (?) | `p09/motor/exp.39` | P09-MONO | source | - | yes |
| slit1r | oms58 (?) | `p09/motor/exp.38` | P09-MONO | source | - | yes |
| slit1u | oms58 (?) | `p09/motor/exp.36` | P09-MONO | source | - | yes |
| slit2d | oms58 (?) | `p09/motor/exp.21` | P09-MONO | source | - | yes |
| slit2l | oms58 (?) | `p09/motor/exp.23` | P09-MONO | source | - | yes |
| slit2r | oms58 (?) | `p09/motor/exp.22` | P09-MONO | source | - | yes |
| slit2u | oms58 (?) | `p09/motor/exp.20` | P09-MONO | source | - | yes |
| slit3d | oms58 (?) | `p09/motor/exp.25` | P09-MONO | source | - | yes |
| slit3l | oms58 (?) | `p09/motor/exp.26` | P09-MONO | source | - | yes |
| slit3r | oms58 (?) | `p09/motor/exp.27` | P09-MONO | source | - | yes |
| slit3u | oms58 (?) | `p09/motor/exp.24` | P09-MONO | source | - | yes |
| slit4d | oms58 (?) | `p09/motor/exp.30` | P09-MONO | source | - | yes |
| slit4l | oms58 (?) | `p09/motor/exp.35` | P09-MONO | source | - | yes |
| slit4r | oms58 (?) | `p09/motor/exp.34` | P09-MONO | source | - | yes |
| slit4u | oms58 (?) | `p09/motor/exp.29` | P09-MONO | source | - | yes |
| slit5d | oms58 (?) | `p09/motor/dif.19` | P09-DIF | source | - | yes |
| slit5l | oms58 (?) | `p09/motor/dif.21` | P09-DIF | source | - | yes |
| slit5r | oms58 (?) | `p09/motor/dif.20` | P09-DIF | source | - | yes |
| slit5u | oms58 (?) | `p09/motor/dif.18` | P09-DIF | source | - | yes |
| slit6d | oms58 (?) | `p09/motor/dif.23` | P09-DIF | source | - | yes |
| slit6l | oms58 (?) | `p09/motor/dif.25` | P09-DIF | source | - | yes |
| slit6r | oms58 (?) | `p09/motor/dif.24` | P09-DIF | source | - | yes |
| slit6u | oms58 (?) | `p09/motor/dif.22` | P09-DIF | source | - | yes |
| spar | motor_tango (?) | `p09/vmexecutor/dif.19` | P09-DIF | source | - | yes |
| sperp | motor_tango (?) | `p09/vmexecutor/exp.21` | P09-MONO | source | - | yes |
| sperp | motor_tango (?) | `p09/vmexecutor/dif.09` | P09-DIF | source | - | yes |
| table_height | motor_tango (?) | `p09/vmexecutor/exp.01` | P09-MONO | source | - | yes |
| table_height | motor_tango (?) | `p09/vmexecutor/dif.04` | P09-DIF | source | - | yes |
| table_height_eh1 | motor_tango (?) | `p09/vmexecutor/exp.01` | P09-MONO | source | - | yes |
| table_pitch | motor_tango (?) | `p09/vmexecutor/exp.03` | P09-MONO | source | - | yes |
| tablex | oms58 (?) | `p09/motor/exp.51` | P09-MONO | source | - | yes |
| tablex | motor_tango (?) | `p09/vmexecutor/dif.03` | P09-DIF | source | - | yes |
| tablex_ds | oms58 (?) | `p09/motor/dif.50` | P09-DIF | source | - | yes |
| tablex_eh1 | oms58 (?) | `p09/motor/exp.51` | P09-MONO | source | - | yes |
| tablex_eh2 | motor_tango (?) | `p09/vmexecutor/dif.03` | P09-DIF | source | - | yes |
| tablex_us | oms58 (?) | `p09/motor/dif.49` | P09-DIF | source | - | yes |
| tablez_ds | oms58 (?) | `p09/motor/exp.53` | P09-MONO | source | - | yes |
| tablez_dsl | oms58 (?) | `p09/motor/dif.52` | P09-DIF | source | - | yes |
| tablez_dsr | oms58 (?) | `p09/motor/dif.53` | P09-DIF | source | - | yes |
| tablez_us | oms58 (?) | `p09/motor/exp.52` | P09-MONO | source | - | yes |
| tablez_us | oms58 (?) | `p09/motor/dif.51` | P09-DIF | source | - | yes |
| tga_1240 | module_tango (?) | `p09/tga1240wavegen/mono.01` | P09-MONO | source | - | yes |
| tga_ampl | motor_tango (?) | `p09/attributemotor/tga1240.amplitude` | P09-MONO | source | - | yes |
| tga_off | motor_tango (?) | `p09/attributemotor/tga1240.dcoffset` | P09-MONO | source | - | yes |
| th | oms58 (?) | `p09/motor/exp.05` | P09-MONO | source | - | yes |
| th | oms58 (?) | `p09/omsvme58/difsimu.02` | P09-DIF | source | - | yes |
| th | oms58 (?) | `p09/motor/dif.04` | P09-DIF | source | - | yes |
| ths | oms58 (?) | `p09/motor/dif.26` | P09-DIF | source | - | yes |
| ugap | motor_tango (?) | `p09/vmexecutor/exp.05` | P09-MONO | source | - | yes |
| undulator | motor_tango (?) | `p09/undulator/1` | P09-MONO | source | - | yes |
| user1 | oms58 (?) | `p09/motor/dif.33` | P09-DIF | source | - | yes |
| user6 | oms58 (?) | `p09/motor/dif.45` | P09-DIF | source | - | yes |
| user7 | oms58 (?) | `p09/motor/dif.46` | P09-DIF | source | - | yes |
| user8 | oms58 (?) | `p09/motor/dif.47` | P09-DIF | source | - | yes |
| user9 | oms58 (?) | `p09/motor/dif.48` | P09-DIF | source | - | yes |
| vmth2th | motor_tango (?) | `p09/vmexecutor/exp.22` | P09-MONO | source | - | yes |
| xs | oms58 (?) | `p09/motor/dif.08` | P09-DIF | source | - | yes |
| xs_eh2 | oms58 (?) | `p09/motor/dif.08` | P09-DIF | source | - | yes |
| ys | oms58 (?) | `p09/motor/dif.09` | P09-DIF | source | - | yes |
| ys_eh2 | oms58 (?) | `p09/motor/dif.09` | P09-DIF | source | - | yes |
| zfx | oms58 (?) | `p09/motor/dif.43` | P09-DIF | source | - | yes |
| zfy | oms58 (?) | `p09/motor/dif.44` | P09-DIF | source | - | yes |
| zs | oms58 (?) | `p09/motor/dif.07` | P09-DIF | source | - | yes |
| zs_eh2 | oms58 (?) | `p09/motor/dif.07` | P09-DIF | source | - | yes |

## Candidate enclosures

`P09-DIF`, `P09-MAG`, `P09-MONO` (all inferred, confirm).

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

No user_group_permissions.yaml found.

## Open confirms

- **G1Bottom** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Left** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Right** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **G1Top** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexU** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexV** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexW** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexX** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexY** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SHexZ** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1** (`sis3302`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1_roi1** (`sis3302`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1_roi2** (`sis3302`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1_roi3** (`sis3302`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1_roi4** (`sis3302`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1ms_roi1d1** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1ms_roi1d2** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1ms_roi1d3** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1ms_roi1d4** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_1multiscan** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2** (`mca_sis3302new`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2ms_roi1d1** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2ms_roi1d2** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2ms_roi1d3** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2ms_roi1d4** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_2multiscan** (`sis3302multiscan`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_3** (`mca_sis3302new`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **SIS3302_4** (`mca_sis3302new`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **abs** (`absbox`)
    - family is the Tango module 'absbox'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **abs** (`absbox`)
    - family is the Tango module 'absbox'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **analyzer** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **analyzer** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **andor** (`limaccd`)
    - family is the Tango module 'limaccd'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ath** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ath** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **atth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **atth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **bm** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **bpm1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **bpm2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **broken** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **chi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **chi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **chi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **chi_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **chis_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlbin** (`absbox`)
    - family is the Tango module 'absbox'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlpi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlpi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlya** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlya** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **crlz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryocon32tempctrl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryox** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryox** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryoy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryoy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **cryoz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ctrans** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_bragg** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_parallel** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dcm_perp** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **del** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **del** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **del** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **del_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr** (`e6c`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr** (`e6c`)
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr** (`e6c_p09_eh2`)
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr_hkl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr_hkl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dffrctmtr_hkl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diax** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diaz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot55** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot56** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot57** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot58** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot59** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot60** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot61** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot62** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot63** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **dif_mot64** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_height** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_height** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_pitch** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diff_pitch** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffz_ds** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffz_ds** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffz_us** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **diffz_us** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **e6cctrl** (`E6C`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **e6cctrl** (`PETRA3 P09 EH2`)
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **e6cctrleh1** (`E6C`)
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **e6cctrleh2** (`PETRA3 P09 EH2`)
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **emagvolt** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **emagvolteh2** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **emagz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **energyfmb** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mca01** (`mca_8701`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot48** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot49** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot55** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot56** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot57** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot58** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot59** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot60** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot61** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot62** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot63** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **exp_mot64** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **focus** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **fsla** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ga** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ga** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ga** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ga_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **gap** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **gpib14** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **gpib15** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **graz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_u** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_v** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_w** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_x** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_y** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexa_z** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **hexaconfigsmall** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'hzgpp07eh3:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **k2410** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lks336tempctrl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lks336tempctrleh2** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lks340tempctrl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lks340tempctrleh2** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lmbd** (`lambda`)
    - Tango host 'haslambda01:10000'; endstation to enclosure is a guess
    - enclosure unresolved from Tango host
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **lscitempctrl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m1pitch** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m1x** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m1y** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m1yaw** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m2bender** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m2pitch** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m2x** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m2y** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **m2yaw** (`spk`)
    - family is the Tango module 'spk'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **magnet14tf** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mchi2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mirz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mj1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mj2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mj3** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mnchrmtr** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mnchrmtr** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mono_mot31** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mono_mot32** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mtable** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mth2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mu** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mu** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mu** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **mx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **myaw** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **p100** (`pilatus100k`)
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **p300** (`pilatus300k`)
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pchi** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pe_ctrl** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pe_detector** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **peta** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **peta** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phaseretardercircle1** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phaseretardercircle2** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **phis_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **piezo_x** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **piezo_y** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **piezo_z** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pilc** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pperp** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1chi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1tth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1xt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1zs** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr1zt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2chi** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2tth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2xt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2zs** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2zt** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pr2zx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **prpitch** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pryaw** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps1gap** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps1off** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps2gap** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps2left** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps2off** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ps2right** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **psim** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **pth** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ptrans** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ptth** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ptth** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ptth_trans** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ptth_trans** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **qbpm1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **qbpm2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **rotm** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s1cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s1cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s1dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s1dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s2cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s2cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s2dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s2dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s3cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s3cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s3dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s3dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s4cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s4cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s4dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s4dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s5cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s5cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s5dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s5dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s6cx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s6cy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s6dx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **s6dy** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **samz** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **scanx** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **scany** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **scanz** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mag:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit1u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit2u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit3u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit4d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit4l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit4r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit4u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit5d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit5l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit5r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit5u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit6d** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit6l** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit6r** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **slit6u** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **spar** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **sperp** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **sperp** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **table_height** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **table_height** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **table_height_eh1** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **table_pitch** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex_ds** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex_eh1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex_eh2** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablex_us** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablez_ds** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablez_dsl** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablez_dsr** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablez_us** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tablez_us** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tga_1240** (`module_tango`)
    - family is the Tango module 'module_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tga_ampl** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **tga_off** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **th** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ths** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ugap** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **undulator** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **user1** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **user6** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **user7** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **user8** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **user9** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **vmth2th** (`motor_tango`)
    - family is the Tango module 'motor_tango'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09mono:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **xs** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **xs_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ys** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **ys_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **zfx** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **zfy** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **zs** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
- **zs_eh2** (`oms58`)
    - family is the Tango module 'oms58'; linear-vs-rotary and the CORA Family need a human
    - Tango host 'haspp09dif:10000'; endstation to enclosure is a guess
    - axis granularity: one OnlineXML <device> is one axis or channel; Asset grouping needs a human
