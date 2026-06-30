# Sample

*The sample side. ESRF runs BLISS / Tango; the handles are the real BLISS object names read from the [public ID19 config](https://gitlab.esrf.fr/id19/beamline_configuration), carried `confirm` (CTRL-1).*

ID19 spins the sample through the beam and records a stack of projection radiographs, reconstructing a real-space volume downstream (microtomography). It does this at two endstations sharing one source and optics: the micro-resolution (MR) station for large-field, high-throughput tomography, and the high-resolution (HR) station for small-field, high-resolution tomography. Each has a tomographic rotation stage and a sample positioning stack.

| Asset | Family | Handle | What it does |
| --- | --- | --- | --- |
| `MR_RotationStage` | RotaryStage | `mrsrot` (Elmo) | MR tomographic spin; the master motion |
| `MR_SampleStage` | LinearStage | `mrsx/mrsy/mrxc/mryc/mryrot/mrsz` | MR sample centring + CoR alignment |
| `HR_RotationStage` | RotaryStage | `hrsrot` (Elmo_whistle) | HR tomographic spin; the master motion |
| `HR_SampleStage` | LinearStage | `hrsx/hrsy/hrsz/hrz0/hryrot` | HR sample centring + CoR alignment |

## The rotation stages

The tomographic rotation stage is the operative motion of microtomography: the continuous spin that carries the sample through the beam while the [detector](detector.md) records a projection at each angle. CORA binds both to the catalog [`RotaryStage`](../../../catalog/families.md) family.

- `MR_RotationStage` is the micro-resolution station's rotation (`mrsrot`, an Elmo serial controller over `rfc2217://lid192:28319`). It is the master motion of the MR scan, with a 900 deg/s ceiling, the axis expected to clock the detector triggering (SAMPLE-1).
- `HR_RotationStage` is the high-resolution station's rotation (`hrsrot`, an Elmo_whistle controller over `rfc2217://lid192:28300`), the master motion of the HR scan, also with a 900 deg/s ceiling (SAMPLE-1).

Both play the role the rotary stage plays at the 2-BM pilot and the TomoWise design.

## The sample positioning stacks

Each station carries a linear sample positioning stack that centres the sample on the axis of rotation and steps it out of the beam for flat-field (reference) acquisition. CORA binds both to the catalog [`LinearStage`](../../../catalog/families.md) family.

- `MR_SampleStage` is the MR centring stack (`mrsx`/`mrsy` plus `mrxc`/`mryc` centring on `iceid191`/`iceid192`, and `mryrot`/`mrsz` translation under rotation). A BLISS `XYOnRotation` pseudo-axis controller (`mrxyonsrot`) keeps the sample centred as it rotates (SAMPLE-1).
- `HR_SampleStage` is the HR centring stack (`hrsx`/`hrsy` on `iceid192`, `hrsz`/`hrz0` on `iceid191`, plus `hryrot`). The HRTOMO BLISS session aliases these `srot`/`sz`/`sx`/`sy`/`yrot`; the `XYOnRotation` controller is `hrxyonsrot` (SAMPLE-1).

## Why no new family here

ID19 is a microtomography beamline, and CORA already models microtomography at the 2-BM operational pilot and the MAX IV TomoWise scaffold. The stages are ordinary: the rotation stages are `RotaryStage`, the positioning stacks are `LinearStage`, and the [detectors](detector.md) are `Camera`. No family graduates and the catalog is unchanged. The technique is the existing [`tomography` Method](../../../catalog/methods.md), a further consumer, not a new Method (TECH-1); the volume reconstruction from the projection stack is `ComputePort` work, not a beamline device. The full deployment-level reasoning is on the [model](../model.md) page.

The genuine novelty at ID19 is not on this page at all: it is one layer down, in the control floor. ESRF runs BLISS (Tango-based), not EPICS, so these stages are BLISS axes driven by Elmo and IcePAP controllers rather than EPICS motor records (CTRL-1, see [Controls](controls.md)). MR and HR differ in stage stack and magnification optic, a Practice-and-settings difference, not new vocabulary. The [beamline](../beamline.md) source-walk and the [inventory](../inventory.md) carry the flat reference.
