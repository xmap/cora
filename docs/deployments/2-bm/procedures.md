# Procedures

*Operation BC Procedures registered at 2-BM.*

Each Procedure binds a Method + Practice + Plan to a set of target Assets. See [Model](../../architecture/model.md) for the aggregate shape.

| Procedure | Target Assets |
| --- | --- |
| `motor_homing` | `Rotary`, `SampleTop_X` |
| `first_light` | `StationShutter` + image chain |
| `dark_baseline` | `StationShutter` + image chain |
| `flat_baseline` | `StationShutter` + image chain |
| `resolution_alignment` | `Focus` + image chain |
| `focus_alignment` | `SampleTop_Z` + image chain |
| `center_alignment` | `Rotary`, `SampleTop_X` + image chain |
| `roll_alignment` | `Rotary`, `Hexapod_Roll` + image chain |
| `pitch_alignment` | `Rotary`, `Hexapod_Pitch` + image chain |
| `sensitivity_characterization` | `Hexapod_Roll`, `Hexapod_Pitch` |
| `hexapod_reboot` | `Hexapod` |

Image chain = `Camera`, `Scintillator`.

When `center_alignment` converges, the operator records the result as a `rotation_center` [Calibration](../../architecture/modules/calibration/index.md) on the rotary stage, appended with a `MeasuredSource` citing the Procedure. The alignment is the act; the Calibration stores the value.

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
