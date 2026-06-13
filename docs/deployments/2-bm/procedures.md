# Procedures

*Operation BC Procedures registered at 2-BM.*

Each Procedure binds a Method + Practice + Plan to a set of target Assets. See [Model](../../architecture/model.md) for the aggregate shape.

| Procedure | Target Assets |
| --- | --- |
| `motor_homing` | `Aerotech_ABRS_rotary`, `Sample_top_X` |
| `first_light` | `Shutter_2BM` + image chain |
| `dark_baseline` | `Shutter_2BM` + image chain |
| `flat_baseline` | `Shutter_2BM` + image chain |
| `resolution_alignment` | `Optique_Peter_focus_Z` + image chain |
| `focus_alignment` | `Sample_top_Z` + image chain |
| `center_alignment` | `Aerotech_ABRS_rotary`, `Sample_top_X` + image chain |
| `roll_alignment` | `Aerotech_ABRS_rotary`, `Sample_top_Roll` + image chain |
| `pitch_alignment` | `Aerotech_ABRS_rotary`, `Sample_top_Pitch` + image chain |
| `alignment_calibration` | `Sample_top_Roll` |
| `hexapod_reboot` | `Hexapod_2BM` |

Image chain = `Oryx_5MP_camera`, `Scintillator_LuAG`.

## Pending

| Procedure | Target Assets |
| --- | --- |
| `alignment_auto_chain` | alignment Assets (calibration + Step1..4) |
| `energy_calibration` | channel-cut crystal + DMM |
| `ioc_restart` | EPICS IOC-hosted Assets |
| `vibration_baseline` | high-speed camera |
| `mirror_recoat_return` | `Y3-30_mirror` |
