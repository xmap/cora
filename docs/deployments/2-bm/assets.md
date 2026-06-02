# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

## Inventory

| Asset | Level | Family | Parent |
| --- | --- | --- | --- |
| `Shutter_2BM` | `Device` | `Shutter` | `2-BM` |
| `Aerotech_ABRS_rotary` | `Device` | `RotaryStage` | `2-BM` |
| `Sample_top_X` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Z` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Roll` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Pitch` | `Device` | `LinearStage` | `2-BM` |
| `Hexapod_2BM` | `Device` | `Hexapod` | `2-BM` |
| `Optique_Peter_focus_Z` | `Device` | `LinearStage` | `2-BM` (wired into `MCTOptics`) |
| `MCTOptics` | `Component` | `Microscope` | `2-BM` |
| `MCTOptics_lens_turret` | `Device` | `RotaryStage` (pending) | `2-BM` (wired into `MCTOptics`) |
| `MCTOptics_objective_0` | `Device` | `Objective` | `MCTOptics` |
| `MCTOptics_objective_1` | `Device` | `Objective` | `MCTOptics` |
| `MCTOptics_objective_2` | `Device` | `Objective` | `MCTOptics` |
| `Oryx_5MP_camera` | `Device` | `Camera` | `MCTOptics` |
| `Scintillator_LuAG` | `Device` | `Scintillator` | `MCTOptics` |

### MCTOptics composition

The Optique Peter detector at ~55 m from the source (controlled by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py)) registers as a `Microscope`-Family Component with 5 Device children. The lens turret sits as a sibling under 2-BM (wired in, not a child), and the existing `Optique_Peter_focus_Z` linear stage is reused for shared focus.

```
2-BM (Unit)
+-- MCTOptics (Component)                 Family: Microscope
|   +-- MCTOptics_objective_0 (Device)    Family: Objective    10x
|   +-- MCTOptics_objective_1 (Device)    Family: Objective     5x
|   +-- MCTOptics_objective_2 (Device)    Family: Objective    1.1x
|   +-- Oryx_5MP_camera (Device)          Family: Camera
|   +-- Scintillator_LuAG (Device)        Family: Scintillator
+-- MCTOptics_lens_turret (Device)        Family: RotaryStage (pending)
+-- Optique_Peter_focus_Z (Device)        Family: LinearStage
```

Routing (which objective / camera is currently in the beam) lives OUTSIDE Family settings per the [design lock](../../architecture/modules/equipment/index.md#aggregates): runtime parameters belong on `Method.parameters_schema`, not on `Family.settings_schema`. The lens selector at Run time is the Method parameter `lens_select` (integer 0-2), wired through the topology below.

#### Wiring

Five wires connect MCTOptics to its sibling motors and camera child. The `image_out` port on `Oryx_5MP_camera` does NOT terminate at MCTOptics; image data flows to a separate data-pipeline adapter Asset out of scope for this inventory.

| Source | Source port | Target | Target port |
| --- | --- | --- | --- |
| `MCTOptics` | `lens_turret_setpoint` | `MCTOptics_lens_turret` | `position_setpoint_in` |
| `MCTOptics_lens_turret` | `position_feedback_out` | `MCTOptics` | `lens_turret_feedback` |
| `MCTOptics` | `focus_setpoint` | `Optique_Peter_focus_Z` | `position_setpoint_in` |
| `Optique_Peter_focus_Z` | `position_feedback_out` | `MCTOptics` | `focus_feedback` |
| `MCTOptics` | `camera_trigger` | `Oryx_5MP_camera` | `trigger_in` |

Signal-type vocabulary (locked): `position_setpoint_rotation_deg` / `position_feedback_rotation_deg`, `position_setpoint_linear_mm` / `position_feedback_linear_mm`, `trigger_pulse`, `image_frame_uri` (opaque URI + checksum; pixel format negotiated by the data-pipeline adapter).

The full deployment ceremony is materialized end-to-end in [test_2bm_mctoptics_setup.py](https://github.com/xmap/cora/blob/main/apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py).

## Family affordances

Each Family declares a closed-enum set of operational primitives ([Affordances](../../reference/affordances.md)). The set is required at Family definition and replaces wholesale on `version_family`.

| Family | Affordances |
| --- | --- |
| `Shutter` | `Shutterable` |
| `RotaryStage` | `Rotatable`, `Homeable`, `Limitable`, `Following`, `Marking` |
| `LinearStage` | `Translatable`, `Homeable`, `Limitable`, `Following` |
| `Hexapod` | `Posable`, `Homeable`, `Limitable` |
| `Scintillator` | `Consumable` |
| `Camera` | `Imageable`, `Binnable`, `Triggerable`, `Streamable`, `Recording` |
| `Microscope` | (pending — empty at initial registration) |
| `Objective` | (pending — empty at initial registration) |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface).

## Family settings schemas

NEW schemas registered with the MCTOptics composition. The Phase 10e-a locked schemas (`RotaryStage`, `LinearStage`, `Camera`, `Scintillator`) are declared at the [APS Site assets](../aps/assets.md) level.

### `Microscope`

Intrinsic optical-geometry properties of a microscope-detector assembly.

| Setting | Type | Unit |
| --- | --- | --- |
| `camera_objective` | string | - |
| `camera_tube_length` | number | mm |

### `Objective`

Intrinsic per-lens properties. Motion is via the external turret + focus motors wired in through `Plan.wiring`; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

## Settings

### `Aerotech_ABRS_rotary`

| Setting | Value |
| --- | --- |
| `min_position` | `−360 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `720 deg/s` |
| `encoder_resolution` | `0.0001 deg` |
| `homing_offset` | `0 deg` |

### `Sample_top_X`

| Setting | Value |
| --- | --- |
| `min_position` | `−10 mm` |
| `max_position` | `10 mm` |
| `max_speed` | `1 mm/s` |
| `encoder_resolution` | `0.0005 mm` |

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

### `MCTOptics`

| Setting | Value |
| --- | --- |
| `camera_objective` | `"Mitutoyo Plan Apo"` |
| `camera_tube_length` | `200 mm` |

### `MCTOptics_objective_0` (10x)

| Setting | Value |
| --- | --- |
| `magnification` | `10.0` |
| `numerical_aperture` | `0.28` |
| `focal_length` | `20 mm` |
| `working_distance` | `33.5 mm` |

### `MCTOptics_objective_1` (5x)

| Setting | Value |
| --- | --- |
| `magnification` | `5.0` |
| `numerical_aperture` | `0.14` |
| `focal_length` | `40 mm` |
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

## Pending

| Asset | Family |
| --- | --- |
| `Mirror_2BM` | `Mirror` |
| `softGlueZynq_FPGA` | `TriggerFPGA` |
| `PCO_Dimax_HS` | `HighSpeedCamera` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |
