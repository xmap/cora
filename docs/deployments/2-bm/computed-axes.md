# Computed axes

*2-BM's virtual axes: the `PseudoAxis` Assets whose position is computed from the motors underneath, by a firmware solver, by an edge IOC, or by a `Calibration`-backed lookup. For how the pattern works in general see [Virtual axes and partition rules](../../architecture/modules/equipment/index.md#virtual-axes-and-partition-rules); this page is the 2-BM instances.*

The `PseudoAxis` Assets in the [Inventory](assets.md#inventory) (the hexapod degrees of freedom, the detector-table axes, the energy-tracking optic axes, and the filter foil selector) each present one operator-addressable axis whose value resolves onto real motors. They divide three ways by who owns the math: a firmware `SolverReference` (the hexapod), an edge IOC with no rule at all (the detector table), or a `Calibration`-backed `LookupTable` (the energy axes and the foil selector). Beam-mode switching, the other coordinated optic move, is not a virtual axis; it lives on the [Procedures](procedures.md#beam-modes-mono-pink) page.

## Hexapod DoF model

`Hexapod` is one physical Device (the vendor-sealed Aerotech HEX300; inverse kinematics runs in controller firmware). Its six degrees of freedom are surfaced as six `PseudoAxis` sub-modules parented to it (Device-in-Device, the addressable-sub-module case the `register_asset` decider sanctions), so a Plan, Procedure, or Caution can address a single DoF by name. Each DoF carries a `SolverReference` partition rule naming the firmware solver (`2bmHXP`); the per-DoF envelope is NOT duplicated onto the facets (it stays on the [`Hexapod` settings schema](assets.md#hexapod) for the physical unit), and the EPICS PVs live in each facet's `alternate_identifiers`, not in its name.

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

## Detector table axes

The detector optical table presents six virtual axes on the `2bmb:table3` record, modelled as six `PseudoAxis` sub-Assets parented to `DetectorTable` (Device-in-Device, like the hexapod DoFs). They use the hexapod-aligned axis vocabulary so CORA has one consistent positioner-axis naming:

| Axis Asset | Kind | `table3` field | Raw label |
| --- | --- | --- | --- |
| `DetectorTable_X` | translation | `.X` | n/a |
| `DetectorTable_Y` | translation | `.Y` | n/a |
| `DetectorTable_Z` | translation | `.Z` | n/a |
| `DetectorTable_Pitch` | rotation | `.AX` | `AX` |
| `DetectorTable_Yaw` | rotation | `.AY` | `AY` |
| `DetectorTable_Roll` | rotation | `.AZ` | `AZ` |

Unlike the hexapod, these axes carry NO partition rule and no constituent wiring. The `table3` IOC record (the `table_full` IOC) computes the pose from the six support motors (`M0X` / `M0Y` / `M1Y` / `M2X` / `M2Y` / `M2Z`) in its SRI geometry, so the kinematics are owned by the edge, not by CORA. Addressing an axis is a direct ControlPort write to its `table3.*` PV, and the IOC moves the supports. This is the spine/edge seam: coordinated actuation lives at the edge; CORA names the axis and records the move rather than re-implementing the geometry (which would create a second, drift-prone source of truth). Each axis's `table3.*` PV, plus the raw `AX` / `AY` / `AZ` label for the rotations, live in its `alternate_identifiers`. The angular-axis mapping (`AX` = pitch, `AY` = yaw, `AZ` = roll) is staff-confirmed (STAGE-9). The model lives in `apps/api/tests/integration/scenarios/test_2bm_optical_tables_setup.py`.

## Energy-tracking optic axes

Setting the beam energy at 2-BM is a discrete coordinated move, not one knob. The staff energy-change IOC stores per-energy positions for the whole double-multilayer monochromator (the `store_0` saved table) and drives roughly fifteen motors together (some are discrete index moves, not continuous curves) to a configured set of energies (Mono 13.374, 13.574, 18.0, 20.0, 25.0, 25.584 keV), per the staff-authored [docs2bm components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). The motors that actually move with energy are the DMM Bragg arms (`dmm_us_arm` / `dmm_ds_arm`) and the M2 vertical offset compensator (`dmm_m2_y`), plus the B-station sample-slit vertical pair (`b_slit_top` / `b_slit_bot`) tracking the resulting beam walk. Two things that look like energy axes are not: `crystal2_z` (M2 Z, `2bma:m8`) is a setup translation the IOC does not drive, and the mirror is held constant (its deflection geometry does not change with energy). Neither carries an energy curve. One thing CORA does not yet model at all is the DMM lateral stripe: the substrate carries two multilayer periods (13.8 and 24 angstrom) on stripes 4 mm apart, and the upstream / downstream X motors (`2bma:m25` / `2bma:m28`) may select between them per energy band. Whether that is an operator-facing selection (which would become a named stripe selector, like the mirror's) or a fixed setup is the open question `ENERGY-6`.

CORA models each per-axis relationship as a continuous curve. The underlying physics is continuous (Bragg geometry), so the beamline's discrete saved list is its operational sampling, not a limit: CORA interpolates the saved points and can answer for an off-list energy too. The carrier is a `PseudoAxis` sub-module parented to the physical optic (Device-in-Device, like the hexapod DoFs), carrying a `LookupTable` partition rule that converts energy (`unit_in = "keV"`) to the axis position (`unit_out` is `deg` for the Bragg arms, `mm` for the offset compensator and the slit blades). The rule pins a `Calibration` revision by id rather than inlining the table, so the conversion is reproducible and survives recalibration.

The carrier `Calibration` uses the `energy_position_curve` quantity: the whole curve across energy lives in ONE revision (a `points` array) so the `LookupTable` rule can pin it by id and interpolate. `axis_designation` is the staff handle; `beam_mode` is `mono`, since these axes track energy only in Mono mode. For the quantity shape, see [Calibration quantities](../../architecture/modules/calibration/index.md).

`invertible = True`: the underlying Bragg geometry is monotonic in energy, so the readback reconstructs by inverse interpolation and the facet needs no constituent ports or Plan wires (unlike the hexapod `SolverReference` DoFs). The real saved points should confirm monotonicity.

The seeded curves today are PROVISIONAL: the x-points are the real configured Mono energies, but the positions are placeholders pending the real `store_0` table from 2-BM staff (see [Open questions](questions.md#energy-and-the-optics)). Runtime evaluation (`eval_lookup_table`) is now wired: the kernel interpolates a position for any requested energy and refuses an energy outside the calibrated range (`extrapolation_kind = Error`). Refusing rather than clamping is CORA's conservative default, not a staff-confirmed policy; whether out-of-range should refuse, clamp, or stay menu-only is the open question `ENERGY-4`. What stays deferred before a beamline move are the real saved positions, the per-facet constituent wiring that names each physical motor, and live EPICS dispatch, so for 2-BM this remains an intentional-completeness model rather than a motion path you can run against hardware today. The Bragg-arm angles, being a closed-form function of energy, may later become a computed relationship rather than an interpolated table. The coordinating operation that drives all these axes together (given one target energy) is the `set_energy` Procedure (see [Procedures](procedures.md)): it reads these curves to position each axis, and accepts a free keV value so an operator can request an energy between the configured saved points. The executable model lives in `apps/api/tests/integration/scenarios/test_2bm_energy_curves_setup.py` (the curves) and `test_2bm_set_energy.py` (the coordinating operation).

These curves describe where the optics go for a commanded energy; they do not say whether that commanded energy is the true one. That separate measurement is the `energy_offset` [Calibration](../../architecture/modules/calibration/index.md) on the `Monochromator`, produced by the `energy_characterization` [Procedure](procedures.md) (the channel-cut rocking curve, [item_022](https://docs2bm.readthedocs.io/en/latest/source/ops/item_022.html)). CORA keeps the offset independent of these curves: the correction belongs at the energy-command layer, not inside the energy-to-position table. Whether the energy-change IOC already folds the measured offset into the saved `store_0` positions, or applies it separately, is the open question `ENERGY-8`.

## Filter foil selection

Choosing an absorber foil is a discrete "pick one of N" move, the counterpart to the continuous energy curves above. Per the staff-authored docs2bm components page the foil changer has two paddles: the downstream paddle (`2bma:m18`) is operational, the upstream paddle (`2bma:m17`) is bound in software but not in service. The operational downstream paddle holds four materials plus an empty (`None`) slot.

CORA models the selector as a `Filter_FoilSelector` PseudoAxis under the `Filter` device, carrying a `LookupTable` rule with `interpolation_kind = Nearest` (snap to a slot) backed by an `index_position_table` Calibration. The operator commands a slot index; the rule snaps to the nearest tabulated slot and returns the saved motor position. The slot index is the calibration's `points` array order; each slot also carries its human name (`600 um Al`, `None`) for the audit trail. This reuses the same partition-rule kernel as the energy curves; the only differences are `Nearest` instead of `Linear` and a discrete index table instead of a continuous curve. `extrapolation_kind = Error` refuses a slot index outside the table (you cannot select a foil that is not there), and `invertible = False` with `readback_aggregator_kind = Identity` reconstructs the slot from the single constituent motor's readback.

Unlike the energy curves, the foil positions are REAL, not provisional: they are the staff-published downstream-paddle positions (`600 um Al` at 0, `150 um Al` at 26, `300 um C` at 53, `50 um C` at 80, `None` at 106). The one open item is the position unit: docs2bm reports it as the motor record EGU, "consistent with mm" but not definitively confirmed (`FOIL-1`). The runtime is wired and proven end-to-end (a "select foil" move snaps to the slot and dispatches its position through the in-memory ControlPort in `apps/api/tests/integration/test_pseudoaxis_roundtrip.py`); the model lives in `apps/api/tests/integration/scenarios/test_2bm_filter_foil_setup.py`.

Two things are deliberately out of scope here. The foil's ATTENUATION (the `Attenuable` affordance: transmission as a function of material, thickness, and beam energy) is a separate, richer concern deferred to later work; item 2 is the mechanical position-only move. And the mirror coating stripe, though also a coating selection, is NOT a discrete pick: docs2bm shows its selector (`2bma:m3`) is energy- and mode-dependent (held at one position in Mono, swept per energy in Pink with a coordinated table-X move) and publishes no stripe-to-position map, so it is modelled with the [beam-mode work](procedures.md#beam-modes-mono-pink), not as a filter-style index axis.
