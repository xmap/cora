# Controls

*How 2-BM hardware is driven: the controllers and drive crates, and the trigger box that links them. The drive electronics, gathered in one place; the per-Asset settings, port maps, and Plan wires stay in the [Inventory](../inventory.md).*

A controller is an `Asset` like any other, but it relates to the hardware it moves sideways, through the `controller_id` back-reference, not through containment. That is why controls is its own area rather than a part of any one station: a single controller routinely spans the beam-path stations.

## Motion controllers

Each box's bound vendor Model, communication protocol, slot capacity, and EPICS handle. Per-unit identity (serial, firmware) and the full driven-Asset back-references live in the [Inventory settings](../inventory.md#settings) and [vendor catalog](../inventory.md#vendor-catalog-models).

| Controller | Drives | Model | Protocol | Axes | EPICS handle |
| --- | --- | --- | --- | --- | --- |
| `RotaryDrive` | `Rotary` | Aerotech `aerotech_ensemble_ml` | `Aerotech_Native` | 1 | `2bmb:m100`-`m102` (`ioc2bmb`) |
| `HexapodDrive` | `Hexapod` (six DoF) | Aerotech `aerotech_automation1_ixr3` | `Aerotech_Native` | 6 | `2bmHXP:` |
| `PropagationDistanceDrive` | `PropagationDistance` | Aerotech `aerotech_ensemble_hle` | `Aerotech_Native` | 1 | `2bmbAERO` |
| `SampleStageDrive` | the sample stages, and the Detector objective / camera selectors | OMS `oms_vme58` | `OMS_VME` | 91 | `ioc2bmb` (`2bmb:m*`) |
| `FrontEndDrive` | the front-end optics: `Mirror`, `Monochromator`, `ConditioningSlit`, `SampleSlit`, `Filter` | OMS `oms_vme58` | `OMS_VME` | 91 | `ioc2bma` (`2bma:m*`) |
| `ApertureFineDrive` | the `Aperture` coded-mask (X/Y fine positioning, FPGA-stepped) | Piezosystem Jena `piezosystem_jena_nv200d` (two NV200D units) | `EPICS` | 2 | `JenaNV200D` (host `arcturus`) |

`SampleStageDrive` reaching the Detector selectors, and `Timing` (below) reaching both the camera and the aperture piezo, are why controls is modelled as a cross-cutting area: nesting these boxes under a single station would mis-attribute most of the graph. The two OMS VME58 cards bind one `oms_vme58` Model row (one product line, two physical boards); the Microscope objective (`2bmb:m1`) and camera (`2bmb:m5`) selector steppers run through the `SampleStageDrive` crate rather than as distinct controller Assets.

## Triggering

The timing box is not a `MotionController`: it is itself the actor that generates the pulse train, so it carries the `Pulsing` affordance rather than a `controller_id`.

| Controller | Generates | Model | Protocol | EPICS handle |
| --- | --- | --- | --- | --- |
| `Timing` | the camera frame trigger, plus two sample-piezo step triggers on a readout boundary | softGlueZynq (Xilinx Zynq on a MicroZed carrier) | `EPICS` | `2bmbMZ1:SG:` |

The trigger legs are modelled as Asset ports resolved into Plan wires: see [Signal wiring](../inventory.md#signal-wiring-ports-and-plan-wires) for the camera and NV200D port maps. The box's gateware version and output-channel count are pending (`TIME-1`).

## Software IOCs

Several control paths are software IOCs, not hardware: `ioc2bma`, `ioc2bmb`, `energy`, `MCTOptics`, `table_full`, and `2filter` are EPICS processes referenced by PV prefix in the Plan and Method wiring layer, never registered as Assets.

## Affordances and detail

The two controller Families carry almost no command surface: `MotionController` declares no [affordances](../../../reference/affordances.md) at v1 (its meaningful state, firmware, IP address, axis count, protocol, lives in `settings`), and `TimingController` carries only `Pulsing` through the `Controller` Role. The full driven-Asset back-references and the trigger-wiring port maps are on the [Inventory](../inventory.md#signal-wiring-ports-and-plan-wires) page.
