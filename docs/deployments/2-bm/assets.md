# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself is a root Asset with `tier = Unit` (bound to its Site Facility via `facility_code`) and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

The MCTOptics detector is modelled as an Assembly + Fixture pair (not an Asset row in its own right). The constituent Assets appear in the inventory below; the composition and wiring story lives on the dedicated [MCTOptics deployment](equipment/mctoptics.md) page.

## Inventory

| Asset | Tier | Family | Parent |
| --- | --- | --- | --- |
| `Shutter_2BM` | `Device` | `Shutter` | `2-BM` |
| `Aerotech_Ensemble_drive` | `Device` | `MotionController` | `2-BM` |
| `Aerotech_ABRS_rotary` | `Device` | `RotaryStage` | `2-BM` (driven by `Aerotech_Ensemble_drive`) |
| `OMS_VME58_2bmb_drive` | `Device` | `MotionController` | `2-BM` |
| `OMS_VME58_2bma_drive` | `Device` | `MotionController` | `2-BM` (front-end / beam-conditioning band; no modelled driven stages at v1) |
| `Sample_top_X` | `Device` | `LinearStage` | `2-BM` (driven by `OMS_VME58_2bmb_drive`) |
| `Sample_top_Z` | `Device` | `LinearStage` | `2-BM` (driven by `OMS_VME58_2bmb_drive`) |
| `Sample_top_Roll` | `Device` | `PseudoAxis` | `2-BM` |
| `Sample_top_Pitch` | `Device` | `PseudoAxis` | `2-BM` |
| `Aerotech_Hexapod_drive` | `Device` | `MotionController` | `2-BM` |
| `Hexapod_2BM` | `Device` | `Hexapod` | `2-BM` (driven by `Aerotech_Hexapod_drive`) |
| `Aerotech_2bmbAERO_drive` | `Device` | `MotionController` | `2-BM` |
| `Optique_Peter_focus_Z` | `Device` | `LinearStage` | `2-BM` (bound into MCTOptics Fixture; driven by `Aerotech_2bmbAERO_drive`) |
| `MCTOptics_lens_turret` | `Device` | `RotaryStage` (pending) | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_0` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_1` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_2` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `Oryx_5MP_camera` | `Device` | `Camera` | `2-BM` (bound into MCTOptics Fixture) |
| `Scintillator_LuAG` | `Device` | `Scintillator` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_lens_select` | `Device` | `PseudoAxis` | `2-BM` (bound into MCTOptics Fixture; partition rule decomposes lens index to turret rotation) |

## Family affordances

Each Family declares a closed-enum set of operational primitives ([Affordances](../../reference/affordances.md)). The set is required at Family definition and replaces wholesale on `version_family`.

| Family | Affordances |
| --- | --- |
| `Shutter` | `Shutterable` |
| `MotionController` | (empty at v1; controllers expose configuration + firmware identity through `settings` rather than command-tier affordances) |
| `TimingController` | `Pulsing` (carried via the `Controller` Role). Unlike `MotionController`, a timing box is itself the actor: the pulse-generation affordance is its own, not a driven device's. softGlueZynq generates configurable trigger pulse trains for downstream timing; per-box identity + firmware/bitstream config live in `settings`. |
| `RotaryStage` | `Rotatable`, `Homeable`, `Limitable`, `Following`, `Marking` |
| `LinearStage` | `Translatable`, `Homeable`, `Limitable`, `Following` |
| `Hexapod` | `Posable`, `Homeable`, `Limitable` |
| `Scintillator` | `Consumable` |
| `Camera` | `Imageable`, `Binnable`, `Triggerable`, `Streamable`, `Recording` |
| `Imager` | (empty; this Family exists as the `presents_as_family_id` target for detector Assemblies, including MCTOptics; was `ImagingDetector` before the role-aggregate-design rename) |
| `Objective` | (pending — empty at initial registration) |
| `PseudoAxis` | (empty; partition rules live on `Asset.partition_rule`, not as affordances) |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface). `Imager` and `PseudoAxis` are presenter / facet Families: they carry no affordances, but Methods bind against them via `needed_family_ids` (for `Imager` the Assembly's `presents_as_family_id` is the satisfaction handle; for `PseudoAxis` the Family membership is the gate that lets an Asset carry a `partition_rule`).

`MotionController` is the first separately-modelled drive-electronics Family. v1 ships empty affordances by design: the meaningful state on a controller is configuration (firmware version, IP address, axis count, protocol) and identity (serial number), captured in `settings` and `alternate_identifiers`. Command-tier affordances (firmware-update, reboot, sync-output toggling) are deferred until an operator-side Procedure demands them, at which point they grow on the existing add-only affordance amendment path.

## Vendor catalog (Models)

Per-Asset Model bindings carry the vendor identity that PIDINST Property 6 (Manufacturer) and Property 7 (Model) need. Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families. The four MCTOptics-housing Models (lens turret motor, Mitutoyo MPLAPO objective kit, FLIR Oryx camera, Crytur LuAG scintillator) live on the [MCTOptics deployment](equipment/mctoptics.md#vendor-catalog-models) page; the table below tracks Models bound to non-MCTOptics 2-BM Assets.

| Model | Manufacturer | Part number | Declared Families | Bound at 2-BM |
| --- | --- | --- | --- | --- |
| `aerotech_hexgen_hex300_230hl` | Aerotech | `HEX300-230HL-E1-PL4-TAS` | `Hexapod` | `Hexapod_2BM` |
| `aerotech_abs250mp_m_as` | Aerotech | `ABS250MP-M-AS` | `RotaryStage` | `Aerotech_ABRS_rotary` |
| `aerotech_ensemble_hle10_40_a_mxh` | Aerotech | `HLE10-40-A-MXH` | `MotionController` | `Aerotech_Ensemble_drive` |
| `aerotech_hexapod_drive_unknown_pn` | Aerotech | `unknown-pending-confirmation` | `MotionController` | `Aerotech_Hexapod_drive` |
| `aerotech_2bmbaero_drive_unknown_pn` | Aerotech | `unknown-pending-confirmation` | `MotionController` | `Aerotech_2bmbAERO_drive` |
| `aerotech_pro225sl_1000` | Aerotech | `PRO225SL-1000` | `LinearStage` | `Optique_Peter_focus_Z` |
| `oms_vme58` | Oregon Micro Systems | `VME58` | `MotionController` | `OMS_VME58_2bmb_drive`, `OMS_VME58_2bma_drive` |
| `kohzu_cyat_070` | Kohzu | `CYAT-070` | `LinearStage` | `Sample_top_X`, `Sample_top_Z` |

A Model id is deterministic: `model_stream_id` derives it as `uuid5` over the canonical `(lowercased manufacturer name, case-preserved part number)` vendor key, so the same vendor product converges on one id across facilities and a second `define_model` on the same real key returns `409`. `oms_vme58` is the convergence case in the table: both `OMS_VME58_2bmb_drive` and `OMS_VME58_2bma_drive` bind the one `oms_vme58` Model row (one product, two physical boards). The two `unknown-pending-confirmation` rows are the deliberate exception: that placeholder part number is NOT a real vendor key, so `model_stream_id` falls back to a random id, keeping `aerotech_hexapod_drive_unknown_pn` and `aerotech_2bmbaero_drive_unknown_pn` distinct rather than collapsing both unconfirmed drives onto one identity. When their real part numbers are confirmed, each re-registers under its derived id.

Part-number suffix conventions vary by vendor: Aerotech's `HEX300-230HL-E1-PL4-TAS` encodes operationally significant variants (`-E1` incremental encoder, `-PL4` ultra-high-accuracy preload, `-TAS` thermal-actively-stabilized); `ABS250MP-M-AS` follows the same pattern (`-M` mid-precision class, `-AS` air-bearing series); `PRO225SL-1000` carries the `-1000` mm travel suffix natively. v1 stores the full type designation as a single `part_number` string; the catalog convention upgrades to suffix decomposition at the second case where a suffix axis crosses Model boundaries (rule-of-three), or at the first APS imaging stage+drive registration, whichever fires first.

The Aerotech Ensemble HLE10-40-A-MXH (companion drive for `aerotech_abs250mp_m_as`) IS now modelled as a separate Asset (`Aerotech_Ensemble_drive`) with `tier = Device` under 2-BM, with `Aerotech_ABRS_rotary.controller_id` carrying the back-reference. This was the FIRST `MotionController` Asset shipped, anchoring the controller-as-Asset slice on the unambiguously-identified rotary drive per `project_controller_as_asset_stage1_design`. A SECOND `MotionController` Asset (`Aerotech_Hexapod_drive`) now models the drive for `Hexapod_2BM`, with `Hexapod_2BM.controller_id` carrying the back-reference; the 2-BM source page does not name the drive's specific product line (the EPICS interface is "native Aerotech Ensemble" but the box is not identified, nor is rack-separate vs sealed-in integration confirmed), so the Model row uses `unknown-pending-confirmation` for the part number and the per-Asset Settings block carries placeholders that operators replace via `update_asset_settings` once the physical hardware is verified. A THIRD `MotionController` Asset (`Aerotech_2bmbAERO_drive`) models the drive electronics that the `2bmbAERO` EPICS IOC manages on behalf of `Optique_Peter_focus_Z`; the Asset name uses the IOC handle (the most stable operator-facing identifier; the drive's product line is almost certainly Aerotech Ensemble-family but unconfirmed on the source page), and the same `unknown-pending-confirmation` pattern carries the per-unit identity placeholders. A FOURTH `MotionController` Asset (`OMS_VME58_2bmb_drive`) now models the Oregon Micro Systems VME58 motor controller card in the 2-BM b-station IOC crate (`ioc2bmb`), which drives the `2bmb:m1`-`2bmb:m91` motor band including `Sample_top_X` (`2bmb:m18`) and `Sample_top_Z` (`2bmb:m17`); both stage Assets now carry `controller_id` back-references to `OMS_VME58_2bmb_drive`. The remaining 89 driven motors on the 2bmb crate live in [Pending](#pending) until each earns its own Asset registration; the controller Asset is the addressability handle that makes a future "VME-bus glitch took out m1-m91" Caution scope honestly to the bus rather than dispersing across 91 motor Assets. A FIFTH `MotionController` Asset (`OMS_VME58_2bma_drive`) models the sibling OMS VME58 board in the 2-BM a-station IOC crate (`ioc2bma`), which drives the front-end / beam-conditioning motor band (`Mirror`, `DMM`, slits, monitor); none of those driven motors are modelled at v1, so the controller Asset ships in isolation with no current `controller_id` back-references pointing at it. The controller registration still ships because absence-of-tracking on hardware that demonstrably exists (and gets rebooted, replaced, firmware-versioned by 2-BM operators) is exactly the self-justifying-defer that `feedback_intentional_modeling_not_mirroring` exists to forbid. Both OMS-VME58 instances bind to the same `oms_vme58` Model row per the one-Model-per-product-line convention; per-instance identity (serial number, firmware version) lives in the per-Asset Settings block. PARTIAL SHIP today is 5 of 7 controller hardware classes; the remaining 2 (Nanotec ST4118 stepper inside Optique Peter, and the Schunk LPTM 30 inside the camera selector) remain deferred per `project_controller_as_asset_research`; each earns its own Stage-1 call when its own trigger fires.

`Sample_top_Pitch` and `Sample_top_Roll` are PseudoAxis Assets (virtual DoFs over the 2bmHXP hexapod-kinematics solver) and do not bind to a vendor Model. The Model-binding flow (PIDINST) targets physical commissioned hardware; the underlying constituents (the Hexapod_2BM physical axes) carry the Model binding. The remaining four hexapod DoFs (X, Y, Z, Yaw) and the constituent-port wiring from Hexapod_2BM to the virtual DoFs are deferred until the trigger named in `project_pitch_roll_retag`. The Kohzu SA16A-RM goniometer (`Sample_pitch_lam` in the 2-BM source page, possibly the same physical thing as `Sample_top_Pitch` or a third stage) gets its own Model row when the operator-naming question lands.

## Family settings schemas

NEW schemas registered for the 2-BM deployment. The `RotaryStage`, `LinearStage`, and `Scintillator` schemas are declared at the [APS Site assets](../aps/assets.md) level once a second beamline uses them; today they remain implicit in the per-Asset [Settings](#settings) values below. The `Camera` schema is made explicit below: the 2-BM detector classes (the active FLIR Oryx and the decommissioned PCO Dimax) differ along settings axes (`max_framerate_hz`, `sensor_kind`, `readout_mode`), not Family axes, so the high-framerate variant stays a `Camera` rather than a separate Family. `Imager` and `PseudoAxis` carry no settings schema (they are presenter / facet Families).

### `Objective`

Intrinsic per-lens properties. Motion is via the lens turret motor wired into the Assembly; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

### `Hexapod`

Operational envelope of a 6-DoF parallel-kinematic positioner. The schema captures the vendor-published envelope (per-DoF travel, speed, resolution, accuracy, load capacity) without exploding the legs as sub-Assets (vendor-sealed unit; inverse kinematics runs in controller firmware, not in CORA). DoF-level addressability (Shape 2: per-DoF PseudoAxis facets referencing this Hexapod as constituent) is a separate design question gated on the Plan.wiring terminal-typing contract.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `travel_x` | number > 0 | mm | single-axis from home; translation envelope |
| `travel_y` | number > 0 | mm | |
| `travel_z` | number > 0 | mm | |
| `travel_a` | number > 0 | deg | rotation envelope around X (tilt) |
| `travel_b` | number > 0 | deg | rotation envelope around Y (tilt) |
| `travel_c` | number > 0 | deg | rotation envelope around Z (yaw) |
| `max_speed_translation` | number > 0 | mm/s | typically dominated by the slowest translation axis |
| `max_speed_rotation` | number > 0 | deg/s | typically dominated by the slowest rotation axis |
| `resolution_translation` | number > 0 | nm | encoder resolution for X/Y/Z (vendor reports a common value) |
| `resolution_rotation` | number > 0 | urad | encoder resolution for A/B/C |
| `accuracy_translation` | number > 0 | um | bidirectional positioning accuracy, dominant translation DoF |
| `accuracy_rotation` | number > 0 | urad | bidirectional positioning accuracy, dominant rotation DoF |
| `load_capacity_vertical` | number > 0 | kg | rated load with platform horizontal |
| `load_capacity_horizontal` | number > 0 | kg | rated load with platform vertical |
| `stage_mass` | number > 0 | kg | bare platform mass (excludes mounted payload) |

The pairs `max_speed_translation` / `max_speed_rotation`, `resolution_*`, and `accuracy_*` collapse the six per-DoF measurements down to two values per metric in v1; the vendor datasheet reports per-DoF variation small enough that the dominant-DoF figure is a faithful envelope. When a Method binds against per-DoF setpoints (currently no such Method exists), Shape 2 (PseudoAxis facets) is the surface that grows; the schema above stays as the envelope contract.

### `MotionController`

Identity + configuration + connectivity of a separately-modelled drive-electronics box. Field selection follows the intentional-design posture: every field exists because reproducibility, federation, or operational reasoning needs it, not because the existing 2-BM ad-hoc representation already carries it. Per-axis Procedures continue to target the driven stage Asset; controller-tier Procedures (firmware update, controller swap, sync-output retune) target the controller Asset and read these fields. See `project_controller_as_asset_stage1_design`.

| Setting | Type | Required | Notes |
| --- | --- | --- | --- |
| `serial_number` | string, 1-128 chars | yes | Per-unit identity; operator-facing canonical key. Distinct from `Asset.alternate_identifiers` (PIDINST cross-reference set), which can also carry serial numbers among other schemes; `serial_number` here is the single operator-blessed canonical value. |
| `firmware_version` | string, 1-64 chars | yes | Reproducibility provenance. Required intentionally per the intentional-modeling posture: absence-of-operator-demand is the failure mode that posture exists to forbid. A controller without a recorded firmware version cannot honestly answer the "did the firmware change between Run X and Run Y" question. Free-text in v1; semver validation defers to the second-vendor proof. |
| `ip_address` | string, 7-45 chars | no | Network identity. Optional because not every controller class is network-attached (RS-232 / RS-485 / VME-bus boxes have no IP). Format validation is shape-only at this layer (route / Pydantic may impose IPv4 / IPv6 regex when deployments warrant it). |
| `axis_count` | integer, 1-91 | yes | Operational metadata. Bounds bracket smallest single-axis (1) to largest OMS-VME58 deployment at 2-BM (91 Kohzu motors). Drives the eventual multi-motor Caution-fans-out semantics when that trigger fires. |
| `protocol` | closed enum: `EPICS \| Aerotech_Native \| OMS_VME \| Serial_RS232 \| Serial_RS485 \| Modbus_TCP \| Other` | yes | Communication protocol. Six known plus `Other` escape valve; future additions follow the add-only-enum convention. |

`manufacturer` is NOT on this schema: vendor identity lives on the bound Model row per the Capability-declares-settings-schema pattern (`Aerotech` for `Aerotech_Ensemble_drive` comes from `aerotech_ensemble_hle10_40_a_mxh`).

### `TimingController`

Identity + configuration + connectivity of a separately-modelled timing-signal box, the second `<Domain>Controller` Family after `MotionController`. Same intentional-design posture: every field exists because reproducibility, federation, or operational reasoning needs it. The driven device (the camera) carries the `Triggerable` affordance; the timing box carries `Pulsing` (via the `Controller` Role) because it is the active generator of the trigger pulse train. Draft schema pending 2-BM operator confirmation on the softGlueZynq physical box.

| Setting | Type | Required | Notes |
| --- | --- | --- | --- |
| `serial_number` | string, 1-128 chars | yes | Per-unit identity; operator-facing canonical key. Same role as on `MotionController`. |
| `firmware_version` | string, 1-64 chars | yes | Reproducibility provenance. For an FPGA box this is the gateware / bitstream version: the trigger logic itself can change between Runs, so a Run cannot honestly answer "did the timing change between Run X and Run Y" without it. Free-text in v1. |
| `ip_address` | string, 7-45 chars | no | Network identity. The softGlueZynq is network-attached and EPICS-fronted; optional because future timing sources may not be. |
| `output_channel_count` | integer, 1-64 | yes | Number of independent trigger / gate output lines the box drives. Analogue of `MotionController.axis_count`; bounds the eventual "one output line failed" Caution scope. |
| `protocol` | closed enum: `EPICS \| Aerotech_Native \| OMS_VME \| Serial_RS232 \| Serial_RS485 \| Modbus_TCP \| Other` | yes | Communication protocol, shared closed enum with `MotionController`. softGlueZynq is `EPICS`. |

The detailed trigger routing (the softGlue logic-block wiring, e.g. the `PSO -> MUX2-1 -> GateDly1 -> camera Line2` path on the 2-BM box) is per-Run / per-Method configuration, not Asset settings: it changes with the scan, while the schema above records the durable box identity.

### `Camera`

Intrinsic detector properties, made explicit at 2-BM because a second detector class (the high-framerate PCO Dimax) shares the Family with the FLIR Oryx and differs only along settings axes. The first four fields formalize what the per-Asset Settings already carry; the last three are the high-framerate extension that lets one `Camera` Family span both detectors (the `Mirror`-precedent rule: variant-as-settings, not variant-as-subtype).

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `sensor_width` | integer > 0 | pixel | Active sensor columns. |
| `sensor_height` | integer > 0 | pixel | Active sensor rows. |
| `pixel_size` | number > 0 | um | Physical sensor pixel pitch (before optical magnification). |
| `bit_depth` | integer > 0 | bit | ADC bit depth per pixel. |
| `max_framerate_hz` | number > 0 | Hz | Full-frame maximum frame rate; the axis that distinguishes a high-speed PCO Dimax from a general-purpose Oryx without a separate Family. |
| `sensor_kind` | closed enum: `CMOS \| sCMOS \| CCD \| EMCCD` | | Sensor architecture. Four known values; add-only enum. |
| `readout_mode` | closed enum: `RollingShutter \| GlobalShutter` | | Shutter / readout architecture; governs motion-blur behaviour under triggered fly-scans. |

## Settings

### `Aerotech_Ensemble_drive`

Bound to Model `aerotech_ensemble_hle10_40_a_mxh`. The Aerotech Ensemble HLE10-40-A-MXH digital drive that runs `Aerotech_ABRS_rotary`. First `MotionController` Asset shipped at 2-BM; the back-reference lives on `Aerotech_ABRS_rotary.controller_id`.

Placeholder values below are intentional. The controller-as-Asset design ships the substrate for reproducibility provenance now; the actual operator-confirmed firmware version and serial number land via `update_asset_settings` once 2-BM staff verifies them on the physical hardware. Leaving the fields out entirely would silently re-create the 2-BM ad-hoc absence-of-tracking that the slice exists to address.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` |
| `firmware_version` | `unknown-pending-confirmation` |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `Aerotech_2bmbAERO_drive`

Bound to Model `aerotech_2bmbaero_drive_unknown_pn`. The Aerotech drive electronics that the `2bmbAERO` EPICS IOC manages on behalf of `Optique_Peter_focus_Z`. Third `MotionController` Asset shipped at 2-BM; the back-reference lives on `Optique_Peter_focus_Z.controller_id`.

Operators address the focus motor via `2bmbAERO:m1` (IOC name + motor channel); the IOC is software (an EPICS process) while the Asset modelled here is the hardware drive box behind it (per OPC UA DI / AAS DigitalNameplate alignment, CORA models field-replaceable, firmware-versioned drive electronics rather than the software process talking to them). The drive's specific product line is not named on the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the Asset name carries the IOC handle (the most stable operator-facing identifier) and settings placeholders cover identity details that operators verify on the physical hardware.

`axis_count=1` reflects the 1:1 binding to the single focus_Z stage; `protocol=Aerotech_Native` matches the rotary anchor's posture for the same vendor family.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` |
| `firmware_version` | `unknown-pending-confirmation` |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `OMS_VME58_2bmb_drive`

Bound to Model `oms_vme58`. The Oregon Micro Systems VME58 motor controller card in the 2-BM b-station IOC crate (`ioc2bmb`), which drives the `2bmb:m1`-`2bmb:m91` motor band per the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Fourth `MotionController` Asset shipped at 2-BM; the back-references live on `Sample_top_X.controller_id` and `Sample_top_Z.controller_id` (`2bmb:m18` and `2bmb:m17` respectively); the remaining 89 driven motors on this crate are tracked in [Pending](#pending).

Operators address motors on this crate via the EPICS channel naming `2bmb:m<N>` (IOC name + motor channel); the IOC is software (an EPICS process running in the `ioc2bmb` crate) while the Asset modelled here is the OMS VME58 hardware board itself. Same OPC UA DI / AAS DigitalNameplate alignment as the Aerotech drives: CORA models the field-replaceable, firmware-versioned drive electronics rather than the software process that addresses them. The Aerotech Ensemble axes (`2bmb:m100`-`2bmb:m102`) on the same IOC are addressed through a separate Aerotech HLE10-40-A-MXH and ship as their own `Aerotech_Ensemble_drive` Asset; one IOC, two physical controllers, two MotionController Assets.

`axis_count=91` is the OMS-VME58 card's slot-cardinality at 2-BM and the upper bound of the settings_schema range; even though only two of the 91 channels are currently bound to modelled stages, the controller's intrinsic capacity is the value the field records. `protocol=OMS_VME` matches the closed-enum value in the `MotionController` settings schema. The drive is VME-bus addressed (not IP-attached), so `ip_address` is omitted.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` |
| `firmware_version` | `unknown-pending-confirmation` |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

`ip_address` is omitted (VME-bus addressed, no IP); the field is optional on the schema. `serial_number` and `firmware_version` carry the same `unknown-pending-confirmation` placeholders as the Aerotech drives; operator confirmation lands via `update_asset_settings` once the 2-BM staff verifies the physical card.

### `OMS_VME58_2bma_drive`

Bound to Model `oms_vme58` (same product line as `OMS_VME58_2bmb_drive`; one Model row, two Asset instances). The Oregon Micro Systems VME58 motor controller card in the 2-BM a-station IOC crate (`ioc2bma`), which drives the front-end / beam-conditioning motor band (`Mirror`, `DMM`, slits, monitor, etc. per the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html)). Fifth `MotionController` Asset shipped at 2-BM; NO `controller_id` back-references point at this controller from any v1-modelled stage because the front-end driven motors are all in [Pending](#pending).

The controller still ships as an Asset because its existence in reality is the load-bearing fact (operators reboot it, replace it, version its firmware) regardless of whether any driven motor is yet modelled in CORA. Waiting for a driven-stage trigger before registering the controller would invert the dependency the controller-as-Asset substrate is designed around: stages depend on controllers (`controller_id` is a forward reference from the stage), not the other way round. When the front-end stages get modelled in a future slice, they will reference this controller's id verbatim without retroactive controller registration ceremony.

`axis_count=91` matches the OMS-VME58 card's slot-cardinality (identical to `OMS_VME58_2bmb_drive`; per-card hardware capacity, not per-deployment binding count). `protocol=OMS_VME` matches the closed-enum value. `ip_address` is omitted (VME-bus addressed).

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` |
| `firmware_version` | `unknown-pending-confirmation` |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

`ip_address` is omitted (VME-bus addressed, no IP); the field is optional on the schema. Both placeholders land via `update_asset_settings` once 2-BM staff verifies the physical card; the 2bma + 2bmb cards carry distinct serial numbers and may run distinct firmware versions despite sharing a Model row.

### `Aerotech_Hexapod_drive`

Bound to Model `aerotech_hexapod_drive_unknown_pn`. The Aerotech drive electronics that run `Hexapod_2BM`. Second `MotionController` Asset shipped at 2-BM; the back-reference lives on `Hexapod_2BM.controller_id`.

The Asset name records what the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) actually says (Aerotech vendor, drives the hexapod stage, EPICS interface is "native Aerotech Ensemble") without overclaiming the drive's specific product line. The page does not name the controller box, nor confirm whether the drive sits in a separate rack or is sealed into the HexGen stage. The Asset still ships now per the intentional-modeling rule (waiting for source-page disambiguation would let the ad-hoc absence-of-tracking self-justify indefinitely); operator confirmation lands later via `update_asset_settings` and a `version_model` of the bound Model row.

Placeholder values below follow the same intentional-design posture as `Aerotech_Ensemble_drive`. The `axis_count=6` is the operationally meaningful integer for any hexapod drive: a hexapod has 6 DoF, regardless of which Aerotech product line the controller belongs to.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` |
| `firmware_version` | `unknown-pending-confirmation` |
| `axis_count` | `6` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `Aerotech_ABRS_rotary`

Bound to Model `aerotech_abs250mp_m_as`. Aerotech ABS250MP-M-AS air-bearing direct-drive rotary stage (250 mm aperture, mid-precision class), driven by `Aerotech_Ensemble_drive` (referenced via `Aerotech_ABRS_rotary.controller_id`).

| Setting | Value |
| --- | --- |
| `min_position` | `−360 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `720 deg/s` |
| `encoder_resolution` | `0.0001 deg` |
| `homing_offset` | `0 deg` |

### `Sample_top_X`

Bound to Model `kohzu_cyat_070`, driven by `OMS_VME58_2bmb_drive` (referenced via `Sample_top_X.controller_id`; addressed on EPICS channel `2bmb:m18`). Kohzu CYAT-070 crossed-roller alignment stage (80 x 80 mm table, ball-screw lead 1.0 mm). Sister Asset `Sample_top_Z` binds the same Model and the same controller. The full vendor-published envelope (±0.5 um repeatability, lost motion ≤ 2 um, backlash ≤ 1 um, straightness ≤ 3 um per 30 mm, load 98 N, weight 1.7 kg) lives on the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the v1 Settings below capture only the operationally bound min/max/speed/resolution fields.

| Setting | Value |
| --- | --- |
| `min_position` | `−10 mm` |
| `max_position` | `10 mm` |
| `max_speed` | `1 mm/s` |
| `encoder_resolution` | `0.0005 mm` |

### `Hexapod_2BM`

Bound to Model `aerotech_hexgen_hex300_230hl`, driven by `Aerotech_Hexapod_drive` (referenced via `Hexapod_2BM.controller_id`). Values from the Aerotech HEX300-230HL product datasheet (Hex300-Data-Sheet-D20250203). Per-DoF figures collapse to the dominant axis where the vendor's range across DoFs fits within a faithful envelope (e.g., translation accuracy reported as the laxest of X / Y / Z).

| Setting | Value |
| --- | --- |
| `travel_x` | `55 mm` |
| `travel_y` | `60 mm` |
| `travel_z` | `25 mm` |
| `travel_a` | `15 deg` |
| `travel_b` | `15 deg` |
| `travel_c` | `30 deg` |
| `max_speed_translation` | `25 mm/s` |
| `max_speed_rotation` | `15 deg/s` |
| `resolution_translation` | `20 nm` |
| `resolution_rotation` | `0.2 urad` |
| `accuracy_translation` | `1 um` |
| `accuracy_rotation` | `10 urad` |
| `load_capacity_vertical` | `45 kg` |
| `load_capacity_horizontal` | `21 kg` |
| `stage_mass` | `12 kg` |

### `Scintillator_LuAG`

| Setting | Value |
| --- | --- |
| `thickness` | `100 um` |
| `decay_time` | `0.07 us` |

### `Oryx_5MP_camera`

| Setting | Value |
| --- | --- |
| `sensor_width` | `2448 pixel` |
| `sensor_height` | `2048 pixel` |
| `pixel_size` | `3.45 um` |
| `bit_depth` | `12 bit` |

### `MCTOptics_objective_0` (10x)

| Setting | Value |
| --- | --- |
| `magnification` | `10.0` |
| `numerical_aperture` | `0.28` |
| `focal_length` | `20 mm` |
| `working_distance` | `33.5 mm` |

### `MCTOptics_objective_1` (2x)

| Setting | Value |
| --- | --- |
| `magnification` | `2.0` |
| `numerical_aperture` | `0.055` |
| `focal_length` | `100 mm` |
| `working_distance` | `34 mm` |

### `MCTOptics_objective_2` (1.1x)

| Setting | Value |
| --- | --- |
| `magnification` | `1.1` |
| `numerical_aperture` | `0.03` |
| `focal_length` | `200 mm` |
| `working_distance` | `50 mm` |

### `MCTOptics_lens_turret`

`RotaryStage` Family assumed (pending 2-BM operator confirmation; if the turret is a translating slide, the Family flips to `LinearStage` and the signal types switch from `rotation_deg` to `linear_mm`).

| Setting | Value |
| --- | --- |
| `min_position` | `0 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `30 deg/s` |
| `encoder_resolution` | `0.01 deg` |

## Engineering drawings

Each Asset may carry one canonical engineering reference as a `(system, number, revision)` triple per the [Drawing VO](../../architecture/modules/equipment/index.md). The carrier holds the build-to document for the physical specimen; the [Mount drawing](equipment/mctoptics.md#engineering-drawings) on the slot is a separate document (where the slot lives in the beamline). v1 is single-valued; the Drawing-frozenset promotion and `Model.drawing` / `Fixture.drawing` extensions defer to the rule-of-three trigger.

Assets not listed below have no canonical document cited on the 2-BM source page yet (Aerotech `ABS250MP` datasheet for `Aerotech_ABRS_rotary`, Kohzu `CYAT-070` datasheet for the four `Sample_top_*` stages, an APS shutter drawing for `Shutter_2BM`, and a FLIR Oryx datasheet for `Oryx_5MP_camera`). These populate when the operator confirms the canonical reference.

### `Hexapod_2BM`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `Hex300-Data-Sheet` |
| `revision` | `D20250203` |

Aerotech HEX300-230HL hexapod product datasheet (Hex300-Data-Sheet-D20250203.pdf). The MCTOptics deployment cites this as the structured reference for the 6-DoF positioner that anchors the sample stack.

### `Optique_Peter_focus_Z`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

Optique Peter MICRX080 microscope manual (MAN-11863-0521-0465-A, 21 May 2021, 53 pages). The shared vendor manual covers every Optique Peter housing constituent (focus stage, lens turret, lens kit, scintillator). Same reference attaches to each MCTOptics-bound Asset below.

### `MCTOptics_lens_turret`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `MCTOptics_objective_0`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

v1 attaches the housing manual as the canonical reference; the Mitutoyo MPLAPO LWD per-magnification datasheet is the eventual upgrade once part numbers are verified (see the [vendor catalog note](equipment/mctoptics.md#vendor-catalog-models) on the Plan-Apo-NIR three-part-number split).

### `MCTOptics_objective_1`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `MCTOptics_objective_2`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `Scintillator_LuAG`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

## Pending

| Asset | Family |
| --- | --- |
| `Y3-30_mirror` | `Mirror` |
| `softGlueZynq_FPGA` | `TimingController` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |

`TimingController` here is the catalog-aligned Family, replacing the earlier `TriggerFPGA` placeholder. Substrate ("FPGA") is not a Family axis: the softGlueZynq is a `TimingController` whose identity + gateware version live in `settings`, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

## Decommissioned (provenance only)

Detectors 2-BM ran in the past. They are neither active Assets nor awaiting registration; [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) records them under `decommissioned` for provenance. When modelled they are `Camera` Assets in a terminal lifecycle state: the `Camera` Family spans them and the active FLIR Oryx, because performance class ("high-speed") is a settings axis, not a separate Family, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

| Asset | Family | Note |
| --- | --- | --- |
| `PCO_Dimax_HS` | `Camera` | High-speed CMOS camera; superseded by the FLIR Oryx detector chain. |
| `Adimec_Quartz_Q-12A180` | `Camera` | Earlier 2-BM CoaXPress camera. |
