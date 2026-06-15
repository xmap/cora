# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself is a root Asset with `tier = Unit` (bound to its Site Facility via `facility_code`) and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

The Microscope detector is modelled as an Assembly + Fixture pair over a reusable Optics sub-assembly, with the constituents contained in one `Housing` Asset. The constituent Assets appear in the inventory below; the composition, containment, and wiring story lives on the dedicated [Microscope deployment](equipment/microscope.md) page.

Devices are located in one of the two hutch Enclosures, the optics hutch `2-BM-A` or the experiment hutch `2-BM-B`, declared per Device via `located_in_enclosure_id`. The Located-in column below records where each Device sits; the two hutches and the pre-flight gate they drive are on the [Enclosures](enclosures.md) page. The hutches are Enclosures, not Assets, so they do not appear as inventory rows.

## Inventory

| Asset | Tier | Family | Parent | Located in |
| --- | --- | --- | --- | --- |
| `StationShutter` | `Device` | `Shutter` | `2-BM` | `2-BM-B` |
| `RotaryDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `Rotary` | `Device` | `RotaryStage` | `2-BM` (driven by `RotaryDrive`) | `2-BM-B` |
| `SampleStageDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `FrontEndDrive` | `Device` | `MotionController` | `2-BM` (front-end / beam-conditioning band; no modelled driven stages at v1) | `2-BM-A` |
| `SampleTop_X` | `Device` | `LinearStage` | `2-BM` (driven by `SampleStageDrive`) | `2-BM-B` |
| `SampleTop_Z` | `Device` | `LinearStage` | `2-BM` (driven by `SampleStageDrive`) | `2-BM-B` |
| `HexapodDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `Hexapod` | `Device` | `Hexapod` | `2-BM` (driven by `HexapodDrive`) | `2-BM-B` |
| `Hexapod_X` | `Device` | `PseudoAxis` | `Hexapod` (DoF; translation along X) | `2-BM-B` |
| `Hexapod_Y` | `Device` | `PseudoAxis` | `Hexapod` (DoF; translation along Y) | `2-BM-B` |
| `Hexapod_Z` | `Device` | `PseudoAxis` | `Hexapod` (DoF; translation along Z) | `2-BM-B` |
| `Hexapod_Roll` | `Device` | `PseudoAxis` | `Hexapod` (DoF; rotation A about X) | `2-BM-B` |
| `Hexapod_Pitch` | `Device` | `PseudoAxis` | `Hexapod` (DoF; rotation B about Y) | `2-BM-B` |
| `Hexapod_Yaw` | `Device` | `PseudoAxis` | `Hexapod` (DoF; rotation C about Z) | `2-BM-B` |
| `FocusDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `Housing` | `Component` | `Housing` | `2-BM` (installed into a Mount; parents the Microscope constituents) | `2-BM-B` |
| `Turret` | `Device` | `RotaryStage` (pending) | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_10x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_2x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_1.1x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_Selector` | `Device` | `PseudoAxis` | `Housing` (bound into Microscope Fixture; partition rule decomposes lens index to turret rotation) | `2-BM-B` |
| `Focus` | `Device` | `LinearStage` | `Housing` (bound into Microscope Fixture; driven by `FocusDrive`) | `2-BM-B` |
| `Camera` | `Device` | `Camera` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Scintillator` | `Device` | `Scintillator` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |

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
| `Housing` | (empty; the containment chassis Family carried by the `Housing` Asset that parents the Microscope constituents; no command surface) |
| `Objective` | (pending: empty at initial registration) |
| `PseudoAxis` | (empty; partition rules live on `Asset.partition_rule`, not as affordances) |
| `Table` | `Translatable`, `Rotatable` (provisional superset for the hutch support tables: the sample table is translation-only, the detector table adds tilt axes; the per-table axis set is a settings difference, not a Family split, see [Family settings schemas](#table)). Carries-other-equipment is `parent_id` placement, not an affordance; there is no Supporting affordance. Assets are [Pending](#pending) until seeded. |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface). `PseudoAxis` is a facet Family: it carries no affordances, but Methods bind against it via `needed_family_ids`, and the Family membership is the gate that lets an Asset carry a `partition_rule`. Detector Assemblies, including the Microscope, advertise the `Detector` Role through the Assembly's `presents_as` set rather than through a presenter Family.

`MotionController` is the first separately-modelled drive-electronics Family. v1 ships empty affordances by design: the meaningful state on a controller is configuration (firmware version, IP address, axis count, protocol) and identity (serial number), captured in `settings` and `alternate_identifiers`. Command-tier affordances (firmware-update, reboot, sync-output toggling) are deferred until an operator-side Procedure demands them, at which point they grow on the existing add-only affordance amendment path.

## Hexapod DoF model

`Hexapod` is one physical Device (the vendor-sealed Aerotech HEX300; inverse kinematics runs in controller firmware). Its six degrees of freedom are surfaced as six `PseudoAxis` sub-modules parented to it (Device-in-Device, the addressable-sub-module case the `register_asset` decider sanctions), so a Plan, Procedure, or Caution can address a single DoF by name. Each DoF carries a `SolverReference` partition rule naming the firmware solver (`2bmHXP`); the per-DoF envelope is NOT duplicated onto the facets (it stays on the [`Hexapod` settings schema](#hexapod) for the physical unit), and the EPICS PVs live in each facet's `alternate_identifiers`, not in its name.

| DoF Asset | Kind | Axis | Vendor rotation label |
| --- | --- | --- | --- |
| `Hexapod_X` | translation | along X | n/a |
| `Hexapod_Y` | translation | along Y | n/a |
| `Hexapod_Z` | translation | along Z | n/a |
| `Hexapod_Roll` | rotation | about X | A (`travel_a`) |
| `Hexapod_Pitch` | rotation | about Y | B (`travel_b`) |
| `Hexapod_Yaw` | rotation | about Z | C (`travel_c`) |

The A/B/C labels are the schema's own (`travel_a` = about X, etc.). The EPICS channel map (`2bmHXP:m1`-`2bmHXP:m6`) will live in each facet's `alternate_identifiers` once an operator confirms it; the 2-BM source page names two rotational channels (`2bmHXP:m4`, `2bmHXP:m5`) but the full six-channel-to-axis mapping is unverified, so it is not asserted here (tracked as `HXP-1` in [Open questions](questions.md)).

### Constituent-port wiring

Each DoF reads its feedback from the physical `Hexapod` and exposes one operator-addressable virtual port. The link is `Plan.wires`, not a field on the partition rule: no rule shape carries a constituent id, and `SolverReference` lets the firmware own the kinematics, so the constituents are read from the wires at evaluate time.

| Asset | Port | Direction | `signal_type` |
| --- | --- | --- | --- |
| `Hexapod` | `x_feedback_out`, `y_feedback_out`, `z_feedback_out` | OUTPUT | `position_feedback_linear_mm` |
| `Hexapod` | `roll_feedback_out`, `pitch_feedback_out`, `yaw_feedback_out` | OUTPUT | `position_feedback_rotation_deg` |
| `Hexapod_X` / `_Y` / `_Z` | `constituent_in` | INPUT | `position_feedback_linear_mm` |
| `Hexapod_X` / `_Y` / `_Z` | `x_out` / `y_out` / `z_out` | OUTPUT | `position_setpoint_linear_mm` |
| `Hexapod_Roll` / `_Pitch` / `_Yaw` | `constituent_in` | INPUT | `position_feedback_rotation_deg` |
| `Hexapod_Roll` / `_Pitch` / `_Yaw` | `roll_out` / `pitch_out` / `yaw_out` | OUTPUT | `position_setpoint_rotation_deg` |

Six wires, one per DoF (`Hexapod.<axis>_feedback_out -> Hexapod_<Axis>.constituent_in`), carry the feedback each PseudoAxis needs to reconstruct its readback. `validate_pseudoaxis_fanout` accepts each: exactly one OUTPUT port on the facet, one incoming wire, homogeneous `signal_type`, and `SolverReference` is exempt from the arity check.

These ports and wires are modelled and validate at Plan-bind, but the runtime that would decompose a virtual setpoint into hexapod motion (`eval_solver_reference`) is still deferred and raises `NotImplementedError`, so the wired Plan is not yet runtime-executable. The executable model lives in `apps/api/tests/integration/scenarios/test_2bm_hexapod_pose_wiring.py`.

## Vendor catalog (Models)

Per-Asset Model bindings carry the vendor identity that PIDINST Property 6 (Manufacturer) and Property 7 (Model) need. Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families. The four Microscope-housing Models (lens turret motor, Mitutoyo MPLAPO objective kit, FLIR Oryx camera, Crytur LuAG scintillator) live on the [Microscope deployment](equipment/microscope.md#vendor-catalog-models) page; the table below tracks Models bound to non-microscope 2-BM Assets.

| Model | Manufacturer | Part number | Declared Families | Bound at 2-BM |
| --- | --- | --- | --- | --- |
| `aerotech_hex300` | Aerotech | `HEX300-230HL-E1-PL4-TAS` | `Hexapod` | `Hexapod` |
| `aerotech_abs250mp` | Aerotech | `ABS250MP-M-AS` | `RotaryStage` | `Rotary` |
| `aerotech_ensemble` | Aerotech | `HLE10-40-A-MXH` | `MotionController` | `RotaryDrive` |
| `aerotech_hexapod_drive_unknown_pn` | Aerotech | `unknown-pending-confirmation` (DRIVE-4) | `MotionController` | `HexapodDrive` |
| `aerotech_2bmbaero_drive_unknown_pn` | Aerotech | `unknown-pending-confirmation` (DRIVE-4) | `MotionController` | `FocusDrive` |
| `aerotech_pro225sl` | Aerotech | `PRO225SL-1000` | `LinearStage` | `Focus` |
| `oms_vme58` | Oregon Micro Systems | `VME58` | `MotionController` | `SampleStageDrive`, `FrontEndDrive` |
| `kohzu_cyat070` | Kohzu | `CYAT-070` | `LinearStage` | `SampleTop_X`, `SampleTop_Z` |

A Model id is deterministic: `model_stream_id` derives it as `uuid5` over the canonical `(lowercased manufacturer name, case-preserved part number)` vendor key, so the same vendor product converges on one id across facilities and a second `define_model` on the same real key returns `409`. `oms_vme58` is the convergence case in the table: both `SampleStageDrive` and `FrontEndDrive` bind the one `oms_vme58` Model row (one product, two physical boards). The two `unknown-pending-confirmation` rows are the deliberate exception: that placeholder part number is NOT a real vendor key, so `model_stream_id` falls back to a random id, keeping `aerotech_hexapod_drive_unknown_pn` and `aerotech_2bmbaero_drive_unknown_pn` distinct rather than collapsing both unconfirmed drives onto one identity. When their real part numbers are confirmed, each re-registers under its derived id.

Part-number suffix conventions vary by vendor: Aerotech's `HEX300-230HL-E1-PL4-TAS` encodes operationally significant variants (`-E1` incremental encoder, `-PL4` ultra-high-accuracy preload, `-TAS` thermal-actively-stabilized); `ABS250MP-M-AS` follows the same pattern (`-M` mid-precision class, `-AS` air-bearing series); `PRO225SL-1000` carries the `-1000` mm travel suffix natively. v1 stores the full type designation as a single `part_number` string; the catalog convention upgrades to suffix decomposition at the second case where a suffix axis crosses Model boundaries (rule-of-three), or at the first APS imaging stage+drive registration, whichever fires first.

All five `MotionController` Assets are named for the function they serve (the device or station they drive); the vendor identity lives on the bound `Model` and the EPICS / IOC handle in `alternate_identifiers`, per the [Asset instance names](../../reference/conventions.md#asset-instance-names) convention. The Aerotech Ensemble HLE10-40-A-MXH (companion drive for `aerotech_abs250mp`) IS now modelled as a separate Asset (`RotaryDrive`) with `tier = Device` under 2-BM, with `Rotary.controller_id` carrying the back-reference. This was the FIRST `MotionController` Asset shipped, anchoring the controller-as-Asset slice on the unambiguously-identified rotary drive per `project_controller_as_asset_stage1_design`. A SECOND `MotionController` Asset (`HexapodDrive`) now models the drive for `Hexapod`, with `Hexapod.controller_id` carrying the back-reference; the 2-BM source page does not name the drive's specific product line (the EPICS interface is "native Aerotech Ensemble" but the box is not identified, nor is rack-separate vs sealed-in integration confirmed), so the Model row uses `unknown-pending-confirmation` for the part number and the per-Asset Settings block carries placeholders that operators replace via `update_asset_settings` once the physical hardware is verified. A THIRD `MotionController` Asset (`FocusDrive`) models the drive electronics that the `2bmbAERO` EPICS IOC manages on behalf of `Focus`; the Asset is named for its function and the IOC handle `2bmbAERO` is recorded in `alternate_identifiers` (kind `EPICS_PV`) rather than in the name. The drive's product line is almost certainly Aerotech Ensemble-family but unconfirmed on the source page, so the same `unknown-pending-confirmation` pattern carries the per-unit identity placeholders. A FOURTH `MotionController` Asset (`SampleStageDrive`) now models the Oregon Micro Systems VME58 motor controller card in the 2-BM b-station IOC crate (`ioc2bmb`), which drives the `2bmb:m1`-`2bmb:m91` motor band including `SampleTop_X` (`2bmb:m18`) and `SampleTop_Z` (`2bmb:m17`); both stage Assets now carry `controller_id` back-references to `SampleStageDrive`. The remaining 89 driven motors on the 2bmb crate live in [Pending](#pending) until each earns its own Asset registration; the controller Asset is the addressability handle that makes a future "VME-bus glitch took out m1-m91" Caution scope honestly to the bus rather than dispersing across 91 motor Assets. A FIFTH `MotionController` Asset (`FrontEndDrive`) models the sibling OMS VME58 board in the 2-BM a-station IOC crate (`ioc2bma`), which drives the front-end / beam-conditioning motor band (the `Mirror`, the `Monochromator`, the `ConditioningSlit` and `SampleSlit`, and the `Filter`, all enumerated in [Pending](#pending)); none of those driven motors are modelled at v1, so the controller Asset ships in isolation with no current `controller_id` back-references pointing at it. The controller registration still ships because absence-of-tracking on hardware that demonstrably exists (and gets rebooted, replaced, firmware-versioned by 2-BM operators) is exactly the self-justifying-defer that `feedback_intentional_modeling_not_mirroring` exists to forbid. Both OMS-VME58 instances bind to the same `oms_vme58` Model row per the one-Model-per-product-line convention; per-instance identity (serial number, firmware version) lives in the per-Asset Settings block. PARTIAL SHIP today is 5 of 7 controller hardware classes; the remaining 2 (Nanotec ST4118 stepper inside Optique Peter, and the Schunk LPTM 30 inside the camera selector) remain deferred per `project_controller_as_asset_research`; each earns its own Stage-1 call when its own trigger fires.

The six `Hexapod_*` DoF facets are PseudoAxis Assets (virtual DoFs over the `2bmHXP` hexapod-kinematics solver) and do not bind to a vendor Model: the Model-binding flow (PIDINST) targets physical commissioned hardware, so the physical `Hexapod` carries the Model binding (`aerotech_hex300`) and the facets inherit vendor identity through the constituent wiring. The full six-DoF surface and its constituent-port wiring are described under [Hexapod DoF model](#hexapod-dof-model). The Kohzu SA16A-RM goniometer (`LaminographyPitch`, `2bmb:m49`) is a SEPARATE, permanently-installed stage (staff source page `item_020`), not the hexapod's `Hexapod_Pitch` axis; tomography vs laminography is a tilt setpoint on it, not an insert/remove. Its Model `kohzu_sa16a` is now in the [vendor catalog](../../catalog/index.md), bound when `LaminographyPitch` is registered (currently in [Pending](#pending)). The exact model is the operator working value pending confirmation (STAGE-6: the source swivel kit also lists `SA16A-RS` / `SA07A-R2L`).

## Family settings schemas

NEW schemas registered for the 2-BM deployment. The `RotaryStage`, `LinearStage`, and `Scintillator` schemas are declared at the [APS Site assets](../aps/assets.md) level once a second beamline uses them; today they remain implicit in the per-Asset [Settings](#settings) values below. The `Camera` schema is made explicit below: the 2-BM detector classes (the active FLIR Oryx and the decommissioned PCO Dimax) differ along settings axes (`max_framerate_hz`, `sensor_kind`, `readout_mode`), not Family axes, so the high-framerate variant stays a `Camera` rather than a separate Family. `PseudoAxis` carries no settings schema (it is a facet Family).

### `Objective`

Intrinsic per-lens properties. Motion is via the lens turret motor wired into the Assembly; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

### `Hexapod`

Operational envelope of a 6-DoF parallel-kinematic positioner. The schema captures the vendor-published envelope (per-DoF travel, speed, resolution, accuracy, load capacity) without exploding the legs as sub-Assets (vendor-sealed unit; inverse kinematics runs in controller firmware, not in CORA). DoF-level addressability is realized by six per-DoF PseudoAxis sub-modules (`Hexapod_X` ... `Hexapod_Yaw`) parented to this Hexapod, each carrying a `SolverReference` partition rule and wired to a hexapod feedback port; see [Constituent-port wiring](#constituent-port-wiring). The envelope below stays the single contract for the physical unit; the DoF facets carry no settings of their own.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `travel_x` | number > 0 | mm | single-axis from home; translation envelope |
| `travel_y` | number > 0 | mm | |
| `travel_z` | number > 0 | mm | |
| `travel_a` | number > 0 | deg | rotation envelope around X (Roll; DoF `Hexapod_Roll`) |
| `travel_b` | number > 0 | deg | rotation envelope around Y (Pitch; DoF `Hexapod_Pitch`) |
| `travel_c` | number > 0 | deg | rotation envelope around Z (Yaw; DoF `Hexapod_Yaw`) |
| `max_speed_translation` | number > 0 | mm/s | typically dominated by the slowest translation axis |
| `max_speed_rotation` | number > 0 | deg/s | typically dominated by the slowest rotation axis |
| `resolution_translation` | number > 0 | nm | encoder resolution for X/Y/Z (vendor reports a common value) |
| `resolution_rotation` | number > 0 | urad | encoder resolution for A/B/C |
| `accuracy_translation` | number > 0 | um | bidirectional positioning accuracy, dominant translation DoF |
| `accuracy_rotation` | number > 0 | urad | bidirectional positioning accuracy, dominant rotation DoF |
| `load_capacity_vertical` | number > 0 | kg | rated load with platform horizontal |
| `load_capacity_horizontal` | number > 0 | kg | rated load with platform vertical |
| `stage_mass` | number > 0 | kg | bare platform mass (excludes mounted payload) |

The pairs `max_speed_translation` / `max_speed_rotation`, `resolution_*`, and `accuracy_*` collapse the six per-DoF measurements down to two values per metric in v1; the vendor datasheet reports per-DoF variation small enough that the dominant-DoF figure is a faithful envelope. The six per-DoF PseudoAxis facets (`Hexapod_X` ... `Hexapod_Yaw`) are the surface a Method binds against when it addresses a single DoF; the schema above stays as the envelope contract for the physical unit. No pilot Method addresses a single DoF yet, and the runtime solver bridge that would execute such a setpoint (`eval_solver_reference`) is still deferred, so the facets are modelled and wiring-validated but not yet runtime-executable.

### `MotionController`

Identity + configuration + connectivity of a separately-modelled drive-electronics box. Field selection follows the intentional-design posture: every field exists because reproducibility, federation, or operational reasoning needs it, not because the existing 2-BM ad-hoc representation already carries it. Per-axis Procedures continue to target the driven stage Asset; controller-tier Procedures (firmware update, controller swap, sync-output retune) target the controller Asset and read these fields. See `project_controller_as_asset_stage1_design`.

| Setting | Type | Required | Notes |
| --- | --- | --- | --- |
| `serial_number` | string, 1-128 chars | yes | Per-unit identity; operator-facing canonical key. Distinct from `Asset.alternate_identifiers` (PIDINST cross-reference set), which can also carry serial numbers among other schemes; `serial_number` here is the single operator-blessed canonical value. |
| `firmware_version` | string, 1-64 chars | yes | Reproducibility provenance. Required intentionally per the intentional-modeling posture: absence-of-operator-demand is the failure mode that posture exists to forbid. A controller without a recorded firmware version cannot honestly answer the "did the firmware change between Run X and Run Y" question. Free-text in v1; semver validation defers to the second-vendor proof. |
| `ip_address` | string, 7-45 chars | no | Network identity. Optional because not every controller class is network-attached (RS-232 / RS-485 / VME-bus boxes have no IP). Format validation is shape-only at this layer (route / Pydantic may impose IPv4 / IPv6 regex when deployments warrant it). |
| `axis_count` | integer, 1-91 | yes | Operational metadata. Bounds bracket smallest single-axis (1) to largest OMS-VME58 deployment at 2-BM (91 Kohzu motors). Drives the eventual multi-motor Caution-fans-out semantics when that trigger fires. |
| `protocol` | closed enum: `EPICS \| Aerotech_Native \| OMS_VME \| Serial_RS232 \| Serial_RS485 \| Modbus_TCP \| Other` | yes | Communication protocol. Six known plus `Other` escape valve; future additions follow the add-only-enum convention. |

`manufacturer` is NOT on this schema: vendor identity lives on the bound Model row per the Capability-declares-settings-schema pattern (`Aerotech` for `RotaryDrive` comes from `aerotech_ensemble`).

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

### `Table`

The support/positioning table Family (the hutch optical tables; staff name it in the [2-BM components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html)). One Family spans three 2-BM tables that differ only along a settings axis (the motor/axis layout), not a Family axis, so it is one `Table` Family rather than a split: `SampleTable` (four direct translation motors, no combined record), `DetectorTable` (six virtual axes on record `2bmb:table3`, computed from six support motors in an SRI 3-Y / 2-X / 1-Z geometry), and the unused `MirrorTable` (`Dma:table1`). The Family carries motion affordances for the axes a given table drives; the carries-other-equipment relationship is `Asset.parent_id` placement, not an affordance. Draft schema pending registration; the EPICS handles (the virtual record and per-axis or support-motor PVs) live in each Asset's `alternate_identifiers`, not in the schema.

| Setting | Type | Notes |
| --- | --- | --- |
| `axis_layout` | closed enum: `translation_xyz \| virtual_pose` | The families-settings-over-subtypes discriminator: which motor/axis layout this table presents. `translation_xyz` = the sample table's direct motors; `virtual_pose` = a composite record exposing translation + tilt virtual axes (the detector and mirror tables; the specific record goes in `virtual_record`). Add-only enum. |
| `virtual_record` | string, optional | The composite EPICS record when the table exposes one (`2bmb:table3`, `Dma:table1`); absent for the sample table, which addresses its four motors directly. |
| `geometry` | string, optional | Support-point layout when the axes are computed from support motors (for example, SRI 3 Y-supports / 2 X-supports / 1 Z-support). |

## Settings

### `RotaryDrive`

Bound to Model `aerotech_ensemble`. The Aerotech Ensemble HLE10-40-A-MXH digital drive that runs `Rotary`. First `MotionController` Asset shipped at 2-BM; the back-reference lives on `Rotary.controller_id`.

Placeholder values below are intentional. The controller-as-Asset design ships the substrate for reproducibility provenance now; the actual operator-confirmed firmware version and serial number land via `update_asset_settings` once 2-BM staff verifies them on the physical hardware. Leaving the fields out entirely would silently re-create the 2-BM ad-hoc absence-of-tracking that the slice exists to address.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `FocusDrive`

Bound to Model `aerotech_2bmbaero_drive_unknown_pn`. The Aerotech drive electronics that the `2bmbAERO` EPICS IOC manages on behalf of `Focus`. Third `MotionController` Asset shipped at 2-BM; the back-reference lives on `Focus.controller_id`.

Operators address the focus motor via `2bmbAERO:m1` (IOC name + motor channel); the IOC is software (an EPICS process) while the Asset modelled here is the hardware drive box behind it (per OPC UA DI / AAS DigitalNameplate alignment, CORA models field-replaceable, firmware-versioned drive electronics rather than the software process talking to them). The drive's specific product line is not named on the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the IOC handle `2bmbAERO` lives in `alternate_identifiers` (kind `EPICS_PV`) rather than the name, and settings placeholders cover identity details that operators verify on the physical hardware.

`axis_count=1` reflects the 1:1 binding to the single focus_Z stage; `protocol=Aerotech_Native` matches the rotary anchor's posture for the same vendor family.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `SampleStageDrive`

Bound to Model `oms_vme58`. The Oregon Micro Systems VME58 motor controller card in the 2-BM b-station IOC crate (`ioc2bmb`), which drives the `2bmb:m1`-`2bmb:m91` motor band per the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Fourth `MotionController` Asset shipped at 2-BM; the back-references live on `SampleTop_X.controller_id` and `SampleTop_Z.controller_id` (`2bmb:m18` and `2bmb:m17` respectively); the remaining 89 driven motors on this crate are tracked in [Pending](#pending).

Operators address motors on this crate via the EPICS channel naming `2bmb:m<N>` (IOC name + motor channel); the IOC is software (an EPICS process running in the `ioc2bmb` crate) while the Asset modelled here is the OMS VME58 hardware board itself. Same OPC UA DI / AAS DigitalNameplate alignment as the Aerotech drives: CORA models the field-replaceable, firmware-versioned drive electronics rather than the software process that addresses them. The Aerotech Ensemble axes (`2bmb:m100`-`2bmb:m102`) on the same IOC are addressed through a separate Aerotech HLE10-40-A-MXH and ship as their own `RotaryDrive` Asset; one IOC, two physical controllers, two MotionController Assets.

`axis_count=91` is the OMS-VME58 card's slot-cardinality at 2-BM and the upper bound of the settings_schema range; even though only two of the 91 channels are currently bound to modelled stages, the controller's intrinsic capacity is the value the field records. `protocol=OMS_VME` matches the closed-enum value in the `MotionController` settings schema. The drive is VME-bus addressed (not IP-attached), so `ip_address` is omitted.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

`ip_address` is omitted (VME-bus addressed, no IP); the field is optional on the schema. `serial_number` and `firmware_version` carry the same `unknown-pending-confirmation` placeholders as the Aerotech drives; operator confirmation lands via `update_asset_settings` once the 2-BM staff verifies the physical card.

### `FrontEndDrive`

Bound to Model `oms_vme58` (same product line as `SampleStageDrive`; one Model row, two Asset instances). The Oregon Micro Systems VME58 motor controller card in the 2-BM a-station IOC crate (`ioc2bma`), which drives the front-end / beam-conditioning motor band (the `Mirror`, the `Monochromator`, the `ConditioningSlit` and `SampleSlit`, and the `Filter`, per the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html)). Fifth `MotionController` Asset shipped at 2-BM; NO `controller_id` back-references point at this controller from any v1-modelled stage because the front-end driven motors are all in [Pending](#pending), each row there enumerating the band this controller drives.

The controller still ships as an Asset because its existence in reality is the load-bearing fact (operators reboot it, replace it, version its firmware) regardless of whether any driven motor is yet modelled in CORA. Waiting for a driven-stage trigger before registering the controller would invert the dependency the controller-as-Asset substrate is designed around: stages depend on controllers (`controller_id` is a forward reference from the stage), not the other way round. When the front-end stages get modelled in a future slice, they will reference this controller's id verbatim without retroactive controller registration ceremony.

`axis_count=91` matches the OMS-VME58 card's slot-cardinality (identical to `SampleStageDrive`; per-card hardware capacity, not per-deployment binding count). `protocol=OMS_VME` matches the closed-enum value. `ip_address` is omitted (VME-bus addressed).

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

`ip_address` is omitted (VME-bus addressed, no IP); the field is optional on the schema. Both placeholders land via `update_asset_settings` once 2-BM staff verifies the physical card; the 2bma + 2bmb cards carry distinct serial numbers and may run distinct firmware versions despite sharing a Model row.

### `HexapodDrive`

Bound to Model `aerotech_hexapod_drive_unknown_pn`. The Aerotech drive electronics that run `Hexapod`. Second `MotionController` Asset shipped at 2-BM; the back-reference lives on `Hexapod.controller_id`.

The Asset is named for its function (the hexapod drive). What the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) actually says (Aerotech vendor, drives the hexapod stage, EPICS interface is "native Aerotech Ensemble") is captured where it belongs: the vendor on the bound `Model`, the "native Aerotech Ensemble" handle in `alternate_identifiers`. The page does not name the controller box, nor confirm whether the drive sits in a separate rack or is sealed into the HexGen stage, so the product line is not overclaimed. The Asset still ships now per the intentional-modeling rule (waiting for source-page disambiguation would let the ad-hoc absence-of-tracking self-justify indefinitely); operator confirmation lands later via `update_asset_settings` and a `version_model` of the bound Model row.

Placeholder values below follow the same intentional-design posture as `RotaryDrive`. The `axis_count=6` is the operationally meaningful integer for any hexapod drive: a hexapod has 6 DoF, regardless of which Aerotech product line the controller belongs to.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `6` |
| `protocol` | `Aerotech_Native` |

`ip_address` is omitted at v1 pending operator confirmation; the field is optional on the schema.

### `Rotary`

Bound to Model `aerotech_abs250mp`. Aerotech ABS250MP-M-AS air-bearing direct-drive rotary stage (250 mm aperture, mid-precision class), driven by `RotaryDrive` (referenced via `Rotary.controller_id`).

| Setting | Value |
| --- | --- |
| `min_position` | `−360 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `720 deg/s` |
| `encoder_resolution` | `0.0001 deg` |
| `homing_offset` | `0 deg` |

### `SampleTop_X`

Bound to Model `kohzu_cyat070`, driven by `SampleStageDrive` (referenced via `SampleTop_X.controller_id`; addressed on EPICS channel `2bmb:m18`). Kohzu CYAT-070 crossed-roller alignment stage (80 x 80 mm table, ball-screw lead 1.0 mm). Sister Asset `SampleTop_Z` binds the same Model and the same controller. The full vendor-published envelope (±0.5 um repeatability, lost motion ≤ 2 um, backlash ≤ 1 um, straightness ≤ 3 um per 30 mm, load 98 N, weight 1.7 kg) lives on the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the v1 Settings below capture only the operationally bound min/max/speed/resolution fields.

| Setting | Value |
| --- | --- |
| `min_position` | `−10 mm` |
| `max_position` | `10 mm` |
| `max_speed` | `1 mm/s` |
| `encoder_resolution` | `0.0005 mm` |

### `Hexapod`

Bound to Model `aerotech_hex300`, driven by `HexapodDrive` (referenced via `Hexapod.controller_id`). Values from the Aerotech HEX300-230HL product datasheet (Hex300-Data-Sheet-D20250203). Per-DoF figures collapse to the dominant axis where the vendor's range across DoFs fits within a faithful envelope (e.g., translation accuracy reported as the laxest of X / Y / Z).

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

### `Scintillator`

| Setting | Value |
| --- | --- |
| `thickness` | `100 um` |
| `decay_time` | `0.07 us` |

### `Camera`

| Setting | Value |
| --- | --- |
| `sensor_width` | `2448 pixel` |
| `sensor_height` | `2048 pixel` |
| `pixel_size` | `3.45 um` |
| `bit_depth` | `12 bit` |

### `Objective_10x` (10x)

| Setting | Value |
| --- | --- |
| `magnification` | `10.0` |
| `numerical_aperture` | `0.28` |
| `focal_length` | `20 mm` |
| `working_distance` | `33.5 mm` |

### `Objective_2x` (2x)

| Setting | Value |
| --- | --- |
| `magnification` | `2.0` |
| `numerical_aperture` | `0.055` |
| `focal_length` | `100 mm` |
| `working_distance` | `34 mm` |

### `Objective_1.1x` (1.1x)

| Setting | Value |
| --- | --- |
| `magnification` | `1.1` |
| `numerical_aperture` | `0.03` |
| `focal_length` | `200 mm` |
| `working_distance` | `50 mm` |

### `Turret`

`RotaryStage` Family assumed (pending 2-BM operator confirmation; if the turret is a translating slide, the Family flips to `LinearStage` and the signal types switch from `rotation_deg` to `linear_mm`).

| Setting | Value |
| --- | --- |
| `min_position` | `0 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `30 deg/s` |
| `encoder_resolution` | `0.01 deg` |

## Engineering drawings

Each Asset may carry one canonical engineering reference as a `(system, number, revision)` triple per the [Drawing VO](../../architecture/modules/equipment/index.md). The carrier holds the build-to document for the physical specimen; the [Mount drawing](equipment/microscope.md#engineering-drawings) on the slot is a separate document (where the slot lives in the beamline). v1 is single-valued; the Drawing-frozenset promotion and `Model.drawing` / `Fixture.drawing` extensions defer to the rule-of-three trigger.

Assets not listed below have no canonical document cited on the 2-BM source page yet (Aerotech `ABS250MP` datasheet for `Rotary`, Kohzu `CYAT-070` datasheet for the four `SampleTop_*` stages, an APS shutter drawing for `StationShutter`, and a FLIR Oryx datasheet for `Camera`). These populate when the operator confirms the canonical reference.

### `Hexapod`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `Hex300-Data-Sheet` |
| `revision` | `D20250203` |

Aerotech HEX300-230HL hexapod product datasheet (Hex300-Data-Sheet-D20250203.pdf). The Microscope deployment cites this as the structured reference for the 6-DoF positioner that anchors the sample stack.

### `Focus`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

Optique Peter MICRX080 microscope manual (MAN-11863-0521-0465-A, 21 May 2021, 53 pages). The shared vendor manual covers every Optique Peter housing constituent (focus stage, lens turret, lens kit, scintillator). Same reference attaches to each Microscope-bound Asset below.

### `Turret`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `Objective_10x`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

v1 attaches the housing manual as the canonical reference; the Mitutoyo MPLAPO LWD per-magnification datasheet is the eventual upgrade once part numbers are verified (see the [vendor catalog note](equipment/microscope.md#vendor-catalog-models) on the Plan-Apo-NIR three-part-number split).

### `Objective_2x`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `Objective_1.1x`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `Scintillator`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

## Pending

Devices that physically exist at 2-BM but are not yet registered as CORA Assets; each carries `new: true` in the 2-BM descriptor (`deployments/2-bm/beamline.yaml`). The first five rows are the front-end / beam-conditioning motor band driven by `FrontEndDrive` (they hold `2bma:m` channels in the descriptor): that controller ships modelled while none of its driven stages do. `BeamPositionMonitor` is a sixth unmodelled front-end device but a diagnostic, not a motor: the descriptor records no PV or controller for it.

Three `Table`-Family support tables also sit here pending registration: `SampleTable` (the four-motor translation table on the Vibraplane base that carries the hexapod stack), `DetectorTable` (the six-virtual-axis `2bmb:table3` table under the Optique Peter stage and microscope), and `MirrorTable` (`Dma:table1`, present but not used operationally). They differ by axis layout, not Family, so they share one `Table` Family ([Family settings schemas](#table)). Whether to describe all three, and whether the axis layout is a settings difference or a Family split, is tracked as `STAGE-7` and `STAGE-8` in [Open questions](questions.md).

| Asset | Family |
| --- | --- |
| `Mirror` | `Mirror` |
| `Monochromator` | `Monochromator` |
| `ConditioningSlit` | `Slit` |
| `SampleSlit` | `Slit` |
| `Filter` | `Filter` |
| `BeamPositionMonitor` | `Diagnostic` |
| `Timing` | `TimingController` |
| `SampleTable` | `Table` |
| `DetectorTable` | `Table` |
| `MirrorTable` | `Table` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |

`TimingController` here is the catalog-aligned Family, replacing the earlier `TriggerFPGA` placeholder. Substrate ("FPGA") is not a Family axis: the softGlueZynq is a `TimingController` whose identity + gateware version live in `settings`, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

## Decommissioned (provenance only)

Detectors 2-BM ran in the past. They are neither active Assets nor awaiting registration; [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) records them under `decommissioned` for provenance. When modelled they are `Camera` Assets in a terminal lifecycle state: the `Camera` Family spans them and the active FLIR Oryx, because performance class ("high-speed") is a settings axis, not a separate Family, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

| Asset | Family | Note |
| --- | --- | --- |
| `PCO_Dimax_HS` | `Camera` | High-speed CMOS camera; superseded by the FLIR Oryx detector chain. |
| `Adimec_Quartz_Q-12A180` | `Camera` | Earlier 2-BM CoaXPress camera. |
