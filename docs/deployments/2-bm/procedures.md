# Procedures

*Operation BC Procedures registered at 2-BM.*

A Procedure is the record of one operational task. It acts on a set of target Assets and may realize a [Capability](../../catalog/capabilities.md); it runs either standalone or as a phase of a [Run](runs.md). The Procedure aggregate does not itself bind a Method, Practice, or Plan: those name the technique and its wiring, while the Procedure is the task record and its per-step log. See [Model](../../architecture/model.md) for the aggregate shape.

The line between a Run and a Procedure is the data product: an operation that yields a scientific [Dataset](datasets.md) is a [Run](runs.md), one that only performs and logs a task is a Procedure. The dark- and flat-field baselines therefore run as subject-less calibration [Runs](runs.md), not Procedures; the tasks below are the no-data operations: homing, alignment, characterization, recovery, and the coordinated energy change.

An operation can also be authored as a [Recipe](recipes.md): a reusable, parameterized step sequence (setpoint / check / action) that expands into a Procedure once an operator binds its tunable values.

| Procedure | Target Assets |
| --- | --- |
| `motor_homing` | `Rotary`, `SampleTop_X` |
| `first_light` | `StationShutter` + image chain |
| `resolution_alignment` | `Focus` + image chain |
| `focus_alignment` | `SampleTop_Z` + image chain |
| `center_alignment` | `Rotary`, `SampleTop_X` + image chain |
| `roll_alignment` | `Rotary`, `Hexapod_Roll` + image chain |
| `pitch_alignment` | `Rotary`, `Hexapod_Pitch` + image chain |
| `sensitivity_characterization` | `Hexapod_Roll`, `Hexapod_Pitch` |
| `hexapod_reboot` | `Hexapod` |
| `set_energy` | the energy-tracking facets (`Monochromator` Bragg arms + M2 offset, `SampleSlit` vertical pair) |

Image chain = `Camera`, `Scintillator`.

When `center_alignment` converges, the operator records the result as a `rotation_center` [Calibration](../../architecture/modules/calibration/index.md) on the rotary stage, appended with a `MeasuredSource` citing the Procedure. The alignment is the act; the Calibration stores the value.

`set_energy` is the coordinating energy-change operation (the Procedure kind names the specific operation, distinct from the `cora.capability.energy_change` Capability code it realizes, as `motor_homing` sits under `maintenance`): given a target energy (a free keV value), it drives the energy-tracking optic axes together to their per-energy positions, reading each axis's [energy curve](assets.md#energy-tracking-optic-axes). A Method declares the free-keV parameter; the Procedure expresses the coordinated move. It satisfies the `energy_configured` precondition stub listed under [From the 2-BM procedures source](#from-the-2-bm-procedures-source). Because the curves interpolate, an operator can request an energy between the configured saved points, not just the menu. The operator's `EnergyChange` Decision (modeled in the energy-change scenario) is the forward-looking justification; this Procedure is the motion record. The per-axis curve evaluation is now wired: the runtime interpolates a position for any requested energy (including a value between the saved points), and refuses an energy outside the calibrated range rather than clamping. Executing the coordinated move at the beamline still needs three things, so today the Procedure records the move rather than driving it: the real saved positions (the seeded curves are provisional pending staff), the per-facet constituent wiring that names each physical motor, and live EPICS dispatch.

## From the 2-BM procedures source

The [2bm-procedures](https://github.com/xray-imaging/2bm-procedures) repo ([rendered](https://docs2bm.readthedocs.io/en/latest/source/procedures.html)) is the staff-authored source for 2-BM procedures. Three are validated at the beamline; CORA has not modelled them yet (their target Assets are in [Pending](#pending)). Each staff procedure is structured as Name / Devices / Preconditions / Parameters / Steps / Postconditions / Failure modes; adopting that precondition-graph shape (the tables here are flat) is a future Operation BC concern.

| Staff procedure (validated) | Target Assets | Note |
| --- | --- | --- |
| Detector Z-rail alignment to the beam | `DetectorTable` (angular axes `2bmb:table3.AX` / `.AY`) | NOT the same as `roll_alignment` / `pitch_alignment` above: those align the sample `Hexapod`, not the detector table |
| Centre and close an L3-style slit aperture | `ConditioningSlit` | two-phase: centre on Hcenter / Vcenter, then sequential H / V size reduction |
| Calibrate the throw of each L3 slit blade motor | `ConditioningSlit` blade motors | drive each blade by +/- blade_throw_mm, measure edge shift, report per-blade slopes |

The source also defines eight stub procedures as named targets for a precondition graph (each declares only its postcondition): `beamline_enabled`, `a_slits_open`, `energy_configured`, `flag_in_beam`, `b_shutter_open` (P6-50 safety shutter), `b_slits_configured`, `sample_out_of_beam`, `microscope_configured`. They become real Procedures as the alignment procedures' preconditions are modelled.

## Pending

| Procedure | Target Assets |
| --- | --- |
| `alignment_auto_chain` | alignment Assets (characterization + Step1..4) |
| `energy_characterization` | channel-cut crystal + DMM |
| `ioc_restart` | EPICS IOC-hosted Assets |
| `vibration_baseline` | high-speed camera |
| `mirror_recoat_return` | `Mirror` |
