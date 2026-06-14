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
| `alignment_calibration` | `Hexapod_Roll` |
| `hexapod_reboot` | `Hexapod` |

Image chain = `Camera`, `Scintillator`.

## Pending

| Procedure | Target Assets |
| --- | --- |
| `alignment_auto_chain` | alignment Assets (calibration + Step1..4) |
| `energy_calibration` | channel-cut crystal + DMM |
| `ioc_restart` | EPICS IOC-hosted Assets |
| `vibration_baseline` | high-speed camera |
| `mirror_recoat_return` | `Mirror` |
