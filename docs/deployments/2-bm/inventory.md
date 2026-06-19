# Inventory

The 2-BM equipment inventory: the CORA Asset model view (the device tree, settings, vendor Models, drawings, and signal wiring) plus the computed axes. Live condition is served by the app, not this page.

## Assets

One row per registered Asset under the `2-BM` root (`tier = Unit`, bound to its Site Facility via `facility_code`). Hutches `2-BM-A` (optics) / `2-BM-B` (experiment) are [Enclosures](enclosures.md), not Assets. Condition is served live by the app.

| Asset | Family | Model | Parent | Key settings | Condition |
| --- | --- | --- | --- | --- | --- |
| `StationShutter` | `Shutter` | (none cited) | `2-BM` | - | live |
| `SampleTable` | `Table` | (none) | `2-BM` | `axis_layout=translation_xyz` | live |
| `RotaryDriveChassis` | `Housing` | `aerotech_tm3a` | `2-BM` | serial `160591-A-1-1`, order `730578` | live |
| `RotaryDrive` | `MotionController` | `aerotech_ensemble_ml` | `RotaryDriveChassis` | serial `730792/1`, `axis_count=1`, `Aerotech_Native` | live |
| `Rotary` | `RotaryStage` | `aerotech_abrs250mp` | `LaminographyPitch` | -360..360 deg, `max_speed=720 deg/s`, `encoder_resolution=0.000676 deg` | live |
| `SampleStageDrive` | `MotionController` | `oms_vme58` | `2-BM` | `axis_count=91`, `OMS_VME` | live |
| `FrontEndDrive` | `MotionController` | `oms_vme58` | `2-BM` | `axis_count=91`, `OMS_VME` | live |
| `Mirror` | `Mirror` | (none) | `MirrorTable` | driven by `FrontEndDrive` | live |
| `MirrorTable` | `Table` | (none) | `2-BM` | `axis_layout=virtual_pose`, `virtual_record=2bma:table1` | live |
| `Monochromator` | `Monochromator` | (none) | `2-BM` | driven by `FrontEndDrive` | live |
| `Monochromator_BraggArmUpstream` | `PseudoAxis` | (none) | `Monochromator` | energy->upstream Bragg arm (deg) | live |
| `Monochromator_BraggArmDownstream` | `PseudoAxis` | (none) | `Monochromator` | energy->downstream Bragg arm (deg) | live |
| `Monochromator_M2Y` | `PseudoAxis` | (none) | `Monochromator` | energy->M2 vertical offset (mm) | live |
| `ConditioningSlit` | `Slit` | (none) | `2-BM` | white-beam slits; driven by `FrontEndDrive` | live |
| `Filter` | `Filter` | (none) | `2-BM` | foil changer; driven by `FrontEndDrive` | live |
| `Filter_FoilSelector` | `PseudoAxis` | (none) | `Filter` | slot index -> paddle position (Nearest) | live |
| `DiagnosticFlag` | `LinearStage` | (none) | `2-BM` | `2bma:m44`; raised in Mono, parked in Pink | live |
| `SampleSlit` | `Slit` | (none) | `2-BM` | B-station slits; driven by `FrontEndDrive` | live |
| `SampleSlit_VerticalTop` | `PseudoAxis` | (none) | `SampleSlit` | energy->top blade beam position (mm) | live |
| `SampleSlit_VerticalBottom` | `PseudoAxis` | (none) | `SampleSlit` | energy->bottom blade beam position (mm) | live |
| `SampleTop_X` | `LinearStage` | `kohzu_cyat070` | `Rotary` | -10..10 mm, `max_speed=1 mm/s`, `encoder_resolution=0.0005 mm` | live |
| `SampleTop_Z` | `LinearStage` | `kohzu_cyat070` | `SampleTop_X` | same Model/controller as `SampleTop_X` | live |
| `HexapodDrive` | `MotionController` | `aerotech_automation1_ixr3` | `2-BM` | serial `486125-01`, `axis_count=6`, `Aerotech_Native` | live |
| `Hexapod` | `Hexapod` | `aerotech_hex300` | `SampleTable` | serial `486060-01`; full HEX300 envelope (see Settings) | live |
| `Hexapod_X` | `PseudoAxis` | (none) | `Hexapod` | DoF; translation X | live |
| `Hexapod_Y` | `PseudoAxis` | (none) | `Hexapod` | DoF; translation Y | live |
| `Hexapod_Z` | `PseudoAxis` | (none) | `Hexapod` | DoF; translation Z; modelled, not wired in current EPICS | modelled (unwired) |
| `Hexapod_Roll` | `PseudoAxis` | (none) | `Hexapod` | DoF; rotation A about X | live |
| `Hexapod_Pitch` | `PseudoAxis` | (none) | `Hexapod` | DoF; rotation B about Y | live |
| `Hexapod_Yaw` | `PseudoAxis` | (none) | `Hexapod` | DoF; rotation C about Z; modelled, not wired in current EPICS | modelled (unwired) |
| `LaminographyPitch` | `TiltStage` | `kohzu_sa16a` | `Hexapod` | Kohzu SA16A `2bmb:m49`; tomo/lamino = tilt setpoint | live |
| `PropagationDistanceDrive` | `MotionController` | `aerotech_ensemble_hle` | `2-BM` | serial `228849-02`, `axis_count=1`, `Aerotech_Native` | live |
| `Timing` | `TimingController` | (none) | `2-BM` | softGlueZynq trigger box; `protocol=EPICS`; no `controller_id` | live |
| `OpticsFineDrive` | `MotionController` | `piezosystem_jena_nv100d` | `2-BM` | Jena NV100D; drives deferred XY piezo axes | live (provisional name) |
| `SampleFineDrive` | `MotionController` | `piezosystem_jena_nv200d` | `2-BM` | Jena NV200D; FPGA-stepped via `Timing` | live (provisional name) |
| `DetectorTable` | `Table` | (none) | `2-BM` | `axis_layout=virtual_pose`, `virtual_record=2bmb:table3` | live |
| `DetectorTable_X` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; `2bmb:table3.X` | live |
| `DetectorTable_Y` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; `2bmb:table3.Y` | live |
| `DetectorTable_Z` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; `2bmb:table3.Z` | live |
| `DetectorTable_Roll` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; raw `AZ`; `2bmb:table3.AZ` | live |
| `DetectorTable_Pitch` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; raw `AX`; `2bmb:table3.AX` | live |
| `DetectorTable_Yaw` | `PseudoAxis` | (none) | `DetectorTable` | IOC virtual axis; raw `AY`; `2bmb:table3.AY` | live |
| `Housing` | `Housing` | (none) | `PropagationDistance` | Microscope chassis; installed into a Mount | live |
| `Turret` | `LinearStage` | (microscope catalog) | `Housing` | -60.030..58.640 mm, `encoder_resolution=0.0016 mm` | live |
| `Objective_10x` | `Objective` | (microscope catalog) | `Housing` | mag 10.0, NA 0.28, f=20 mm, WD 33.5 mm | live |
| `Objective_2x` | `Objective` | (microscope catalog) | `Housing` | mag 2.0, NA 0.055, f=100 mm, WD 34 mm | live |
| `Objective_1.1x` | `Objective` | (microscope catalog) | `Housing` | mag 1.1, NA 0.03, f=200 mm, WD 50 mm | live |
| `Objective_Selector` | `PseudoAxis` | (none) | `Housing` | writes MCTOptics `LensSelect`; lens->turret partition rule | live |
| `PropagationDistance` | `LinearStage` | `aerotech_pro225sl` | `DetectorTable` | sample-to-detector rail; driven by `PropagationDistanceDrive` | live |
| `Camera` | `Camera` | (microscope catalog) | `Housing` | 5 MP FLIR Oryx; 2448x2048, 3.45 um, 12 bit, 162 Hz, CMOS GlobalShutter | live |
| `Camera_HighRes` | `Camera` | `flir_oryx_31mp` | `Housing` | 31 MP FLIR Oryx; pixel 3.45 um; other settings pending | live (settings pending) |
| `Camera_Selector` | `LinearStage` | `schunk_lptm_30` | `Housing` | Schunk LPTM 30; Pos.0=20, Pos.1=15; stage settings pending | live (settings pending) |
| `Scintillator` | `Scintillator` | (microscope catalog) | `Housing` | thickness 100 um, decay 0.07 us | live |

Microscope-bound Models (turret motor, Mitutoyo MPLAPO kit, FLIR Oryx, Crytur LuAG) live on the [Microscope deployment](equipment/microscope.md#vendor-catalog) page. The `kohzu_sa16a` binding for `LaminographyPitch` is on the [Sample tower](equipment/sample_tower.md) page.

## Settings

Per-asset settings the source spells out in prose. Open-item tags (DRIVE-1, DRIVE-2, TIME-1) kept inline.

| Asset | Settings |
| --- | --- |
| `SampleTable` | `axis_layout=translation_xyz`; direct motors `2bmb:m24` Y, `2bmb:m20` Z, `2bmb:m21` X-up, `2bmb:m22` X-down |
| `DetectorTable` | `axis_layout=virtual_pose`; `virtual_record=2bmb:table3`; `geometry=SRI: 3 Y-supports, 2 X-supports, 1 Z-support` |
| `MirrorTable` | `axis_layout=virtual_pose`; `virtual_record=2bma:table1`; `geometry=SRI support table`; X axes `M0X`/`M2X` driven by energy-change IOC; bind table-X surface only until `M1Y=2bma:m3` IOC substitution error fixed |
| `RotaryDrive` | `serial_number=730792/1`; `firmware_version=unknown-pending-confirmation` (DRIVE-2); `axis_count=1`; `protocol=Aerotech_Native`; installed in `RotaryDriveChassis` |
| `RotaryDriveChassis` | altids: serial `160591-A-1-1` (SerialNumber), order `730578` (Other); drawing `630D2079 REV-H`; inventory-only, no command surface |
| `PropagationDistanceDrive` | `serial_number=228849-02`; `firmware_version=unknown-pending-confirmation` (DRIVE-2); `axis_count=1`; `protocol=Aerotech_Native`; IOC handle `2bmbAERO` (EPICS_PV altid); addressed `2bmbAERO:m1` |
| `SampleStageDrive` | `serial_number=unknown-pending-confirmation` (DRIVE-1); `firmware_version=unknown-pending-confirmation` (DRIVE-2); `axis_count=91`; `protocol=OMS_VME`; crate `ioc2bmb`, no IP (VME-bus) |
| `FrontEndDrive` | `serial_number=unknown-pending-confirmation` (DRIVE-1); `firmware_version=unknown-pending-confirmation` (DRIVE-2); `axis_count=91`; `protocol=OMS_VME`; crate `ioc2bma`, no IP (VME-bus) |
| `HexapodDrive` | `serial_number=486125-01`; `firmware_version=unknown-pending-confirmation` (DRIVE-2); `axis_count=6`; `protocol=Aerotech_Native`; Automation1-iXR3 in separate rack |
| `Timing` | `serial_number=unknown-pending-confirmation` (TIME-1); `firmware_version=unknown-pending-confirmation` (TIME-1); `output_channel_count=unknown-pending-confirmation` (TIME-1); `protocol=EPICS`; `2bmbMZ1:SG:` |
| `Rotary` | `min_position=-360 deg`; `max_position=360 deg`; `max_speed=720 deg/s`; `encoder_resolution=0.000676 deg`; `homing_offset=0 deg`; altid serial `146853-A-1-1-X`; part `ABRS-250MP-M-AS` |
| `SampleTop_X` | `min_position=-10 mm`; `max_position=10 mm`; `max_speed=1 mm/s`; `encoder_resolution=0.0005 mm`; channel `2bmb:m18` |
| `SampleTop_Z` | same Model `kohzu_cyat070` + controller as `SampleTop_X`; channel `2bmb:m17` |
| `Hexapod` | `travel_x=55 mm`, `travel_y=60 mm`, `travel_z=25 mm`, `travel_a=15 deg`, `travel_b=15 deg`, `travel_c=30 deg`; `max_speed_translation=25 mm/s`, `max_speed_rotation=15 deg/s`; `resolution_translation=20 nm`, `resolution_rotation=0.2 urad`; `accuracy_translation=1 um`, `accuracy_rotation=10 urad`; `load_capacity_vertical=45 kg`, `load_capacity_horizontal=21 kg`; `stage_mass=12 kg`; altid serial `486060-01` |
| `Scintillator` | `thickness=100 um`; `decay_time=0.07 us` |
| `Camera` | `sensor_width=2448 pixel`; `sensor_height=2048 pixel`; `pixel_size=3.45 um`; `bit_depth=12 bit`; `max_framerate_hz=162 Hz`; `sensor_kind=CMOS`; `readout_mode=GlobalShutter`; altids model `Oryx ORX-10G-51S5M`, serial `19173710`, firmware `1710.0.0.0`, EPICS `2bmSP1:` |
| `Camera_HighRes` | model `Oryx ORX-10G-310S9M`; serial `22150530`; firmware `1904.0.72.0`; EPICS `2bmSP2:`; `pixel_size=3.45 um`; remaining `Camera`-schema settings pending |
| `Camera_Selector` | Schunk LPTM 30 (`2bmb:m5`); Pos.0=20, Pos.1=15; `min/max/max_speed/encoder_resolution` pending |
| `Turret` | `min_position=-60.030 mm`; `max_position=58.640 mm`; `encoder_resolution=0.0016 mm`; Nanotec ST4118M1404-B, Heidenhain ERO 1420 encoder; objectives at 1.1x=-60.030 mm, 10x=58.640 mm |
| `Objective_10x` | `magnification=10.0`; `numerical_aperture=0.28`; `focal_length=20 mm`; `working_distance=33.5 mm` |
| `Objective_2x` | `magnification=2.0`; `numerical_aperture=0.055`; `focal_length=100 mm`; `working_distance=34 mm` |
| `Objective_1.1x` | `magnification=1.1`; `numerical_aperture=0.03`; `focal_length=200 mm`; `working_distance=50 mm` |

## Vendor catalog

Models bound to non-microscope 2-BM Assets. Model ids are derived from `(manufacturer, part number)`, so one vendor product converges on one id. Microscope-housing Models are on the [Microscope deployment](equipment/microscope.md#vendor-catalog) page.

| Model | Vendor | Part number | Drives / used by |
| --- | --- | --- | --- |
| `aerotech_hex300` | Aerotech | `HEX300-230HL-E1-PL4-TAS` | `Hexapod` |
| `aerotech_abrs250mp` | Aerotech | `ABRS-250MP-M-AS` | `Rotary` |
| `aerotech_ensemble_ml` | Aerotech | `ENSEMBLEML 10-40-IO-MXH` | `RotaryDrive` |
| `aerotech_automation1_ixr3` | Aerotech | `Automation1-iXR3-VL1-VB4-VB4-SB0CT222222-P1P1P1P1P1P1-CO-LC1MT1PSO6-SI0-TAS` | `HexapodDrive` |
| `aerotech_ensemble_hle` | Aerotech | `EnsembleHLe10-40-A-IO-MXH` | `PropagationDistanceDrive` |
| `aerotech_pro225sl` | Aerotech | `PRO225SL-1000` | `PropagationDistance` |
| `aerotech_tm3a` | Aerotech | `TM3-A-20B VDC-20B VDC / NO SPLIT / PS24-1 / C1ML-06 / C2ML-09 / US-115VAC` | `RotaryDriveChassis` |
| `oms_vme58` | Oregon Micro Systems | `VME58` | `SampleStageDrive`, `FrontEndDrive` |
| `kohzu_cyat070` | Kohzu | `CYAT-070` | `SampleTop_X`, `SampleTop_Z` |
| `piezosystem_jena_nv100d` | Piezosystem Jena | `NV100D` | `OpticsFineDrive` |
| `piezosystem_jena_nv200d` | Piezosystem Jena | `NV200D/NET` | `SampleFineDrive` |

Controller back-references: `RotaryDrive`->`Rotary.controller_id`; `HexapodDrive`->`Hexapod.controller_id`; `PropagationDistanceDrive`->`PropagationDistance.controller_id` (IOC `2bmbAERO`); `SampleStageDrive`->`SampleTop_X` (`2bmb:m18`) / `SampleTop_Z` (`2bmb:m17`) + 89 further motors on `ioc2bmb`; `FrontEndDrive`->`Mirror`, `Monochromator`, `ConditioningSlit`, `SampleSlit`, `Filter` on `ioc2bma`. The `Objective_Selector` (`2bmb:m1`) and `Camera_Selector` (`2bmb:m5`) steppers run through the `SampleStageDrive` OMS crate, not distinct controller Assets. The six `Hexapod_*` DoF facets bind no Model (the physical `Hexapod` carries `aerotech_hex300`).

## Engineering drawings

One canonical `(system, number, revision)` triple per Asset. Optique Peter `MAN-11863` (rev `0521-0465-A`) is the shared housing manual covering every Microscope-bound constituent.

| Asset | Drawing | System |
| --- | --- | --- |
| `Hexapod` | `Hex300-Data-Sheet` rev `D20250203` | `EDMS` |
| `Rotary` | `630C2125` rev `(-)` | `EDMS` |
| `RotaryDriveChassis` | `630D2079` rev `H` | `EDMS` |
| `PropagationDistance` | `MAN-11863` rev `0521-0465-A` | `EDMS` |
| `Turret` | `MAN-11863` rev `0521-0465-A` | `EDMS` |
| `Objective_10x` | `MAN-11863` rev `0521-0465-A` | `EDMS` |
| `Objective_2x` | `MAN-11863` rev `0521-0465-A` | `EDMS` |
| `Objective_1.1x` | `MAN-11863` rev `0521-0465-A` | `EDMS` |
| `Scintillator` | `MAN-11863` rev `0521-0465-A` | `EDMS` |

Not yet cited: Kohzu `CYAT-070` datasheet (`SampleTop_*`), an APS shutter drawing (`StationShutter`), a FLIR Oryx datasheet (`Camera`).

## Signal wiring

Trigger and step signals are modelled as typed ports plus wires resolved at Plan-bind time. Executable model: `apps/api/tests/integration/scenarios/test_2bm_trigger_wiring.py`.

### Fine-positioning piezo controllers

- `OpticsFineDrive` = Jena NV100D (staff item_027), fine optics positioning from the `mct_optics` screen; carries no trigger input (no FPGA stepping).
- `SampleFineDrive` = Jena NV200D/NET (staff item_028), two piezo axes step under FPGA trigger during tomography.
- Both run EPICS IOCs on host `arcturus` (`JenaNV100D` / `JenaNV200D`), drive two piezo axes each (X/Y), two static IPs per box (recorded once confirmed).
- Only the controller boxes are modelled today; the driven XY piezo axes and final controller names are deferred.

### NV200D trigger wiring

| Asset | Port | Direction | `signal_type` |
| --- | --- | --- | --- |
| `Timing` | `out2`, `out3` | OUTPUT | `step_trigger_ttl` |
| `SampleFineDrive` | `step_x_in`, `step_y_in` | INPUT | `step_trigger_ttl` |

- Wires: `Timing.out2 -> SampleFineDrive.step_x_in`, `Timing.out3 -> SampleFineDrive.step_y_in` (JenaX/JenaY land on FPGA `out2`/`out3`, item_028); up to 1024 positions/axis.
- Gate-delay PVs: `2bmbMZ1:SG:GateDly-3_DLY` (labelled "X axis delay"), `2bmbMZ1:SG:GateDly-2_DLY` (labelled "Y axis delay"); the label-to-cable map appears crossed, recorded verbatim and flagged for confirmation.
- Ports sit on the controller box today; they migrate onto per-axis Assets when registered.

### Camera trigger wiring

| Asset | Port | Direction | `signal_type` |
| --- | --- | --- | --- |
| `Timing` | `camera_trigger_out` | OUTPUT | `frame_trigger_ttl` |
| `Camera` | `trigger_in` | INPUT | `frame_trigger_ttl` |

- One wire: `Timing.camera_trigger_out -> Camera.trigger_in` (item_060). `frame_trigger_ttl` (start exposure) is distinct from the piezo `step_trigger_ttl` (advance a motion step).
- Two labels open for staff: the exact FPGA output channel feeding the camera (path ends at camera `Line2`, no box-side output named), and the `GateDly1` block name (unconfirmed vs the source-grounded `GateDly-2`/`GateDly-3`).
- softGlue `Width`/`DLY` count 10 MHz clock cycles (100 ns/count, so `Width=100` = 10 us pulse); per-scan values are Method/Plan config.

## Computed axes

The `PseudoAxis` Assets whose position is computed from the motors underneath, divided by who owns the math: firmware `SolverReference` (hexapod), an edge IOC with no rule (detector table), or a `Calibration`-backed `LookupTable` (energy axes and foil selector). Executable models cited per subsection.

### Hexapod DoF model

One physical Device (vendor-sealed Aerotech HEX300; inverse kinematics in firmware solver `2bmHXP`). Six DoF surfaced as `PseudoAxis` sub-modules, each carrying a `SolverReference` partition rule; per-DoF envelope stays on the `Hexapod` settings, not duplicated onto facets.

| DoF Asset | Kind | Axis | Vendor label | EPICS channel |
| --- | --- | --- | --- | --- |
| `Hexapod_X` | translation | along X | n/a | `2bmHXP:m1` |
| `Hexapod_Y` | translation | along Y | n/a | `2bmHXP:m2` |
| `Hexapod_Z` | translation | along Z | n/a | none (no operator handle) |
| `Hexapod_Roll` | rotation | about X | A (`travel_a`) | `2bmHXP:m5` |
| `Hexapod_Pitch` | rotation | about Y | B (`travel_b`) | `2bmHXP:m4` |
| `Hexapod_Yaw` | rotation | about Z | C (`travel_c`) | none (no operator handle) |

- Z and Yaw exist physically but are not exposed as operator channels in 2-BM's current EPICS (no `m3`/`m6`); CORA still models all six (deployment-configuration limit, not a device one).
- Constituent-port wiring: each DoF reads feedback from `Hexapod` via `Plan.wires` (not a partition-rule field). `Hexapod` exposes `x/y/z_feedback_out` (`position_feedback_linear_mm`) and `roll/pitch/yaw_feedback_out` (`position_feedback_rotation_deg`); each facet has one `constituent_in` INPUT plus one `<axis>_out` setpoint OUTPUT. Six wires, one per DoF (`Hexapod.<axis>_feedback_out -> Hexapod_<Axis>.constituent_in`). `validate_pseudoaxis_fanout` exempts `SolverReference` from the arity check; decomposition is owned by the firmware solver.

### Detector table axes

Six virtual axes on the `2bmb:table3` record, modelled as `PseudoAxis` sub-Assets of `DetectorTable`. No partition rule and no constituent wiring: the `table_full` IOC computes the pose from six support motors (`M0X` / `M0Y` / `M1Y` / `M2X` / `M2Y` / `M2Z`) in SRI geometry. Addressing is a direct ControlPort write to the `table3.*` PV (spine/edge seam). Model: `apps/api/tests/integration/scenarios/test_2bm_optical_tables_setup.py`.

| Axis Asset | Kind | `table3` field | Raw label |
| --- | --- | --- | --- |
| `DetectorTable_X` | translation | `.X` | n/a |
| `DetectorTable_Y` | translation | `.Y` | n/a |
| `DetectorTable_Z` | translation | `.Z` | n/a |
| `DetectorTable_Pitch` | rotation | `.AX` | `AX` |
| `DetectorTable_Yaw` | rotation | `.AY` | `AY` |
| `DetectorTable_Roll` | rotation | `.AZ` | `AZ` |

Angular mapping (`AX`=pitch, `AY`=yaw, `AZ`=roll) is staff-confirmed (STAGE-9).

### Energy-tracking optic axes

Setting energy is a discrete coordinated move. The staff energy-change IOC stores per-energy positions (`store_0` saved table) and drives ~15 motors. Each per-axis relationship is modelled as a continuous curve: a `PseudoAxis` carrying a `LookupTable` partition rule converting energy (`unit_in=keV`) to axis position, pinning a `Calibration` revision by id (`energy_position_curve` quantity, `beam_mode=mono`). `invertible=True` (Bragg geometry monotonic; no constituent wiring needed). Coordinating operation = the `energy_setting` Procedure, which accepts a free keV value between saved points. Models: `test_2bm_energy_curves_setup.py` (curves) + `test_2bm_energy_setting.py` (operation).

Configured Mono energies (the curve x-points, real): 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV. Pink mode bypasses the monochromator. Beam-mode switching itself is on the [Procedures](procedures.md#beam-modes) page, not a virtual axis.

| Axis Asset | Motors / handle | Curve | unit_out |
| --- | --- | --- | --- |
| `Monochromator_BraggArmUpstream` | `dmm_us_arm` | energy -> upstream Bragg arm | deg |
| `Monochromator_BraggArmDownstream` | `dmm_ds_arm` | energy -> downstream Bragg arm | deg |
| `Monochromator_M2Y` | `dmm_m2_y` | energy -> M2 vertical offset compensator | mm |
| `SampleSlit_VerticalTop` | `b_slit_top` | energy -> top blade beam-walk | mm |
| `SampleSlit_VerticalBottom` | `b_slit_bot` | energy -> bottom blade beam-walk | mm |

- Not energy axes: `crystal2_z` (M2 Z, `2bma:m8`) is a setup translation the IOC does not drive; the mirror is held constant. Neither carries an energy curve.
- DMM lateral stripe not yet modelled: substrate has two multilayer periods (13.8 / 24 angstrom) on stripes 4 mm apart; upstream/downstream X motors (`2bma:m25` / `2bma:m28`) may select per energy band. Operator-facing selection vs fixed setup is open (`ENERGY-6`).
- Seeded curves are PROVISIONAL: x-points are real configured energies, positions are placeholders pending the real `store_0` table (see [Open questions](questions.md#energy-and-the-optics)). Runtime `eval_lookup_table` is wired; out-of-range refuses (`extrapolation_kind=Error`); refuse vs clamp vs menu-only is open (`ENERGY-4`).
- The `energy_offset` Calibration on `Monochromator` (from the `energy_characterization` Procedure, channel-cut rocking curve, item_022) is kept independent of these curves. Whether the IOC folds the measured offset into `store_0` or applies it separately is open (`ENERGY-8`).

### Filter foil selection

Discrete "pick one of N" move. `Filter_FoilSelector` PseudoAxis under `Filter`, carrying a `LookupTable` rule with `interpolation_kind=Nearest` backed by an `index_position_table` Calibration. `extrapolation_kind=Error` (cannot select an absent foil); `invertible=False` with `readback_aggregator_kind=Identity`. Foil changer has two paddles: downstream (`2bma:m18`) operational, upstream (`2bma:m17`) bound in software but not in service. Runtime proven end-to-end in `apps/api/tests/integration/test_pseudoaxis_roundtrip.py`; model: `test_2bm_filter_foil_setup.py`.

Downstream-paddle slot positions (REAL, staff-published):

| Slot index | Material | Position |
| --- | --- | --- |
| 0 | `600 um Al` | 0 |
| 26 | `150 um Al` | 26 |
| 53 | `300 um C` | 53 |
| 80 | `50 um C` | 80 |
| 106 | `None` | 106 |

The position unit is reported as the motor record EGU ("consistent with mm" but not definitively confirmed, `FOIL-1`). Foil ATTENUATION (`Attenuable`) and the energy-dependent mirror coating stripe (`2bma:m3`) are deliberately out of scope here (the stripe is modelled with the [beam-mode work](procedures.md#beam-modes)).
