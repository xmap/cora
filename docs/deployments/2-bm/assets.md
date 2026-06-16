# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself is a root Asset with `tier = Unit` (bound to its Site Facility via `facility_code`) and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

The Microscope detector is modelled as an Assembly + Fixture pair over a reusable Optics sub-assembly, with the constituents contained in one `Housing` Asset. The constituent Assets appear in the inventory below; the composition, containment, and wiring story lives on the dedicated [Microscope deployment](equipment/microscope.md) page.

The sample positioning stack is modelled as a `SampleTower` Assembly + Fixture presenting as the `Positioner` Role, with the stages held in a literal-deep containment chain (each stage parents the one above). The composition, the containment chain, and the experiment-vs-loadout boundary (tomography, laminography, and mosaic are all Recipe Methods/Plans over one Fixture) live on the dedicated [Sample tower deployment](equipment/sample_tower.md) page.

Devices are located in one of the two hutch Enclosures, the optics hutch `2-BM-A` or the experiment hutch `2-BM-B`, declared per Device via `located_in_enclosure_id`. The Located-in column below records where each Device sits; the two hutches and the pre-flight gate they drive are on the [Enclosures](enclosures.md) page. The hutches are Enclosures, not Assets, so they do not appear as inventory rows.

## Inventory

| Asset | Tier | Family | Parent | Located in |
| --- | --- | --- | --- | --- |
| `StationShutter` | `Device` | `Shutter` | `2-BM` | `2-BM-B` |
| `RotaryDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `Rotary` | `Device` | `RotaryStage` | `2-BM` (driven by `RotaryDrive`) | `2-BM-B` |
| `SampleStageDrive` | `Device` | `MotionController` | `2-BM` | `2-BM-B` |
| `FrontEndDrive` | `Device` | `MotionController` | `2-BM` (a-station OMS VME58; drives the front-end optics band) | `2-BM-A` |
| `Mirror` | `Device` | `Mirror` | `2-BM` (driven by `FrontEndDrive`) | `2-BM-A` |
| `Monochromator` | `Device` | `Monochromator` | `2-BM` (driven by `FrontEndDrive`) | `2-BM-A` |
| `Monochromator_BraggArmUpstream` | `Device` | `PseudoAxis` | `Monochromator` (energy-driven; LookupTable converts energy in keV to the upstream Bragg-arm angle in deg) | `2-BM-A` |
| `Monochromator_BraggArmDownstream` | `Device` | `PseudoAxis` | `Monochromator` (energy-driven; downstream Bragg-arm angle in deg) | `2-BM-A` |
| `Monochromator_M2Y` | `Device` | `PseudoAxis` | `Monochromator` (energy-driven; M2 vertical beam-offset compensator in mm) | `2-BM-A` |
| `ConditioningSlit` | `Device` | `Slit` | `2-BM` (white-beam slits; driven by `FrontEndDrive`) | `2-BM-A` |
| `Filter` | `Device` | `Filter` | `2-BM` (foil changer; driven by `FrontEndDrive`) | `2-BM-A` |
| `Filter_FoilSelector` | `Device` | `PseudoAxis` | `Filter` (discrete foil selector; LookupTable snaps a slot index to the downstream paddle position) | `2-BM-A` |
| `SampleSlit` | `Device` | `Slit` | `2-BM` (B-station slits; driven by `FrontEndDrive`) | `2-BM-B` |
| `SampleSlit_VerticalTop` | `Device` | `PseudoAxis` | `SampleSlit` (energy-driven; top blade tracks the per-energy beam position in mm) | `2-BM-B` |
| `SampleSlit_VerticalBottom` | `Device` | `PseudoAxis` | `SampleSlit` (energy-driven; bottom blade tracks the per-energy beam position in mm) | `2-BM-B` |
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
| `Timing` | `Device` | `TimingController` | `2-BM` (softGlueZynq trigger box; generates the camera trigger train via PSO, no `controller_id`) | `2-BM-B` |
| `Housing` | `Component` | `Housing` | `2-BM` (installed into a Mount; parents the Microscope constituents) | `2-BM-B` |
| `Turret` | `Device` | `LinearStage` | `Housing` (bound into Microscope Fixture; sliding ball-screw objective selector) | `2-BM-B` |
| `Objective_10x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_2x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_1.1x` | `Device` | `Objective` | `Housing` (bound into Microscope Fixture) | `2-BM-B` |
| `Objective_Selector` | `Device` | `PseudoAxis` | `Housing` (bound into Microscope Fixture; partition rule decomposes lens index to turret position in mm) | `2-BM-B` |
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
| `TiltStage` | `Rotatable`, `Homeable`, `Limitable` |
| `Scintillator` | `Consumable` |
| `Camera` | `Imageable`, `Binnable`, `Triggerable`, `Streamable`, `Recording` |
| `Housing` | (empty; the containment chassis Family carried by the `Housing` Asset that parents the Microscope constituents; no command surface) |
| `Objective` | (pending: empty at initial registration) |
| `PseudoAxis` | (empty; partition rules live on `Asset.partition_rule`, not as affordances) |
| `Table` | `Translatable`, `Rotatable` (provisional superset for the hutch support tables: the sample table is translation-only, the detector table adds tilt axes; the per-table axis set is a settings difference, not a Family split, see [Family settings schemas](#table)). Carries-other-equipment is `parent_id` placement, not an affordance; there is no Supporting affordance. Assets are [Pending](#pending) until seeded. |
| `Slit` | `Translatable`, `Homeable`, `Limitable` (four independently-driven blades; the ConditioningSlit and SampleSlit instances share this Family) |
| `Mirror` | `Translatable`, `Homeable`, `Limitable` (vertical jacks set the deflection geometry; the coating stripe selector tracks energy and beam mode, see [Filter foil selection](#filter-foil-selection)) |
| `Monochromator` | `Translatable`, `Homeable`, `Limitable` (the Bragg arms and the M2 vertical offset set the energy via an IOC coordinated move; insertable, bypassed in pink beam) |
| `Filter` | `Indexable`, `Attenuable` (discrete absorber-foil selection that attenuates the white beam) |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface). `PseudoAxis` is a facet Family: it carries no affordances, but Methods bind against it via `needed_family_ids`, and the Family membership is the gate that lets an Asset carry a `partition_rule`. Detector Assemblies, including the Microscope, advertise the `Detector` Role through the Assembly's `presents_as` set rather than through a presenter Family; the `SampleTower` Assembly likewise advertises the `Positioner` Role. `TiltStage` is the Kohzu laminography goniometer (a rotational, limited-range stage, so not `LinearStage`, and not `RotaryStage` whose `Following`/`Marking` PSO affordances a tilt does not carry).

`MotionController` declares no command affordances. A controller's meaningful state is configuration (firmware version, IP address, axis count, protocol) and identity (serial number), carried in `settings` and `alternate_identifiers` rather than in a command surface.

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

The A/B/C labels are the schema's own (`travel_a` = about X, etc.). The EPICS channel map is confirmed on the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html): `2bmHXP:m1` = X, `2bmHXP:m2` = Y, `2bmHXP:m4` = Pitch, `2bmHXP:m5` = Roll, recorded in each facet's `alternate_identifiers`. Z and Yaw exist on the physical hexapod but are not exposed as operator channels in 2-BM's current EPICS (there is no `m3`/`m6` operator handle), so those two facets carry no EPICS channel today. CORA still models all six DoF: the unexposed pair is a deployment-configuration limit, not a property of the device.

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

These ports and wires are modelled and validate at Plan-bind time. Decomposition of a virtual pose setpoint into physical hexapod motion is owned by the firmware solver named in each facet's `SolverReference` (`2bmHXP`), not by CORA.

## Energy-tracking optic axes

Setting the beam energy at 2-BM is a discrete coordinated move, not one knob. The staff energy-change IOC stores per-energy positions for the whole double-multilayer monochromator (the `store_0` saved table) and drives roughly fifteen motors together (some are discrete index moves, not continuous curves) to a configured set of energies (Mono 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV), per the staff-authored [docs2bm components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). The motors that actually move with energy are the DMM Bragg arms (`dmm_us_arm` / `dmm_ds_arm`) and the M2 vertical offset compensator (`dmm_m2_y`), plus the B-station sample-slit vertical pair (`b_slit_top` / `b_slit_bot`) tracking the resulting beam walk. Two things that look like energy axes are not: `crystal2_z` (M2 Z, `2bma:m8`) is a setup translation the IOC does not drive, and the mirror is held constant (its deflection geometry does not change with energy). Neither carries an energy curve.

CORA models each per-axis relationship as a continuous curve. The underlying physics is continuous (Bragg geometry), so the beamline's discrete saved list is its operational sampling, not a limit: CORA interpolates the saved points and can answer for an off-list energy too. The carrier is a `PseudoAxis` sub-module parented to the physical optic (Device-in-Device, like the hexapod DoFs), carrying a `LookupTable` partition rule that converts energy (`unit_in = "keV"`) to the axis position (`unit_out` is `deg` for the Bragg arms, `mm` for the offset compensator and the slit blades). The rule pins a `Calibration` revision by id rather than inlining the table, so the conversion is reproducible and survives recalibration.

The Calibration uses the `energy_position_curve` quantity, the catalog's first curve-valued (relationship) quantity. The scalar quantities (`magnification`, `rotation_center`) each carry one measured number and treat `energy` as an operating-point condition (the value you read at the energy you are at); here the whole curve across energy lives in ONE revision (a `points` array), because the curve is evaluated to reach any energy. Energy is the value-side independent variable; the operating-point only names which curve (`axis_designation` is the staff handle, `beam_mode` is `mono` since these axes track energy only in Mono mode).

`invertible = True`: the underlying Bragg geometry is monotonic in energy, so the readback reconstructs by inverse interpolation and the facet needs no constituent ports or Plan wires (unlike the hexapod `SolverReference` DoFs). The real saved points should confirm monotonicity.

The seeded curves today are PROVISIONAL: the x-points are the real configured Mono energies, but the positions are placeholders pending the real `store_0` table from 2-BM staff (see [Open questions](questions.md#energy-and-the-optics)). Runtime evaluation (`eval_lookup_table`) is now wired: the kernel interpolates a position for any requested energy and refuses an energy outside the calibrated range (`extrapolation_kind = Error`). Refusing rather than clamping is CORA's conservative default, not a staff-confirmed policy; whether out-of-range should refuse, clamp, or stay menu-only is the open question `ENERGY-4`. What stays deferred before a beamline move are the real saved positions, the per-facet constituent wiring that names each physical motor, and live EPICS dispatch, so for 2-BM this remains an intentional-completeness model rather than a motion path you can run against hardware today. The Bragg-arm angles, being a closed-form function of energy, may later become a computed relationship rather than an interpolated table. The coordinating operation that drives all these axes together (given one target energy) is the `set_energy` Procedure (see [Procedures](procedures.md)): it reads these curves to position each axis, and accepts a free keV value so an operator can request an energy between the configured saved points. The executable model lives in `apps/api/tests/integration/scenarios/test_2bm_energy_curves_setup.py` (the curves) and `test_2bm_set_energy.py` (the coordinating operation).

## Filter foil selection

Choosing an absorber foil is a discrete "pick one of N" move, the counterpart to the continuous energy curves above. Per the staff-authored docs2bm components page the foil changer has two paddles: the downstream paddle (`2bma:m18`) is operational, the upstream paddle (`2bma:m17`) is bound in software but not in service. The operational downstream paddle holds four materials plus an empty (`None`) slot.

CORA models the selector as a `Filter_FoilSelector` PseudoAxis under the `Filter` device, carrying a `LookupTable` rule with `interpolation_kind = Nearest` (snap to a slot) backed by an `index_position_table` Calibration. The operator commands a slot index; the rule snaps to the nearest tabulated slot and returns the saved motor position. The slot index is the calibration's `points` array order; each slot also carries its human name (`600 um Al`, `None`) for the audit trail. This reuses the same partition-rule kernel as the energy curves; the only differences are `Nearest` instead of `Linear` and a discrete index table instead of a continuous curve. `extrapolation_kind = Error` refuses a slot index outside the table (you cannot select a foil that is not there), and `invertible = False` with `readback_aggregator_kind = Identity` reconstructs the slot from the single constituent motor's readback.

Unlike the energy curves, the foil positions are REAL, not provisional: they are the staff-published downstream-paddle positions (`600 um Al` at 0, `150 um Al` at 26, `300 um C` at 53, `50 um C` at 80, `None` at 106). The one open item is the position unit: docs2bm reports it as the motor record EGU, "consistent with mm" but not definitively confirmed (`FOIL-1`). The runtime is wired and proven end-to-end (a "select foil" move snaps to the slot and dispatches its position through the in-memory ControlPort in `apps/api/tests/integration/test_pseudoaxis_roundtrip.py`); the model lives in `apps/api/tests/integration/scenarios/test_2bm_filter_foil_setup.py`.

Two things are deliberately out of scope here. The foil's ATTENUATION (the `Attenuable` affordance: transmission as a function of material, thickness, and beam energy) is a separate, richer concern deferred to later work; item 2 is the mechanical position-only move. And the mirror coating stripe, though also a coating selection, is NOT a discrete pick: docs2bm shows its selector (`2bma:m3`) is energy- and mode-dependent (held at one position in Mono, swept per energy in Pink with a coordinated table-X move) and publishes no stripe-to-position map, so it is modelled with the beam-mode work, not as a filter-style index axis.

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

Model ids are derived deterministically from the `(manufacturer, part number)` key, so the same vendor product converges on one id across facilities. `oms_vme58` is that case here: `SampleStageDrive` and `FrontEndDrive` are two physical boards of one product line, so both bind the single `oms_vme58` row. The two `unknown-pending-confirmation` rows are the exception: a placeholder part number is not a real vendor key, so `aerotech_hexapod_drive_unknown_pn` and `aerotech_2bmbaero_drive_unknown_pn` stay distinct rather than collapsing onto one id. Each re-registers under its derived id once its real part number is confirmed.

Part-number suffixes encode operationally significant variants: Aerotech `HEX300-230HL-E1-PL4-TAS` (`-E1` incremental encoder, `-PL4` ultra-high-accuracy preload, `-TAS` thermally stabilized), `ABS250MP-M-AS` (`-M` mid-precision class, `-AS` air-bearing series), and `PRO225SL-1000` (`-1000` mm travel). The full type designation is stored as a single `part_number` string.

All five `MotionController` Assets are named for the equipment they drive; vendor identity lives on the bound `Model` and the EPICS / IOC handle in `alternate_identifiers`, per the [Asset instance names](../../reference/conventions.md#asset-instance-names) convention.

| Controller Asset | Drives | Bound Model | Back-reference |
| --- | --- | --- | --- |
| `RotaryDrive` | `Rotary` | `aerotech_ensemble` (Ensemble HLE10-40-A-MXH) | `Rotary.controller_id` |
| `HexapodDrive` | `Hexapod` | `aerotech_hexapod_drive_unknown_pn` | `Hexapod.controller_id` |
| `FocusDrive` | `Focus` (EPICS IOC `2bmbAERO`) | `aerotech_2bmbaero_drive_unknown_pn` | `Focus.controller_id` |
| `SampleStageDrive` | `SampleTop_X` (`2bmb:m18`), `SampleTop_Z` (`2bmb:m17`), and 89 further motors on crate `ioc2bmb` | `oms_vme58` | `SampleTop_X.controller_id`, `SampleTop_Z.controller_id` |
| `FrontEndDrive` | the front-end optics on crate `ioc2bma`: `Mirror`, `Monochromator`, `ConditioningSlit`, `SampleSlit`, `Filter` | `oms_vme58` | `controller_id` on each of the five optics |

The two OMS VME58 boards bind the same `oms_vme58` Model row (one product line, two physical boards); per-instance identity (serial number, firmware version) lives in each Asset's [Settings](#settings). `HexapodDrive` and `FocusDrive` are Aerotech drives whose product line the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) does not name, so their Models carry `unknown-pending-confirmation` part numbers until staff confirm the hardware.

The Microscope objective selector (`2bmb:m1`) and camera selector (`2bmb:m5`) are stepper motors, identified on the source page as a Nanotec `ST4118M1404-B` and a Schunk `LPTM 30`, driven through the `SampleStageDrive` OMS VME58 crate rather than through dedicated controller boxes. Whether to register those steppers as distinct controller Assets, or carry them as the selector stages' motors, is a deferred follow-on.

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

The `max_speed_*`, `resolution_*`, and `accuracy_*` pairs collapse the six per-DoF measurements to two values per metric; the vendor datasheet's per-DoF variation is small enough that the dominant-DoF figure is a faithful envelope. The six per-DoF PseudoAxis facets (`Hexapod_X` ... `Hexapod_Yaw`) are the surface a Method binds against when it addresses a single DoF; this schema stays the envelope contract for the physical unit, and the facets carry no settings of their own.

### `MotionController`

Identity, configuration, and connectivity of a separately-modelled drive-electronics box. Per-axis Procedures target the driven stage Asset; controller-tier Procedures (firmware update, controller swap, sync-output retune) target the controller Asset and read these fields.

| Setting | Type | Required | Notes |
| --- | --- | --- | --- |
| `serial_number` | string, 1-128 chars | yes | Per-unit identity; operator-facing canonical key. Distinct from `Asset.alternate_identifiers` (PIDINST cross-reference set), which can also carry serial numbers among other schemes; `serial_number` here is the single operator-blessed canonical value. |
| `firmware_version` | string, 1-64 chars | yes | Reproducibility provenance: a controller without a recorded firmware version cannot answer "did the firmware change between Run X and Run Y". Free-text. |
| `ip_address` | string, 7-45 chars | no | Network identity. Optional because not every controller class is network-attached (RS-232 / RS-485 / VME-bus boxes have no IP). Format validation is shape-only at this layer (route / Pydantic may impose IPv4 / IPv6 regex when deployments warrant it). |
| `axis_count` | integer, 1-91 | yes | Operational metadata. Bounds bracket the smallest single-axis drive (1) to the largest OMS VME58 deployment at 2-BM (91 motors). |
| `protocol` | closed enum: `EPICS \| Aerotech_Native \| OMS_VME \| Serial_RS232 \| Serial_RS485 \| Modbus_TCP \| Other` | yes | Communication protocol. Six known values plus `Other`. |

`manufacturer` is NOT on this schema: vendor identity lives on the bound Model row per the Capability-declares-settings-schema pattern (`Aerotech` for `RotaryDrive` comes from `aerotech_ensemble`).

### `TimingController`

Identity, configuration, and connectivity of a separately-modelled timing-signal box. The driven device (the camera) carries the `Triggerable` affordance; the timing box carries `Pulsing` (via the `Controller` Role) because it is the active generator of the trigger pulse train. This schema backs the registered `Timing` Asset ([Settings](#timing)); the per-box values land via `update_asset_settings` once 2-BM staff confirms the physical softGlueZynq box (`TIME-1`).

| Setting | Type | Required | Notes |
| --- | --- | --- | --- |
| `serial_number` | string, 1-128 chars | yes | Per-unit identity; operator-facing canonical key. Same role as on `MotionController`. |
| `firmware_version` | string, 1-64 chars | yes | Reproducibility provenance. For an FPGA box this is the gateware / bitstream version: the trigger logic can change between Runs, so a Run cannot answer "did the timing change between Run X and Run Y" without it. Free-text. |
| `ip_address` | string, 7-45 chars | no | Network identity. The softGlueZynq is network-attached and EPICS-fronted; optional because future timing sources may not be. |
| `output_channel_count` | integer, 1-64 | yes | Number of independent trigger / gate output lines the box drives. Analogue of `MotionController.axis_count`. |
| `protocol` | closed enum: `EPICS \| Aerotech_Native \| OMS_VME \| Serial_RS232 \| Serial_RS485 \| Modbus_TCP \| Other` | yes | Communication protocol, shared closed enum with `MotionController`. softGlueZynq is `EPICS`. |

The detailed trigger routing (the softGlue logic-block wiring, e.g. the `PSO -> MUX2-1 -> GateDly1 -> camera Line2` path on the 2-BM box) is per-Run / per-Method configuration, not Asset settings: it changes with the scan, while the schema above records the durable box identity.

### `Camera`

Intrinsic detector properties, made explicit at 2-BM because a second detector class (the high-framerate PCO Dimax) shares the `Camera` Family with the FLIR Oryx and differs only along settings axes. The first four fields formalize what the per-Asset Settings already carry; the last three are the extension that lets one `Camera` Family span both detectors (variant-as-settings, not variant-as-subtype).

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

Bound to Model `aerotech_ensemble` (Aerotech Ensemble HLE10-40-A-MXH digital drive), drives `Rotary` (back-reference on `Rotary.controller_id`). The `unknown-pending-confirmation` placeholders below land via `update_asset_settings` once 2-BM staff confirm the serial number and firmware version on the hardware; the same holds for the other four drives.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

### `FocusDrive`

Bound to Model `aerotech_2bmbaero_drive_unknown_pn`, drives `Focus` (back-reference on `Focus.controller_id`). Operators address the focus motor via `2bmbAERO:m1` (IOC name + channel). The IOC is software (an EPICS process); the Asset modelled here is the hardware drive box behind it, so the IOC handle `2bmbAERO` lives in `alternate_identifiers` (kind `EPICS_PV`), not in the name. `axis_count=1` reflects the 1:1 binding to the single focus stage; `protocol=Aerotech_Native` matches the other Aerotech drives.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `1` |
| `protocol` | `Aerotech_Native` |

### `SampleStageDrive`

Bound to Model `oms_vme58`. The Oregon Micro Systems VME58 motor controller card in the 2-BM b-station IOC crate (`ioc2bmb`), addressed as `2bmb:m<N>`. It drives the `2bmb:m1`-`2bmb:m91` band, including `SampleTop_X` (`2bmb:m18`) and `SampleTop_Z` (`2bmb:m17`) which carry `controller_id` back-references; the remaining 89 motors are in [Pending](#pending). The Aerotech Ensemble axes (`2bmb:m100`-`2bmb:m102`) on the same IOC run through a separate Aerotech drive (the `RotaryDrive` Asset): one IOC, two physical controllers, two Assets. `axis_count=91` is the card's slot capacity even though only two channels are bound today; the board is VME-bus addressed, so `ip_address` is omitted.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

### `FrontEndDrive`

Bound to Model `oms_vme58` (same product line as `SampleStageDrive`; one Model row, two Asset instances). The Oregon Micro Systems VME58 card in the 2-BM a-station IOC crate (`ioc2bma`), driving the front-end / beam-conditioning band; the five optics `Mirror`, `Monochromator`, `ConditioningSlit`, `SampleSlit`, and `Filter` each carry a `controller_id` back-reference to it. `axis_count=91` is the card's slot capacity; the board is VME-bus addressed, so `ip_address` is omitted. The a-station and b-station cards carry distinct serial numbers and may run distinct firmware despite sharing the Model row.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `91` |
| `protocol` | `OMS_VME` |

### `HexapodDrive`

Bound to Model `aerotech_hexapod_drive_unknown_pn`, drives `Hexapod` (back-reference on `Hexapod.controller_id`). The [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) names the vendor (Aerotech) and an EPICS interface ("native Aerotech Ensemble", recorded in `alternate_identifiers`) but not the controller box or whether it is rack-separate or sealed into the stage, so the product line is left as a placeholder rather than overclaimed. `axis_count=6` reflects the hexapod's six degrees of freedom.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (DRIVE-1) |
| `firmware_version` | `unknown-pending-confirmation` (DRIVE-2) |
| `axis_count` | `6` |
| `protocol` | `Aerotech_Native` |

### `Timing`

The softGlueZynq FPGA timing box (`2bmbMZ1:SG:`) that generates the camera trigger pulse train (`PSO -> MUX2-1 -> GateDly1 -> camera Line2`). It carries the `Pulsing` affordance via the `Controller` Role and, unlike a `MotionController`, is itself the actor (the pulse generator), not a driven device, so it carries no `controller_id`. Substrate ("FPGA") is not a Family axis: the box is a `TimingController` whose identity and gateware (bitstream) version live in `settings`, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

The placeholders below land via `update_asset_settings` once 2-BM staff confirm the physical box (`TIME-1`). For an FPGA box the gateware/bitstream version is the reproducibility-critical field: the trigger logic can change between Runs, so a Run cannot answer "did the timing change between Run X and Run Y" without it.

| Setting | Value |
| --- | --- |
| `serial_number` | `unknown-pending-confirmation` (TIME-1) |
| `firmware_version` | `unknown-pending-confirmation` (TIME-1) |
| `output_channel_count` | `unknown-pending-confirmation` (TIME-1) |
| `protocol` | `EPICS` |

The detailed trigger routing (the softGlue logic-block wiring) is per-Run / per-Method configuration, not Asset settings.

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

`LinearStage` Family: the objective selector is a sliding ball-screw stage (Nanotec ST4118M1404-B, 1.8 deg/step over a 2 mm/rev ball screw, Heidenhain ERO 1420 encoder), not a rotating turret, confirmed on the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Positions are in millimeters and the constituent-wiring signal types are `linear_mm`. The min/max below are the operational span between the outer objective positions (1.1x at -60.030 mm, 10x at 58.640 mm).

| Setting | Value |
| --- | --- |
| `min_position` | `-60.030 mm` |
| `max_position` | `58.640 mm` |
| `encoder_resolution` | `0.0016 mm` |

## Engineering drawings

Each Asset may carry one canonical engineering reference as a `(system, number, revision)` triple per the [Drawing VO](../../architecture/modules/equipment/index.md). The carrier holds the build-to document for the physical specimen; the [Mount drawing](equipment/microscope.md#calibration-drawings-and-citation) on the slot is a separate document (where the slot lives in the beamline).

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

Devices that physically exist at 2-BM but are not yet registered as CORA Assets; each carries `new: true` in the 2-BM descriptor (`deployments/2-bm/beamline.yaml`). The five front-end / beam-conditioning optics driven by `FrontEndDrive` are now registered (see the [Inventory](#inventory)); `BeamPositionMonitor` remains an unmodelled front-end device, but a diagnostic, not a motor: the descriptor records no PV or controller for it.

Three `Table`-Family support tables also sit here pending registration: `SampleTable` (the four-motor translation table on the Vibraplane base that carries the hexapod stack), `DetectorTable` (the six-virtual-axis `2bmb:table3` table under the Optique Peter stage and microscope), and `MirrorTable` (`Dma:table1`, present but not used operationally). They differ by axis layout, not Family, so they share one `Table` Family ([Family settings schemas](#table)). Whether to describe all three, and whether the axis layout is a settings difference or a Family split, is tracked as `STAGE-7` and `STAGE-8` in [Open questions](questions.md).

| Asset | Family |
| --- | --- |
| `BeamPositionMonitor` | `Diagnostic` |
| `Camera_HighRes` | `Camera` (second FLIR Oryx, 31 MP, `2bmSP2:`) |
| `Camera_Selector` | `LinearStage` (Schunk LPTM 30, `2bmb:m5`) |
| `SampleTable` | `Table` |
| `DetectorTable` | `Table` |
| `MirrorTable` | `Table` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |

## Decommissioned (provenance only)

Detectors 2-BM ran in the past. They are neither active Assets nor awaiting registration; [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) records them under `decommissioned` for provenance. When modelled they are `Camera` Assets in a terminal lifecycle state: the `Camera` Family spans them and the active FLIR Oryx, because performance class ("high-speed") is a settings axis, not a separate Family, per [How families are decided](../../catalog/index.md#families-settings-over-subtypes).

| Asset | Family | Note |
| --- | --- | --- |
| `PCO_Dimax_HS` | `Camera` | High-speed CMOS camera; superseded by the FLIR Oryx detector chain. |
| `Adimec_Quartz_Q-12A180` | `Camera` | Earlier 2-BM CoaXPress camera. |
