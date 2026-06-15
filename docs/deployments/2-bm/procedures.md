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

## Pending

| Procedure | Target Assets |
| --- | --- |
| `alignment_auto_chain` | alignment Assets (characterization + Step1..4) |
| `energy_characterization` | channel-cut crystal + DMM |
| `ioc_restart` | EPICS IOC-hosted Assets |
| `vibration_baseline` | high-speed camera |
| `mirror_recoat_return` | `Mirror` |
